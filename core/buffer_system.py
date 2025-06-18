"""
NeuroSync Buffer System
Handles sync breaks, command queuing, and data buffering
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from enum import Enum


class BufferType(Enum):
    """Types of buffer data"""
    COMMAND = "command"
    SYNC_DATA = "sync_data"
    HEARTBEAT = "heartbeat"
    EVENT = "event"
    METRIC = "metric"


class BufferEntry:
    """Buffer entry object"""
    
    def __init__(self, buffer_type: BufferType, data: Dict[str, Any], 
                 priority: int = 0, expires_at: Optional[datetime] = None):
        self.entry_id = f"buf_{int(datetime.now().timestamp() * 1000)}"
        self.buffer_type = buffer_type
        self.data = data
        self.priority = priority
        self.created_at = datetime.now(timezone.utc)
        self.expires_at = expires_at
        self.retry_count = 0
        self.max_retries = 3
        self.processed = False
        self.error = None
    
    def is_expired(self) -> bool:
        """Check if buffer entry has expired"""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert buffer entry to dictionary"""
        return {
            'entry_id': self.entry_id,
            'buffer_type': self.buffer_type.value,
            'data': self.data,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'processed': self.processed,
            'error': self.error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BufferEntry':
        """Create buffer entry from dictionary"""
        entry = cls(
            BufferType(data['buffer_type']),
            data['data'],
            data.get('priority', 0)
        )
        entry.entry_id = data['entry_id']
        entry.created_at = datetime.fromisoformat(data['created_at'])
        entry.expires_at = datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None
        entry.retry_count = data.get('retry_count', 0)
        entry.max_retries = data.get('max_retries', 3)
        entry.processed = data.get('processed', False)
        entry.error = data.get('error')
        return entry


class BufferSystem:
    """Buffer system for handling sync breaks and command queuing"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Buffer state
        self.running = False
        self.buffer_file = Path(config.BUFFER_FILE)
        self.buffer_entries = []
        self.max_buffer_size = config.BUFFER_MAX_SIZE
        
        # Processing
        self.command_router = None
        self.processing_enabled = True
        self.flush_interval = config.BUFFER_FLUSH_INTERVAL
        
        # Metrics
        self.metrics = {
            'entries_added': 0,
            'entries_processed': 0,
            'entries_failed': 0,
            'entries_expired': 0,
            'buffer_flushes': 0,
            'file_saves': 0,
            'file_loads': 0
        }
        
        # Tasks
        self.processing_task = None
        self.flush_task = None
        self.cleanup_task = None
        
        # Ensure buffer directory exists
        self.buffer_file.parent.mkdir(parents=True, exist_ok=True)
    
    def set_command_router(self, command_router):
        """Set command router for processing commands"""
        self.command_router = command_router
        self.logger.info("Command router registered with buffer system")
    
    async def add_entry(self, buffer_type: BufferType, data: Dict[str, Any], 
                       priority: int = 0, ttl_seconds: Optional[int] = None) -> str:
        """Add entry to buffer"""
        try:
            # Check buffer size limit
            if len(self.buffer_entries) >= self.max_buffer_size:
                # Remove oldest low-priority entries
                await self._cleanup_buffer()
                
                if len(self.buffer_entries) >= self.max_buffer_size:
                    raise Exception("Buffer is full")
            
            # Calculate expiration
            expires_at = None
            if ttl_seconds:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
            
            # Create buffer entry
            entry = BufferEntry(buffer_type, data, priority, expires_at)
            
            # Add to buffer
            self.buffer_entries.append(entry)
            
            # Sort by priority (higher priority first)
            self.buffer_entries.sort(key=lambda x: (-x.priority, x.created_at))
            
            self.metrics['entries_added'] += 1
            
            self.logger.debug(f"Added buffer entry: {entry.entry_id} ({buffer_type.value})")
            
            return entry.entry_id
            
        except Exception as e:
            self.logger.error(f"Failed to add buffer entry: {e}")
            raise
    
    async def add_command(self, command_type: str, target: str, payload: Dict[str, Any], 
                         priority: int = 0, ttl_seconds: int = 3600) -> str:
        """Add command to buffer"""
        command_data = {
            'command_type': command_type,
            'target': target,
            'payload': payload,
            'source': 'buffer_system'
        }
        
        return await self.add_entry(BufferType.COMMAND, command_data, priority, ttl_seconds)
    
    async def add_sync_data(self, sync_data: Dict[str, Any], priority: int = 5) -> str:
        """Add sync data to buffer"""
        return await self.add_entry(BufferType.SYNC_DATA, sync_data, priority)
    
    async def add_heartbeat(self, heartbeat_data: Dict[str, Any], priority: int = 3) -> str:
        """Add heartbeat data to buffer"""
        return await self.add_entry(BufferType.HEARTBEAT, heartbeat_data, priority, 300)  # 5 min TTL
    
    async def add_event(self, event_data: Dict[str, Any], priority: int = 2) -> str:
        """Add event data to buffer"""
        return await self.add_entry(BufferType.EVENT, event_data, priority)
    
    async def add_metric(self, metric_data: Dict[str, Any], priority: int = 1) -> str:
        """Add metric data to buffer"""
        return await self.add_entry(BufferType.METRIC, metric_data, priority, 1800)  # 30 min TTL
    
    async def process_entry(self, entry: BufferEntry) -> bool:
        """Process a single buffer entry"""
        try:
            self.logger.debug(f"Processing buffer entry: {entry.entry_id}")
            
            # Check if entry has expired
            if entry.is_expired():
                self.logger.debug(f"Buffer entry expired: {entry.entry_id}")
                self.metrics['entries_expired'] += 1
                return False
            
            # Process based on buffer type
            success = False
            
            if entry.buffer_type == BufferType.COMMAND:
                success = await self._process_command(entry)
            elif entry.buffer_type == BufferType.SYNC_DATA:
                success = await self._process_sync_data(entry)
            elif entry.buffer_type == BufferType.HEARTBEAT:
                success = await self._process_heartbeat(entry)
            elif entry.buffer_type == BufferType.EVENT:
                success = await self._process_event(entry)
            elif entry.buffer_type == BufferType.METRIC:
                success = await self._process_metric(entry)
            
            if success:
                entry.processed = True
                self.metrics['entries_processed'] += 1
                self.logger.debug(f"Buffer entry processed successfully: {entry.entry_id}")
            else:
                entry.retry_count += 1
                if entry.retry_count >= entry.max_retries:
                    self.metrics['entries_failed'] += 1
                    self.logger.error(f"Buffer entry failed after {entry.max_retries} retries: {entry.entry_id}")
                    return False
                else:
                    self.logger.warning(f"Buffer entry processing failed, will retry: {entry.entry_id}")
            
            return success
            
        except Exception as e:
            entry.error = str(e)
            entry.retry_count += 1
            self.logger.error(f"Error processing buffer entry {entry.entry_id}: {e}")
            return False
    
    async def _process_command(self, entry: BufferEntry) -> bool:
        """Process command buffer entry"""
        if not self.command_router:
            return False
        
        try:
            data = entry.data
            command_id = await self.command_router.queue_command(
                data['command_type'],
                data['target'],
                data['payload'],
                data.get('source', 'buffer_system')
            )
            
            self.logger.debug(f"Command queued from buffer: {command_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to process command from buffer: {e}")
            return False
    
    async def _process_sync_data(self, entry: BufferEntry) -> bool:
        """Process sync data buffer entry"""
        try:
            # This would integrate with sync manager
            # For now, just log the sync data
            self.logger.info(f"Processing sync data: {entry.data}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to process sync data: {e}")
            return False
    
    async def _process_heartbeat(self, entry: BufferEntry) -> bool:
        """Process heartbeat buffer entry"""
        try:
            # This would integrate with heartbeat system
            # For now, just log the heartbeat
            self.logger.debug(f"Processing heartbeat: {entry.data}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to process heartbeat: {e}")
            return False
    
    async def _process_event(self, entry: BufferEntry) -> bool:
        """Process event buffer entry"""
        try:
            # This would integrate with event system
            # For now, just log the event
            self.logger.info(f"Processing event: {entry.data}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to process event: {e}")
            return False
    
    async def _process_metric(self, entry: BufferEntry) -> bool:
        """Process metric buffer entry"""
        try:
            # This would integrate with metrics system
            # For now, just log the metric
            self.logger.debug(f"Processing metric: {entry.data}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to process metric: {e}")
            return False
    
    async def process_buffer(self):
        """Main buffer processing loop"""
        self.logger.info("Starting buffer processing loop")
        
        while self.running:
            try:
                if not self.processing_enabled:
                    await asyncio.sleep(1)
                    continue
                
                if not self.buffer_entries:
                    await asyncio.sleep(1)
                    continue
                
                # Get highest priority unprocessed entry
                entry_to_process = None
                for entry in self.buffer_entries:
                    if not entry.processed and not entry.is_expired():
                        entry_to_process = entry
                        break
                
                if entry_to_process:
                    await self.process_entry(entry_to_process)
                
                await asyncio.sleep(0.1)  # Brief pause
                
            except asyncio.CancelledError:
                self.logger.info("Buffer processing loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in buffer processing loop: {e}")
                await asyncio.sleep(5)
    
    async def _cleanup_buffer(self):
        """Clean up processed and expired entries"""
        initial_count = len(self.buffer_entries)
        
        # Remove processed entries
        self.buffer_entries = [
            entry for entry in self.buffer_entries 
            if not entry.processed and not entry.is_expired()
        ]
        
        # If still too full, remove oldest low-priority entries
        if len(self.buffer_entries) >= self.max_buffer_size * 0.9:
            # Sort by priority and age, keep highest priority and newest
            self.buffer_entries.sort(key=lambda x: (-x.priority, -x.created_at.timestamp()))
            self.buffer_entries = self.buffer_entries[:int(self.max_buffer_size * 0.8)]
        
        cleaned_count = initial_count - len(self.buffer_entries)
        if cleaned_count > 0:
            self.logger.info(f"Cleaned up {cleaned_count} buffer entries")
    
    async def cleanup_loop(self):
        """Periodic cleanup loop"""
        self.logger.info("Starting buffer cleanup loop")
        
        while self.running:
            try:
                await self._cleanup_buffer()
                await asyncio.sleep(60)  # Cleanup every minute
                
            except asyncio.CancelledError:
                self.logger.info("Buffer cleanup loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)
    
    async def save_to_file(self):
        """Save buffer to file"""
        try:
            buffer_data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'entries': [entry.to_dict() for entry in self.buffer_entries],
                'metrics': self.metrics.copy()
            }
            
            # Write to temporary file first
            temp_file = self.buffer_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(buffer_data, f, indent=2)
            
            # Atomic move
            temp_file.replace(self.buffer_file)
            
            self.metrics['file_saves'] += 1
            self.logger.debug(f"Buffer saved to file: {self.buffer_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save buffer to file: {e}")
    
    async def load_from_file(self):
        """Load buffer from file"""
        try:
            if not self.buffer_file.exists():
                self.logger.info("No buffer file found, starting with empty buffer")
                return
            
            with open(self.buffer_file, 'r') as f:
                buffer_data = json.load(f)
            
            # Restore entries
            self.buffer_entries = []
            for entry_data in buffer_data.get('entries', []):
                try:
                    entry = BufferEntry.from_dict(entry_data)
                    # Skip expired entries
                    if not entry.is_expired():
                        self.buffer_entries.append(entry)
                except Exception as e:
                    self.logger.warning(f"Failed to restore buffer entry: {e}")
            
            # Restore metrics
            saved_metrics = buffer_data.get('metrics', {})
            for key, value in saved_metrics.items():
                if key in self.metrics:
                    self.metrics[key] = value
            
            self.metrics['file_loads'] += 1
            
            self.logger.info(f"Loaded {len(self.buffer_entries)} entries from buffer file")
            
        except Exception as e:
            self.logger.error(f"Failed to load buffer from file: {e}")
    
    async def flush_buffer(self):
        """Flush buffer - save to file and optionally clear processed entries"""
        try:
            await self.save_to_file()
            await self._cleanup_buffer()
            
            self.metrics['buffer_flushes'] += 1
            self.logger.debug("Buffer flushed")
            
        except Exception as e:
            self.logger.error(f"Failed to flush buffer: {e}")
    
    async def flush_loop(self):
        """Periodic flush loop"""
        self.logger.info("Starting buffer flush loop")
        
        while self.running:
            try:
                await self.flush_buffer()
                await asyncio.sleep(self.flush_interval)
                
            except asyncio.CancelledError:
                self.logger.info("Buffer flush loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in flush loop: {e}")
                await asyncio.sleep(self.flush_interval)
    
    def enable_processing(self):
        """Enable buffer processing"""
        self.processing_enabled = True
        self.logger.info("Buffer processing enabled")
    
    def disable_processing(self):
        """Disable buffer processing"""
        self.processing_enabled = False
        self.logger.info("Buffer processing disabled")
    
    def clear_buffer(self):
        """Clear all buffer entries"""
        entry_count = len(self.buffer_entries)
        self.buffer_entries.clear()
        self.logger.info(f"Cleared {entry_count} buffer entries")
    
    async def start(self):
        """Start the buffer system"""
        if self.running:
            self.logger.warning("Buffer system already running")
            return
        
        self.running = True
        self.logger.info("Starting buffer system")
        
        # Load existing buffer
        await self.load_from_file()
        
        # Start processing tasks
        self.processing_task = asyncio.create_task(self.process_buffer())
        self.flush_task = asyncio.create_task(self.flush_loop())
        self.cleanup_task = asyncio.create_task(self.cleanup_loop())
        
        self.logger.info("Buffer system started")
    
    async def stop(self):
        """Stop the buffer system"""
        if not self.running:
            return
        
        self.logger.info("Stopping buffer system")
        self.running = False
        
        # Cancel tasks
        tasks = [self.processing_task, self.flush_task, self.cleanup_task]
        for task in tasks:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Final save
        await self.save_to_file()
        
        self.logger.info("Buffer system stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get buffer system status"""
        return {
            'running': self.running,
            'processing_enabled': self.processing_enabled,
            'buffer_size': len(self.buffer_entries),
            'max_buffer_size': self.max_buffer_size,
            'buffer_file': str(self.buffer_file),
            'metrics': self.metrics.copy(),
            'entries_by_type': {
                buffer_type.value: len([
                    e for e in self.buffer_entries 
                    if e.buffer_type == buffer_type
                ])
                for buffer_type in BufferType
            },
            'entries_by_status': {
                'processed': len([e for e in self.buffer_entries if e.processed]),
                'pending': len([e for e in self.buffer_entries if not e.processed and not e.is_expired()]),
                'expired': len([e for e in self.buffer_entries if e.is_expired()]),
                'failed': len([e for e in self.buffer_entries if e.retry_count >= e.max_retries])
            }
        }
    
    def get_buffer_entries(self, buffer_type: Optional[BufferType] = None, 
                          limit: int = 100) -> List[Dict[str, Any]]:
        """Get buffer entries"""
        entries = self.buffer_entries
        
        if buffer_type:
            entries = [e for e in entries if e.buffer_type == buffer_type]
        
        return [entry.to_dict() for entry in entries[-limit:]]
