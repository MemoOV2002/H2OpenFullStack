"""
H2Open Backend API
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routers import readings, status, websocket
from app.routers.ingest import router as ingest_router
from app.services.serial_service import serial_service

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting H2Open Backend API...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")

    # Serial is optional — disabled when SERIAL_ENABLED=false
    loop = asyncio.get_running_loop()
    serial_service.start(loop)

    yield

    serial_service.stop()
    print("🛑 H2Open API shut down.")


app = FastAPI(
    title="H2Open API",
    description="Water quality monitoring system for the Charles River",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(readings.router,  prefix="/api/v1", tags=["readings"])
app.include_router(status.router,    prefix="/api/v1", tags=["status"])
app.include_router(ingest_router,    prefix="/api/v1", tags=["ingest"])
app.include_router(websocket.router, prefix="/ws",     tags=["websocket"])


@app.get("/")
async def root():
    return {"message": "H2Open API is running", "version": "2.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "database": "connected", "websocket": "ready"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)