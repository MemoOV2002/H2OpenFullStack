"""
Serial communication service for H2Open.
Parses CSV packets from the T-Beam base station over USB serial
and hands them off to the shared packet_processor.
Runs as a background thread alongside the HTTP ingest path.
"""
import os
import serial
import asyncio
import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

SERIAL_PORT  = os.getenv("SERIAL_PORT", "/dev/tty.usbserial-58971201781")
BAUD_RATE    = 115200
TIMEOUT      = 1          # seconds before readline() loops
SERIAL_ENABLED = os.getenv("SERIAL_ENABLED", "true").lower() == "true"


class SerialService:
    def __init__(self):
        self.ser      = None
        self._running = False
        self._thread  = None
        self._loop    = None

    def start(self, loop: asyncio.AbstractEventLoop):
        if not SERIAL_ENABLED:
            logger.info("Serial service disabled via SERIAL_ENABLED env var.")
            return
        self._loop    = loop
        self._running = True
        self._thread  = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        logger.info("Serial service started.")

    def stop(self):
        self._running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        logger.info("Serial service stopped.")

    def _connect(self):
        while self._running:
            try:
                self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT)
                logger.info(f"Serial connected: {SERIAL_PORT}")
                return True
            except serial.SerialException as e:
                logger.warning(f"Serial connect failed ({e}). Retrying in 5s...")
                threading.Event().wait(5)
        return False

    def _read_loop(self):
        if not self._connect():
            return

        while self._running:
            try:
                raw = self.ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    logger.info(f"[serial] {line}")
                    self._handle_line(line)
            except serial.SerialException as e:
                logger.error(f"Serial error: {e}. Reconnecting...")
                self._connect()

    def _handle_line(self, line: str):
        """
        Expected packet format (matches buoy firmware):
          conductivity,temperature,turbidity,pH
          e.g.  450.2,21.3,12.1,7.4
        """
        parts = line.split(",")
        if len(parts) != 4:
            logger.debug(f"Skipping non-packet line: {line!r}")
            return

        try:
            conductivity = float(parts[0])
            temperature  = float(parts[1])
            turbidity    = float(parts[2])
            ph           = float(parts[3])
        except ValueError:
            logger.debug(f"Non-numeric fields, skipping: {line!r}")
            return

        # Import DB session factory here to avoid circular imports
        from app.database import SessionLocal
        from app.services.packet_processor import process_packet

        async def _run():
            db = SessionLocal()
            try:
                await process_packet(
                    conductivity=conductivity,
                    temperature=temperature,
                    turbidity=turbidity,
                    ph=ph,
                    buoy_id="BUOY_01",
                    db=db,
                )
            finally:
                db.close()

        asyncio.run_coroutine_threadsafe(_run(), self._loop)


serial_service = SerialService()