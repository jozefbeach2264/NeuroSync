# heartbeat.py
import asyncio
import time
import json
import httpx

try:
    import psutil
except ImportError:
    psutil = None

class HeartbeatSystem:
    """
    A centralized system to monitor self-status and the health of other subsystems.
    """
    def __init__(self, config):
        self.config = config
        self.sync_log_path = self.config.sync_log_file
        print("HeartbeatSystem Initialized.")

    def _get_self_status(self):
        """Checks the status of the local NeuroSync process."""
        memory_percent = 0
        if psutil:
            memory_percent = psutil.virtual_memory().percent
        
        return {
            "source": "neurosync_heartbeat",
            "timestamp": time.time(),
            "memory_percent": memory_percent
        }

    async def _check_subsystem_health(self, name: str, url: str, client: httpx.AsyncClient):
        """Pings a subsystem's /health endpoint and logs its status."""
        status_data = {
            "timestamp": time.time(),
            "subsystem": name,
            "status": "UNRESPONSIVE",
            "url": url,
            "details": "Request timed out or failed."
        }
        try:
            response = await client.get(url, timeout=20.0)
            if response.status_code == 200:
                status_data["status"] = "ALIVE"
                status_data["details"] = "Health check successful."
            else:
                status_data["details"] = f"Received non-200 status: {response.status_code}"
        except httpx.RequestError as e:
            status_data["details"] = f"Request failed: {str(e)}"
        
        # Log the status to the sync log
        with open(self.sync_log_path, "a") as f:
            f.write(json.dumps(status_data) + "\n")

        if status_data["status"] != "ALIVE":
            print(f"ALERT: Subsystem '{name}' is {status_data['status']}.")
        else:
            print(f"INFO: Subsystem '{name}' is ALIVE.")

    async def start_system_check_loop(self):
        """The main background loop that runs all health checks periodically."""
        interval = self.config.heartbeat_interval_seconds
        print(f"Heartbeat loop starting. Check interval: {interval} seconds.")

        async with httpx.AsyncClient() as client:
            while True:
                # 1. Log self status
                self_status = self._get_self_status()
                # (Optional) You could log this to a file if desired
                # print(f"Self-check: Memory usage is {self_status['memory_percent']}%")

                # 2. Check external services (temporarily disabled to prevent recovery mode)
                # await self._check_subsystem_health("TELEGRAM_BOT", self.config.bot_health_url, client)
                # await self._check_subsystem_health("TRADING_CORE", self.config.core_health_url, client)
                print("INFO: External health checks temporarily disabled")
                
                # 3. Wait for the next cycle
                await asyncio.sleep(interval)
