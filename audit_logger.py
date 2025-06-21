"""
NeuroSync Audit Logger
Comprehensive audit logging system with log rotation and retention
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Dict, Any, List, Optional, Union
from enum import Enum
import gzip
import shutil


class LogLevel(Enum):
    """Log level enumeration"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AuditEventType(Enum):
    """Types of audit events"""
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    COMMAND_EXECUTED = "command_executed"
    COMMAND_FAILED = "command_failed"
    SYNC_EVENT = "sync_event"
    HEARTBEAT_EVENT = "heartbeat_event"
    FAILSAFE_TRIGGERED = "failsafe_triggered"
    USER_ACTION = "user_action"
    AUTHENTICATION = "authentication"
    CONFIGURATION_CHANGE = "configuration_change"
    ERROR_EVENT = "error_event"
    SECURITY_EVENT = "security_event"


class AuditEvent:
    """Audit event object"""
    
    def __init__(self, event_type: AuditEventType, message: str, 
                 component: str = "system", user: Optional[str] = None,
                 metadata: Dict[str, Any] = None, level: LogLevel = LogLevel.INFO):
        self.event_id = f"audit_{int(datetime.now().timestamp() * 1000)}"
        self.event_type = event_type
        self.message = message
        self.component = component
        self.user = user
        self.metadata = metadata or {}
        self.level = level
        self.timestamp = datetime.now(timezone.utc)
        self.session_id = None
        self.ip_address = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit event to dictionary"""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'message': self.message,
            'component': self.component,
            'user': self.user,
            'metadata': self.metadata,
            'level': self.level.value,
            'timestamp': self.timestamp.isoformat(),
            'session_id': self.session_id,
            'ip_address': self.ip_address
        }
    
    def to_json(self) -> str:
        """Convert audit event to JSON string"""
        return json.dumps(self.to_dict(), separators=(',', ':'))


class AuditLogger:
    """Comprehensive audit logging system"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger('neurosync.audit')
        
        # Audit state
        self.running = False
        self.log_dir = Path(config.log_dir)
        self.audit_log_file = self.log_dir / 'audit.log'
        self.json_log_file = self.log_dir / 'audit.json'
        
        # Event buffer for async processing
        self.event_queue = asyncio.Queue()
        self.event_buffer = []
        self.buffer_size = 100
        
        # Metrics
        self.metrics = {
            'events_logged': 0,
            'events_failed': 0,
            'files_rotated': 0,
            'files_compressed': 0,
            'files_cleaned': 0
        }
        
        # Tasks
        self.processing_task = None
        self.rotation_task = None
        self.cleanup_task = None
        
        # Setup logging
        self._setup_loggers()
    
    def _setup_loggers(self):
        """Setup audit loggers with rotation"""
        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup formatted text logger
        self.text_logger = logging.getLogger('neurosync.audit.text')
        self.text_logger.setLevel(logging.DEBUG)
        
        # Rotating file handler for text logs
        text_handler = RotatingFileHandler(
            self.audit_log_file,
            maxBytes=self.config.log_rotation_size,
            backupCount=self.config.log_rotation_count
        )
        
        # Custom formatter for audit logs
        audit_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(component)-15s | %(user)-10s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S UTC'
        )
        text_handler.setFormatter(audit_formatter)
        self.text_logger.addHandler(text_handler)
        
        # Setup JSON logger
        self.json_logger = logging.getLogger('neurosync.audit.json')
        self.json_logger.setLevel(logging.DEBUG)
        
        # Rotating file handler for JSON logs
        json_handler = RotatingFileHandler(
            self.json_log_file,
            maxBytes=self.config.log_rotation_size,
            backupCount=self.config.log_rotation_count
        )
        
        # JSON formatter
        json_formatter = logging.Formatter('%(message)s')
        json_handler.setFormatter(json_formatter)
        self.json_logger.addHandler(json_handler)
        
        self.logger.info("Audit loggers configured")
    
    async def log_event(self, event_type: Union[AuditEventType, str], 
                       message: str, component: str = "system", 
                       user: Optional[str] = None, metadata: Dict[str, Any] = None,
                       level: LogLevel = LogLevel.INFO):
        """Log an audit event"""
        try:
            # Convert string to enum if needed
            if isinstance(event_type, str):
                try:
                    event_type = AuditEventType(event_type)
                except ValueError:
                    event_type = AuditEventType.ERROR_EVENT
                    metadata = metadata or {}
                    metadata['original_event_type'] = event_type
            
            # Create audit event
            event = AuditEvent(event_type, message, component, user, metadata, level)
            
            # Queue event for processing
            await self.event_queue.put(event)
            
        except Exception as e:
            self.logger.error(f"Failed to queue audit event: {e}")
            self.metrics['events_failed'] += 1
    
    async def log_system_start(self, version: str = "unknown", user: str = "system"):
        """Log system start event"""
        await self.log_event(
            AuditEventType.SYSTEM_START,
            f"NeuroSync system started (version: {version})",
            "system",
            user,
            {"version": version, "startup_time": datetime.now(timezone.utc).isoformat()}
        )
    
    async def log_system_stop(self, reason: str = "normal_shutdown", user: str = "system"):
        """Log system stop event"""
        await self.log_event(
            AuditEventType.SYSTEM_STOP,
            f"NeuroSync system stopped: {reason}",
            "system",
            user,
            {"reason": reason, "shutdown_time": datetime.now(timezone.utc).isoformat()}
        )
    
    async def log_command(self, command_type: str, target: str, success: bool, 
                         user: str = "system", metadata: Dict[str, Any] = None):
        """Log command execution"""
        event_type = AuditEventType.COMMAND_EXECUTED if success else AuditEventType.COMMAND_FAILED
        status = "executed" if success else "failed"
        
        await self.log_event(
            event_type,
            f"Command {status}: {command_type} -> {target}",
            "command_router",
            user,
            {
                "command_type": command_type,
                "target": target,
                "success": success,
                **(metadata or {})
            },
            LogLevel.INFO if success else LogLevel.ERROR
        )
    
    async def log_sync_event(self, sync_type: str, success: bool, 
                           metadata: Dict[str, Any] = None):
        """Log synchronization event"""
        status = "successful" if success else "failed"
        
        await self.log_event(
            AuditEventType.SYNC_EVENT,
            f"Sync {status}: {sync_type}",
            "sync_manager",
            None,
            {
                "sync_type": sync_type,
                "success": success,
                **(metadata or {})
            },
            LogLevel.INFO if success else LogLevel.WARNING
        )
    
    async def log_heartbeat(self, heartbeat_id: int, success: bool, 
                           metadata: Dict[str, Any] = None):
        """Log heartbeat event"""
        status = "sent" if success else "failed"
        
        await self.log_event(
            AuditEventType.HEARTBEAT_EVENT,
            f"Heartbeat {status}: #{heartbeat_id}",
            "heartbeat",
            None,
            {
                "heartbeat_id": heartbeat_id,
                "success": success,
                **(metadata or {})
            },
            LogLevel.DEBUG if success else LogLevel.WARNING
        )
    
    async def log_failsafe_event(self, condition: str, level: str, action: str,
                               metadata: Dict[str, Any] = None):
        """Log failsafe event"""
        await self.log_event(
            AuditEventType.FAILSAFE_TRIGGERED,
            f"Failsafe triggered: {condition} ({level}) -> {action}",
            "failsafe_monitor",
            None,
            {
                "condition": condition,
                "failsafe_level": level,
                "action": action,
                **(metadata or {})
            },
            LogLevel.CRITICAL
        )
    
    async def log_user_action(self, action: str, user: str, success: bool,
                            ip_address: str = None, metadata: Dict[str, Any] = None):
        """Log user action"""
        status = "completed" if success else "failed"
        
        event = await self._create_event(
            AuditEventType.USER_ACTION,
            f"User action {status}: {action}",
            "interface",
            user,
            {
                "action": action,
                "success": success,
                **(metadata or {})
            },
            LogLevel.INFO if success else LogLevel.WARNING
        )
        
        if ip_address:
            event.ip_address = ip_address
        
        await self.event_queue.put(event)
    
    async def log_authentication(self, user: str, success: bool, method: str = "unknown",
                               ip_address: str = None, metadata: Dict[str, Any] = None):
        """Log authentication event"""
        status = "successful" if success else "failed"
        
        event = await self._create_event(
            AuditEventType.AUTHENTICATION,
            f"Authentication {status}: {user} ({method})",
            "auth",
            user,
            {
                "method": method,
                "success": success,
                **(metadata or {})
            },
            LogLevel.INFO if success else LogLevel.ERROR
        )
        
        if ip_address:
            event.ip_address = ip_address
        
        await self.event_queue.put(event)
    
    async def log_security_event(self, event_description: str, severity: str = "medium",
                               user: str = None, ip_address: str = None,
                               metadata: Dict[str, Any] = None):
        """Log security event"""
        level_map = {
            "low": LogLevel.INFO,
            "medium": LogLevel.WARNING,
            "high": LogLevel.ERROR,
            "critical": LogLevel.CRITICAL
        }
        
        event = await self._create_event(
            AuditEventType.SECURITY_EVENT,
            f"Security event ({severity}): {event_description}",
            "security",
            user,
            {
                "severity": severity,
                **(metadata or {})
            },
            level_map.get(severity, LogLevel.WARNING)
        )
        
        if ip_address:
            event.ip_address = ip_address
        
        await self.event_queue.put(event)
    
    async def _create_event(self, event_type: AuditEventType, message: str,
                          component: str, user: str, metadata: Dict[str, Any],
                          level: LogLevel) -> AuditEvent:
        """Create audit event"""
        return AuditEvent(event_type, message, component, user, metadata, level)
    
    async def process_events(self):
        """Process queued audit events"""
        self.logger.info("Starting audit event processing")
        
        while self.running:
            try:
                # Get event from queue
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                
                # Add to buffer
                self.event_buffer.append(event)
                
                # Process buffer if full or timeout
                if len(self.event_buffer) >= self.buffer_size:
                    await self._flush_buffer()
                
                self.event_queue.task_done()
                
            except asyncio.TimeoutError:
                # Flush buffer periodically even if not full
                if self.event_buffer:
                    await self._flush_buffer()
                continue
            except asyncio.CancelledError:
                self.logger.info("Audit event processing cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in audit event processing: {e}")
                await asyncio.sleep(1)
        
        # Flush remaining events
        if self.event_buffer:
            await self._flush_buffer()
    
    async def _flush_buffer(self):
        """Flush event buffer to log files"""
        if not self.event_buffer:
            return
        
        try:
            for event in self.event_buffer:
                # Log to text file
                extra = {
                    'component': event.component or 'unknown',
                    'user': event.user or 'system'
                }
                
                if event.level == LogLevel.DEBUG:
                    self.text_logger.debug(event.message, extra=extra)
                elif event.level == LogLevel.INFO:
                    self.text_logger.info(event.message, extra=extra)
                elif event.level == LogLevel.WARNING:
                    self.text_logger.warning(event.message, extra=extra)
                elif event.level == LogLevel.ERROR:
                    self.text_logger.error(event.message, extra=extra)
                elif event.level == LogLevel.CRITICAL:
                    self.text_logger.critical(event.message, extra=extra)
                
                # Log to JSON file
                self.json_logger.info(event.to_json())
                
                self.metrics['events_logged'] += 1
            
            self.event_buffer.clear()
            
        except Exception as e:
            self.logger.error(f"Failed to flush audit buffer: {e}")
            self.metrics['events_failed'] += len(self.event_buffer)
            self.event_buffer.clear()
    
    async def rotate_logs(self):
        """Manual log rotation and compression"""
        try:
            # Rotate text logs
            for handler in self.text_logger.handlers:
                if isinstance(handler, RotatingFileHandler):
                    handler.doRollover()
            
            # Rotate JSON logs
            for handler in self.json_logger.handlers:
                if isinstance(handler, RotatingFileHandler):
                    handler.doRollover()
            
            self.metrics['files_rotated'] += 1
            
            # Compress old log files
            await self._compress_old_logs()
            
            self.logger.info("Log rotation completed")
            
        except Exception as e:
            self.logger.error(f"Log rotation failed: {e}")
    
    async def _compress_old_logs(self):
        """Compress old log files"""
        try:
            log_patterns = ['audit.log.*', 'audit.json.*']
            
            for pattern in log_patterns:
                for log_file in self.log_dir.glob(pattern):
                    if log_file.suffix == '.gz':
                        continue  # Already compressed
                    
                    compressed_file = log_file.with_suffix(log_file.suffix + '.gz')
                    
                    with open(log_file, 'rb') as f_in:
                        with gzip.open(compressed_file, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    
                    log_file.unlink()  # Remove original
                    self.metrics['files_compressed'] += 1
            
        except Exception as e:
            self.logger.error(f"Log compression failed: {e}")
    
    async def cleanup_old_logs(self):
        """Clean up old log files based on retention policy"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.config.AUDIT_LOG_RETENTION_DAYS)
            
            log_patterns = ['audit.log.*', 'audit.json.*']
            
            for pattern in log_patterns:
                for log_file in self.log_dir.glob(pattern):
                    if log_file.stat().st_mtime < cutoff_date.timestamp():
                        log_file.unlink()
                        self.metrics['files_cleaned'] += 1
                        self.logger.info(f"Cleaned up old log file: {log_file.name}")
            
        except Exception as e:
            self.logger.error(f"Log cleanup failed: {e}")
    
    async def maintenance_loop(self):
        """Periodic maintenance tasks"""
        self.logger.info("Starting audit log maintenance loop")
        
        while self.running:
            try:
                # Daily maintenance
                await asyncio.sleep(24 * 3600)  # 24 hours
                
                if not self.running:
                    break
                
                # Perform maintenance
                await self._compress_old_logs()
                await self.cleanup_old_logs()
                
            except asyncio.CancelledError:
                self.logger.info("Audit maintenance loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in maintenance loop: {e}")
                await asyncio.sleep(3600)  # Wait an hour before retry
    
    async def search_events(self, event_type: Optional[str] = None,
                          component: Optional[str] = None, user: Optional[str] = None,
                          start_time: Optional[datetime] = None,
                          end_time: Optional[datetime] = None,
                          limit: int = 1000) -> List[Dict[str, Any]]:
        """Search audit events (simplified file-based search)"""
        try:
            events = []
            
            # Read JSON log file
            if self.json_log_file.exists():
                with open(self.json_log_file, 'r') as f:
                    for line in f:
                        try:
                            event_data = json.loads(line.strip())
                            
                            # Apply filters
                            if event_type and event_data.get('event_type') != event_type:
                                continue
                            
                            if component and event_data.get('component') != component:
                                continue
                            
                            if user and event_data.get('user') != user:
                                continue
                            
                            if start_time:
                                event_time = datetime.fromisoformat(event_data['timestamp'])
                                if event_time < start_time:
                                    continue
                            
                            if end_time:
                                event_time = datetime.fromisoformat(event_data['timestamp'])
                                if event_time > end_time:
                                    continue
                            
                            events.append(event_data)
                            
                            if len(events) >= limit:
                                break
                                
                        except (json.JSONDecodeError, KeyError):
                            continue
            
            return events[-limit:]  # Return most recent events
            
        except Exception as e:
            self.logger.error(f"Event search failed: {e}")
            return []
    
    async def start(self):
        """Start the audit logger"""
        if self.running:
            self.logger.warning("Audit logger already running")
            return
        
        self.running = True
        self.logger.info("Starting audit logger")
        
        # Start processing tasks
        self.processing_task = asyncio.create_task(self.process_events())
        self.rotation_task = asyncio.create_task(self.maintenance_loop())
        
        # Log system start
        await self.log_system_start("1.0.0", "system")
        
        self.logger.info("Audit logger started")
    
    async def stop(self):
        """Stop the audit logger"""
        if not self.running:
            return
        
        self.logger.info("Stopping audit logger")
        
        # Log system stop
        await self.log_system_stop("normal_shutdown", "system")
        
        self.running = False
        
        # Cancel tasks
        tasks = [self.processing_task, self.rotation_task]
        for task in tasks:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Final flush
        if self.event_buffer:
            await self._flush_buffer()
        
        self.logger.info("Audit logger stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get audit logger status"""
        return {
            'running': self.running,
            'log_dir': str(self.log_dir),
            'audit_log_file': str(self.audit_log_file),
            'json_log_file': str(self.json_log_file),
            'queue_size': self.event_queue.qsize(),
            'buffer_size': len(self.event_buffer),
            'metrics': self.metrics.copy(),
            'log_files': [
                {
                    'file': f.name,
                    'size': f.stat().st_size,
                    'modified': datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                }
                for f in self.log_dir.glob('audit.*')
                if f.is_file()
            ]
        }
