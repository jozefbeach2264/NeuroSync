# NeuroSync/main.py
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from config import Config
from heartbeat import HeartbeatSystem

# --- Lifespan Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("INFO: NeuroSync server starting up...")
    # Start the heartbeat monitor as a background task
    heartbeat_task = asyncio.create_task(app.state.heartbeat.start_monitoring())
    yield
    # Code to run on shutdown
    print("INFO: NeuroSync server shutting down...")
    heartbeat_task.cancel()
    print("INFO: Heartbeat monitor stopped.")

# --- Application Setup ---
app = FastAPI(lifespan=lifespan)
app.state.config = Config()
app.state.heartbeat = HeartbeatSystem(app.state.config)
app.state.connected_clients = set()

# --- WebSocket Endpoint ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    app.state.connected_clients.add(websocket)
    print(f"INFO: WebSocket client connected. Total clients: {len(app.state.connected_clients)}")
    try:
        while True:
            data = await websocket.receive_text()
            print(f"INFO: WebSocket received: {data}")
            # Optional: Broadcast to other clients
            # for client in app.state.connected_clients:
            #     if client != websocket:
            #         await client.send_text(f"Broadcast: {data}")
    except WebSocketDisconnect:
        app.state.connected_clients.remove(websocket)
        print(f"INFO: WebSocket client disconnected. Total clients: {len(app.state.connected_clients)}")

# --- HTTP Endpoint ---
@app.get("/status")
async def get_status():
    return {"status": "ok", "service": "NeuroSync"}
