"""
NeuroSync Configuration Management
Centralized configuration for all system components
"""

import os
from pathlib import Path


class Config:
    """Configuration manager for NeuroSync system"""
    
    def __init__(self):
        self.load_config()
    
    def load_config(self):
        """Load configuration from environment variables with defaults"""
        
        # System Configuration
        self.DEBUG = self.get_bool_env('DEBUG', False)
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        self.LOG_DIR = os.getenv('LOG_DIR', 'logs')
        self.DATA_DIR = os.getenv('DATA_DIR', 'data')
        
        # Network Configuration
        self.HOST = os.getenv('HOST', '0.0.0.0')
        self.WEB_PORT = int(os.getenv('WEB_PORT', '5000'))
        self.API_PORT = int(os.getenv('API_PORT', '8000'))
        
        # Heartbeat System
        self.HEARTBEAT_INTERVAL = int(os.getenv('HEARTBEAT_INTERVAL', '30'))
        self.HEARTBEAT_TIMEOUT = int(os.getenv('HEARTBEAT_TIMEOUT', '90'))
        self.SYNC_TOLERANCE = int(os.getenv('SYNC_TOLERANCE', '5'))
        
        # Command System
        self.COMMAND_TIMEOUT = int(os.getenv('COMMAND_TIMEOUT', '60'))
        self.MAX_COMMAND_QUEUE = int(os.getenv('MAX_COMMAND_QUEUE', '100'))
        self.COMMAND_RETRY_ATTEMPTS = int(os.getenv('COMMAND_RETRY_ATTEMPTS', '3'))
        
        # Load Balancer
        self.MAX_CONCURRENT_TASKS = int(os.getenv('MAX_CONCURRENT_TASKS', '10'))
        self.TASK_TIMEOUT = int(os.getenv('TASK_TIMEOUT', '300'))
        
        # Buffer System
        self.BUFFER_MAX_SIZE = int(os.getenv('BUFFER_MAX_SIZE', '1000'))
        self.BUFFER_FLUSH_INTERVAL = int(os.getenv('BUFFER_FLUSH_INTERVAL', '60'))
        self.BUFFER_FILE = os.getenv('BUFFER_FILE', 'data/buffer.json')
        
        # Logging Configuration
        self.LOG_ROTATION_SIZE = int(os.getenv('LOG_ROTATION_SIZE', '10485760'))  # 10MB
        self.LOG_ROTATION_COUNT = int(os.getenv('LOG_ROTATION_COUNT', '5'))
        self.AUDIT_LOG_RETENTION_DAYS = int(os.getenv('AUDIT_LOG_RETENTION_DAYS', '30'))
        
        # Failsafe Configuration
        self.FAILSAFE_CHECK_INTERVAL = int(os.getenv('FAILSAFE_CHECK_INTERVAL', '10'))
        self.MAX_SYNC_FAILURES = int(os.getenv('MAX_SYNC_FAILURES', '5'))
        self.MAX_COMMAND_FAILURES = int(os.getenv('MAX_COMMAND_FAILURES', '10'))
        
        # Telegram Integration
        self.TELEGRAM_ENABLED = self.get_bool_env('TELEGRAM_ENABLED', False)
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
        self.TELEGRAM_ADMIN_IDS = self.get_list_env('TELEGRAM_ADMIN_IDS', [])
        
        # Command Filtering
        self.COMMAND_WHITELIST = self.get_list_env('COMMAND_WHITELIST', [
            'status', 'health', 'sync', 'restart', 'stop', 'start',
            'toggle_on', 'toggle_off', 'load_balance', 'failsafe'
        ])
        
        # Security
        self.REQUIRE_AUTH = self.get_bool_env('REQUIRE_AUTH', True)
        self.API_KEY = os.getenv('API_KEY', 'default_neurosync_key')
        self.MAX_LOGIN_ATTEMPTS = int(os.getenv('MAX_LOGIN_ATTEMPTS', '5'))
        
        # Ensure directories exist
        self.ensure_directories()
    
    def get_bool_env(self, key, default=False):
        """Get boolean environment variable"""
        value = os.getenv(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    def get_list_env(self, key, default=None):
        """Get list from environment variable (comma-separated)"""
        if default is None:
            default = []
        
        value = os.getenv(key, '')
        if not value:
            return default
        
        return [item.strip() for item in value.split(',') if item.strip()]
    
    def ensure_directories(self):
        """Ensure required directories exist"""
        directories = [
            self.LOG_DIR,
            self.DATA_DIR,
            os.path.dirname(self.BUFFER_FILE) if os.path.dirname(self.BUFFER_FILE) else '.'
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def get_log_config(self):
        """Get logging configuration dictionary"""
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                },
                'detailed': {
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s'
                }
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'level': self.LOG_LEVEL,
                    'formatter': 'standard',
                    'stream': 'ext://sys.stdout'
                },
                'file': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': self.LOG_LEVEL,
                    'formatter': 'detailed',
                    'filename': f'{self.LOG_DIR}/neurosync.log',
                    'maxBytes': self.LOG_ROTATION_SIZE,
                    'backupCount': self.LOG_ROTATION_COUNT
                }
            },
            'root': {
                'level': self.LOG_LEVEL,
                'handlers': ['console', 'file']
            }
        }
    
    def validate_config(self):
        """Validate configuration settings"""
        errors = []
        
        # Validate Telegram settings
        if self.TELEGRAM_ENABLED:
            if not self.TELEGRAM_BOT_TOKEN:
                errors.append("TELEGRAM_BOT_TOKEN is required when Telegram is enabled")
            if not self.TELEGRAM_CHAT_ID:
                errors.append("TELEGRAM_CHAT_ID is required when Telegram is enabled")
        
        # Validate numeric settings
        if self.HEARTBEAT_INTERVAL <= 0:
            errors.append("HEARTBEAT_INTERVAL must be positive")
        
        if self.HEARTBEAT_TIMEOUT <= self.HEARTBEAT_INTERVAL:
            errors.append("HEARTBEAT_TIMEOUT must be greater than HEARTBEAT_INTERVAL")
        
        if self.MAX_CONCURRENT_TASKS <= 0:
            errors.append("MAX_CONCURRENT_TASKS must be positive")
        
        if self.BUFFER_MAX_SIZE <= 0:
            errors.append("BUFFER_MAX_SIZE must be positive")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")
        
        return True
    
    def __str__(self):
        """String representation of configuration (excluding sensitive data)"""
        safe_config = {}
        for key, value in self.__dict__.items():
            if 'token' in key.lower() or 'key' in key.lower() or 'password' in key.lower():
                safe_config[key] = '***HIDDEN***'
            else:
                safe_config[key] = value
        
        return f"NeuroSync Config: {safe_config}"
