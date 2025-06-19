# main.py
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# Import the new, root-level modules
from config import Config
from heartbeat import HeartbeatSystem
# These files will be moved from their subdirectories by the script
from audit_logger import AuditLogger
from command_router import CommandRouter

# A dictionary to hold our running service instances
services = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages the startup and shutdown of background services."""
    print("NeuroSync starting up...")
    
    # 1. Initialize Configuration
    config = Config()
    
    # 2. Initialize Core Components
    services["config"] = config
    services["audit"] = AuditLogger(config)
    services["router"] = CommandRouter(config, services) # Pass services for inter-module communication
    services["heartbeat"] = HeartbeatSystem(config)

    # 3. Start background tasks for each long-running service
    asyncio.create_task(services["audit"].start())
    asyncio.create_task(services["heartbeat"].start_system_check_loop())
    
    print("All NeuroSync services have been started.")
    
    yield # The application is now running
    
    # This code runs on shutdown (e.g., when you press Ctrl+C)
    print("NeuroSync shutting down...")
    for name, service in services.items():
        if hasattr(service, 'stop'):
            await service.stop()
    print("All NeuroSync services have been stopped.")

# Create the FastAPI app instance with our new lifespan manager
app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "NeuroSync Network Core is active."}

@app.get("/health")
async def health_check():
    """A simple health check endpoint for other services to ping."""
    return {"status": "ok"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """The main WebSocket endpoint for high-speed, bidirectional communication."""
    await websocket.accept()
    print("Client connected via WebSocket.")
    try:
        while True:
            data = await websocket.receive_text()
            # Feed received data into the command router for processing
            response = await services["router"].handle_command(data)
            # Send the response back to the client
            if response:
                await websocket.send_text(response)
    except WebSocketDisconnect:
        print("Client disconnected.")

