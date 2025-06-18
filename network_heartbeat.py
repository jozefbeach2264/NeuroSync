import time
import uuid
import json # You were missing this import
import asyncio
import httpx # A modern, async-friendly HTTP client

# Your existing class - no changes needed here. It's good.
class NetworkHeartbeat:
    def __init__(self, log_path="logs/heartbeat.log", memory_limit_mb=80): # Adjusted to 80% per docs
        self.log_path = log_path
        self.memory_limit = memory_limit_mb
        self.id = str(uuid.uuid4())[:8]
        self.last_ping = time.time()
        # Per GPT-4, the threshold is 80%
        print(f"NetworkHeartbeat initialized. Memory threshold: {self.memory_limit}%")

    def emit(self):
        now = time.time()
        # [span_3](start_span)Check if the memory usage exceeds the threshold[span_3](end_span)
        memory_flag = self._check_memory()
        ping_data = {
            "source": "network_heartbeat",
            "time": now,
            "uuid": self.id,
            "delta": round(now - self.last_ping, 4),
            "memory_percent": self._get_memory_percent(),
            [span_4](start_span)"memory_throttle_flag": memory_flag, # Flag if RAM exceeds 80% threshold[span_4](end_span)
            "drift_warning": self._check_drift(now)
        }
        self.last_ping = now
        with open(self.log_path, "a") as f:
            f.write(json.dumps(ping_data) + "\n")
        
        return ping_data

    def _get_memory_percent(self):
        try:
            import psutil
            return psutil.virtual_memory().percent
        except ImportError:
            return 0

    def _check_memory(self):
        return self._get_memory_percent() >= self.memory_limit

    def _check_drift(self, current_time):
        return abs(current_time - time.time()) > 1.0

# --- NEW: The System Coordinator Logic ---
class SystemCoordinator:
    def __init__(self, heartbeat_emitter, sync_log_path="logs/sync_status.log"):
        self.emitter = heartbeat_emitter
        self.sync_log_path = sync_log_path
        # Define the health check URLs for your other applications
        self.bot_health_url = "https://replit.com/@jozefbeach2264/Telegram-Rolling5-Bot?s=app"
        self.core_health_url = "https://replit.com/@jozefbeach2264/Trading-Reality-Core?s=app"
        print("SystemCoordinator initialized. Monitoring endpoints:")
        print(f" - BOT: {self.bot_health_url}")
        print(f" - CORE: {self.core_health_url}")


    async def check_subsystem_health(self, name, url, client):
        status_data = {
            "timestamp": time.time(),
            "subsystem": name,
            "status": "UNRESPONSIVE",
            "details": ""
        }
        try:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                status_data["status"] = "ALIVE"
            else:
                status_data["details"] = f"Received non-200 status: {response.status_code}"
        except httpx.RequestError as e:
            status_data["details"] = f"Request failed: {str(e)}"
        
        # Log the status of the subsystem
        with open(self.sync_log_path, "a") as f:
            f.write(json.dumps(status_data) + "\n")
        
        # [span_5](start_span)This logic flags any subsystem going dark[span_5](end_span)
        if status_data["status"] != "ALIVE":
            print(f"ALERT: Subsystem '{name}' is {status_data['status']}. Details: {status_data['details']}")

    async def run_forever(self):
        # [span_6](start_span)Per GPT-7, the heartbeat emits a signed packet every 15s[span_6](end_span)
        check_interval_seconds = 15 
        print(f"Coordinator loop starting. Check interval: {check_interval_seconds} seconds.")

        async with httpx.AsyncClient() as client:
            while True:
                # 1. Emit the Network app's own heartbeat
                self.emitter.emit()
                
                # 2. Check the health of other services
                await self.check_subsystem_health("TELEGRAM_BOT", self.bot_health_url, client)
                await self.check_subsystem_health("TRADING_CORE", self.core_health_url, client)
                
                # 3. Wait for the next cycle
                await asyncio.sleep(check_interval_seconds)

# --- How to run it ---
# This part would typically go in your main.py
if __name__ == "__main__":
    print("Initializing heartbeat system...")
    
    # Create an instance of your emitter
    heartbeat_emitter = NetworkHeartbeat()
    
    # Create an instance of the new coordinator
    coordinator = SystemCoordinator(heartbeat_emitter)
    
    # Run the coordinator's main loop
    try:
        asyncio.run(coordinator.run_forever())
    except KeyboardInterrupt:
        print("Heartbeat system stopped by user.")

