# NeuroSync/config.py (Corrected and Complete)
import os
from dotenv import load_dotenv

# This line loads the secrets from the .env file or Replit's Secrets tool
load_dotenv()

class Config:
    """Manages all configuration settings for the NeuroSync service."""
    def __init__(self):
        # URL for the TradingCore's health check endpoint
        self.core_health_url = os.getenv("CORE_HEALTH_URL")
        
        # URL for the Telegram Bot's health check endpoint
        self.bot_health_url = os.getenv("BOT_HEALTH_URL")
        
        # Interval in seconds for the heartbeat check
        self.heartbeat_interval_seconds = 15

        # A debug print to confirm the secrets are loaded
        print("--- NeuroSync Config Initialized ---")
        print(f"Loaded CORE_HEALTH_URL: {self.core_health_url}")
        print(f"Loaded BOT_HEALTH_URL: {self.bot_health_url}")
        print("------------------------------------")

