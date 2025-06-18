"""
NeuroSync Heartbeat System
Manages network heartbeat generation and monitoring
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Callable


class HeartbeatSystem:
    """Core heartbeat system for network synchronization"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Heartbeat state
        self.running = False
        self.heartbeat_count = 0
        self.last_heartbeat = None
        self.sync_manager = None
        
        # Callbacks and handlers
        self.heartbeat_callbacks = []
        self.failure_callbacks = []
        
        # Performance metrics
        self.metrics = {
            'total_heartbeats': 0,
            'failed_heartbeats': 0,
            'avg_response_time': 0.0,
            'last_sync_time': None
        }
        
        # Heartbeat task
        self.heartbeat_task = None
    
    def set_sync_manager(self, sync_manager):
        """Set the sync manager for timestamp validation"""
        self.sync_manager = sync_manager
        self.logger.info("Sync manager registered with heartbeat system")
    
    def add_heartbeat_callback(self, callback: Callable):
        """Add callback function to be called on each heartbeat"""
        self.heartbeat_callbacks.append(callback)
        self.logger.debug(f"Added heartbeat callback: {callback.__name__}")
    
    def add_failure_callback(self, callback: Callable):
        """Add callback function to be called on heartbeat failure"""
        self.failure_callbacks.append(callback)
        self.logger.debug(f"Added failure callback: {callback.__name__}")
    
    def generate_heartbeat_payload(self) -> Dict[str, Any]:
        """Generate heartbeat payload with current system state"""
        current_time = datetime.now(timezone.utc)
        
        payload = {
            'timestamp': current_time.isoformat(),
            'heartbeat_id': self.heartbeat_count,
            'system_id': 'neurosync_main',
            'status': 'active',
            'metrics': {
                'uptime': time.time() - (self.metrics.get('start_time', time.time())),
                'total_heartbeats': self.metrics['total_heartbeats'],
                'failed_heartbeats': self.metrics['failed_heartbeats'],
                'success_rate': self._calculate_success_rate()
            },
            'sync_info': {
                'last_sync': self.metrics.get('last_sync_time'),
                'sync_status': 'synchronized' if self.is_synchronized() else 'out_of_sync'
            },
            'component_status': self._get_component_status()
        }
        
        return payload
    
    def _calculate_success_rate(self) -> float:
        """Calculate heartbeat success rate"""
        total = self.metrics['total_heartbeats']
        if total == 0:
            return 100.0
        
        failed = self.metrics['failed_heartbeats']
        return ((total - failed) / total) * 100.0
    
    def _get_component_status(self) -> Dict[str, str]:
        """Get status of system components"""
        # This would be populated by component health checks
        return {
            'heartbeat': 'active',
            'sync_manager': 'active' if self.sync_manager else 'inactive',
            'command_router': 'active',  # Would be updated by actual component
            'load_balancer': 'active',   # Would be updated by actual component
        }
    
    def is_synchronized(self) -> bool:
        """Check if system is properly synchronized"""
        if not self.sync_manager:
            return False
        
        return self.sync_manager.is_synchronized()
    
    async def send_heartbeat(self) -> bool:
        """Send heartbeat and process response"""
        try:
            start_time = time.time()
            
            # Generate heartbeat payload
            payload = self.generate_heartbeat_payload()
            
            # Log heartbeat
            self.logger.debug(f"Sending heartbeat {self.heartbeat_count}: {payload}")
            
            # Validate with sync manager if available
            if self.sync_manager:
                sync_result = await self.sync_manager.validate_timestamp(
                    payload['timestamp']
                )
                payload['sync_validation'] = sync_result
            
            # Call registered callbacks
            await self._execute_heartbeat_callbacks(payload)
            
            # Update metrics
            response_time = time.time() - start_time
            self.metrics['avg_response_time'] = (
                (self.metrics['avg_response_time'] + response_time) / 2
            )
            self.metrics['total_heartbeats'] += 1
            self.metrics['last_sync_time'] = payload['timestamp']
            
            self.last_heartbeat = payload
            self.logger.info(f"Heartbeat {self.heartbeat_count} sent successfully")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send heartbeat {self.heartbeat_count}: {e}")
            self.metrics['failed_heartbeats'] += 1
            
            # Call failure callbacks
            await self._execute_failure_callbacks(e)
            
            return False
    
    async def _execute_heartbeat_callbacks(self, payload: Dict[str, Any]):
        """Execute registered heartbeat callbacks"""
        for callback in self.heartbeat_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(payload)
                else:
                    callback(payload)
            except Exception as e:
                self.logger.error(f"Heartbeat callback error: {e}")
    
    async def _execute_failure_callbacks(self, error: Exception):
        """Execute registered failure callbacks"""
        for callback in self.failure_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(error)
                else:
                    callback(error)
            except Exception as e:
                self.logger.error(f"Failure callback error: {e}")
    
    async def heartbeat_loop(self):
        """Main heartbeat loop"""
        self.logger.info("Starting heartbeat loop")
        self.metrics['start_time'] = time.time()
        
        while self.running:
            try:
                # Send heartbeat
                success = await self.send_heartbeat()
                
                if success:
                    self.heartbeat_count += 1
                
                # Wait for next heartbeat interval
                await asyncio.sleep(self.config.HEARTBEAT_INTERVAL)
                
            except asyncio.CancelledError:
                self.logger.info("Heartbeat loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(5)  # Brief pause before retry
    
    async def start(self):
        """Start the heartbeat system"""
        if self.running:
            self.logger.warning("Heartbeat system already running")
            return
        
        self.running = True
        self.heartbeat_count = 0
        self.metrics = {
            'total_heartbeats': 0,
            'failed_heartbeats': 0,
            'avg_response_time': 0.0,
            'last_sync_time': None,
            'start_time': time.time()
        }
        
        # Start heartbeat loop
        self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())
        
        self.logger.info("Heartbeat system started")
    
    async def stop(self):
        """Stop the heartbeat system"""
        if not self.running:
            return
        
        self.logger.info("Stopping heartbeat system")
        self.running = False
        
        # Cancel heartbeat task
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Heartbeat system stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current heartbeat system status"""
        return {
            'running': self.running,
            'heartbeat_count': self.heartbeat_count,
            'last_heartbeat': self.last_heartbeat,
            'metrics': self.metrics.copy(),
            'is_synchronized': self.is_synchronized(),
            'callbacks_registered': {
                'heartbeat': len(self.heartbeat_callbacks),
                'failure': len(self.failure_callbacks)
            }
        }
    
    def get_health_info(self) -> Dict[str, Any]:
        """Get health information for monitoring"""
        current_time = time.time()
        last_heartbeat_time = None
        
        if self.last_heartbeat:
            try:
                last_heartbeat_time = datetime.fromisoformat(
                    self.last_heartbeat['timestamp'].replace('Z', '+00:00')
                ).timestamp()
            except (ValueError, KeyError):
                pass
        
        time_since_last = (
            current_time - last_heartbeat_time 
            if last_heartbeat_time else None
        )
        
        is_healthy = (
            self.running and 
            time_since_last is not None and 
            time_since_last < (self.config.HEARTBEAT_TIMEOUT * 2)
        )
        
        return {
            'healthy': is_healthy,
            'running': self.running,
            'time_since_last_heartbeat': time_since_last,
            'success_rate': self._calculate_success_rate(),
            'total_heartbeats': self.metrics['total_heartbeats'],
            'failed_heartbeats': self.metrics['failed_heartbeats']
        }
