# config.py
import os
    
from dotenv import load_dotenv

        # Load environment variables from a .env file
load_dotenv()

class Config:
            """
            Manages all configuration for the NeuroSync application.
            """
            def __init__(self):
                # --- General Settings ---
                self.app_name = "NeuroSync"

                # --- Heartbeat Settings ---
                self.heartbeat_interval_seconds: int = 15
                self.bot_health_url: str = os.getenv("BOT_HEALTH_URL", "http://127.0.0.1:8001/health")
                self.core_health_url: str = os.getenv("CORE_HEALTH_URL", "http://127.0.0.1:8002/health")

                # --- Logging Settings ---
                self.LOG_DIR = "logs"
                self.audit_log_file = os.path.join(self.LOG_DIR, "audit.json")
                self.sync_log_file = os.path.join(self.LOG_DIR, "sync_status.log")

                # --- ADDED: Log Rotation Settings ---
                # Get rotation size from environment variable, default to 10MB
                self.LOG_ROTATION_SIZE = int(os.getenv('LOG_ROTATION_SIZE', '10485760'))
                # Get number of backup log files to keep, default to 5
                self.LOG_ROTATION_COUNT = int(os.getenv('LOG_ROTATION_COUNT', '5'))

                # Ensure log directory exists
                os.makedirs(self.LOG_DIR, exist_ok=True)
