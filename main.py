# NeuroSync/main.py (Definitive Version with all endpoints)
import logging
import asyncio
import httpx
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.WARNING)

# --- Configuration Class ---
load_dotenv()
class Config:
    def __init__(self):
        self.rolling5_status_url = os.getenv("ROLLING5_STATUS_URL")
        self.tradingcore_status_url = os.getenv("TRADINGCORE_STATUS_URL")
        self.check_interval_seconds = int(os.getenv("HEARTBEAT_INTERVAL", 15))

        if not self.rolling5_status_url or not self.tradingcore_status_url:
            raise ValueError(
                "CRITICAL ERROR: Missing URL secrets. "
                "Please ensure both ROLLING5_STATUS_URL and TRADINGCORE_STATUS_URL are set in Replit Secrets."
            )

# --- Background Heartbeat Task ---
async def heartbeat_loop(config: Config):
    """A background task that periodically pings other services."""
    logging.info(
        "Heartbeat monitor started. Checking services every %d seconds.",
        config.check_interval_seconds
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            # Check Rolling5
            try:
                response = await client.get(config.rolling5_status_url)
                if response.status_code == 200 and response.json().get("status") == "ok":
                    logging.info("Heartbeat: [Rolling5] is ✅ ONLINE")
                else:
                    logging.warning("Heartbeat: [Rolling5] is ❌ OFFLINE (Status: %d)", response.status_code)
            except httpx.RequestError as e:
                logging.error("Heartbeat: [Rolling5] is ❌ UNREACHABLE (%s)", e.__class__.__name__)
            
            # Check TradingCore
            try:
                response = await client.get(config.tradingcore_status_url)
                if response.status_code == 200 and response.json().get("status") == "ok":
                    logging.info("Heartbeat: [TradingCore] is ✅ ONLINE")
                else:
                    logging.warning("Heartbeat: [TradingCore] is ❌ OFFLINE (Status: %d)", response.status_code)
            except httpx.RequestError as e:
                logging.error("Heartbeat: [TradingCore] is ❌ UNREACHABLE (%s)", e.__class__.__name__)

            await asyncio.sleep(config.check_interval_seconds)

# --- FastAPI Lifespan Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    monitor_task = None
    try:
        config = Config()
        monitor_task = asyncio.create_task(heartbeat_loop(config))
    except ValueError as e:
        logging.critical(e)
    
    yield
    
    if monitor_task:
        logging.info("Shutting down heartbeat monitor...")
        monitor_task.cancel()

# --- FastAPI Application ---
app = FastAPI(lifespan=lifespan)

# --- THIS IS THE MISSING ENDPOINT ---
@app.get("/")
def root():
    """Root endpoint for browser and uptime checks."""
    return {"status": "ok", "service": "NeuroSync"}
# -----------------------------------

@app.get("/status")
def health_check():
    """A simple health check endpoint for other services to ping."""
    return {"status": "ok", "service": "NeuroSync"}
