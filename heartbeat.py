# NeuroSync/heartbeat.py
import asyncio
import httpx
from datetime import datetime

class HeartbeatSystem:
    def __init__(self, config):
        self.config = config
        headers = {"User-Agent": "NeuroSync Heartbeat Monitor"}
        self.client = httpx.AsyncClient(timeout=10.0, headers=headers)
        self.subsystems = {
            "TRADING_CORE": self.config.core_health_url,
            "ROLLING5_BOT": self.config.bot_health_url
        }

    async def check_subsystem(self, name: str, url: str):
        if not url:
            print(f"INFO: URL for '{name}' not configured. Skipping.")
            return
        try:
            response = await self.client.get(url)
            if response.status_code == 200:
                print(f"INFO: Heartbeat check SUCCESS for '{name}' ({response.status_code} OK)")
            else:
                print(f"ALERT: Heartbeat check FAILED for '{name}' (Status: {response.status_code})")
        except httpx.RequestError as e:
            print(f"ALERT: Heartbeat check FAILED for '{name}' (Error: {e.__class__.__name__})")

    async def start_monitoring(self):
        print("--- Heartbeat Monitoring Starting ---")
        while True:
            await asyncio.gather(*(self.check_subsystem(name, url) for name, url in self.subsystems.items()))
            await asyncio.sleep(self.config.heartbeat_interval_seconds)
