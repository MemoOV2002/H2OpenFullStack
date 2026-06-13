"""
WebSocket endpoint for real-time data streaming
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import json
import asyncio

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections for broadcasting updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"✅ New WebSocket connection. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove disconnected WebSocket"""
        self.active_connections.remove(websocket)
        print(f"❌ WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """
        Broadcast message to all connected clients
        Removes dead connections automatically
        """
        dead_connections = []
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"❌ Failed to send to client: {e}")
                dead_connections.append(connection)
        
        # Clean up dead connections
        for connection in dead_connections:
            self.active_connections.remove(connection)


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/live-data")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time sensor data
    
    Clients connect to: ws://localhost:8000/ws/live-data
    
    Messages sent to client:
    {
        "type": "sensor_reading",
        "buoy_id": "buoy_001",
        "ecoli_cfu": 180.5,
        "is_safe": true,
        "timestamp": "2025-01-27T10:30:00"
    }
    """
    await manager.connect(websocket)
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connection",
            "message": "Connected to H2Open live data stream",
            "active_connections": len(manager.active_connections)
        })
        
        # Keep connection alive and listen for client messages
        while True:
            # Wait for client message (or use this as heartbeat)
            data = await websocket.receive_text()
            
            # Echo back for testing
            await websocket.send_json({
                "type": "echo",
                "message": f"Received: {data}"
            })
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


async def broadcast_new_reading(reading_data: dict):
    """
    Helper function to broadcast new sensor reading to all connected clients
    
    Call this function when new data arrives from LoRa:
    
    await broadcast_new_reading({
        "type": "sensor_reading",
        "buoy_id": "buoy_001",
        "ecoli_cfu": 180.5,
        "is_safe": True,
        "temperature": 22.3,
        "timestamp": "2025-01-27T10:30:00"
    })
    """
    await manager.broadcast(reading_data)
    print(f"📡 Broadcasted reading to {len(manager.active_connections)} clients")


# For testing - simulate live data
async def simulate_live_data():
    """
    Test function to simulate live sensor data
    Remove this in production
    """
    import random
    from datetime import datetime
    
    while True:
        await asyncio.sleep(10)  # Send update every 10 seconds
        
        # Simulate reading
        reading = {
            "type": "sensor_reading",
            "buoy_id": f"buoy_00{random.randint(1, 3)}",
            "ecoli_cfu": round(random.uniform(100, 300), 1),
            "temperature": round(random.uniform(18, 25), 1),
            "is_safe": random.choice([True, False]),
            "timestamp": datetime.now().isoformat()
        }
        
        await manager.broadcast(reading)
