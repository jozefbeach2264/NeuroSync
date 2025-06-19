"""
NeuroSync Sync Manager
Handles timestamp validation and state consistency checking
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any


class SyncManager:
    """Manages synchronization and timestamp validation"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Sync state
        self.running = False
        self.sync_tolerance = config.SYNC_TOLERANCE
        self.reference_time = None
        self.time_offset = 0.0
        
        # Sync history for analysis
        self.sync_history = []
        self.max_history = 100
        
        # State consistency tracking
        self.state_checksums = {}
        self.state_versions = {}
        
        # Sync metrics
        self.metrics = {
            'sync_checks': 0,
            'sync_failures': 0,
            'drift_corrections': 0,
            'avg_drift': 0.0,
            'max_drift': 0.0,
            'last_sync_check': None
        }
        
        # Periodic sync task
        self.sync_task = None
    
    async def validate_timestamp(self, timestamp_str: str) -> Dict[str, Any]:
        """Validate timestamp against system time and sync state"""
        try:
            # Parse timestamp
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            
            received_time = datetime.fromisoformat(timestamp_str)
            current_time = datetime.now(timezone.utc)
            
            # Calculate drift
            drift = abs((received_time - current_time).total_seconds())
            
            # Update metrics
            self.metrics['sync_checks'] += 1
            self.metrics['avg_drift'] = (self.metrics['avg_drift'] + drift) / 2
            self.metrics['max_drift'] = max(self.metrics['max_drift'], drift)
            self.metrics['last_sync_check'] = current_time.isoformat()
            
            # Determine sync status
            is_synchronized = drift <= self.sync_tolerance
            
            if not is_synchronized:
                self.metrics['sync_failures'] += 1
                self.logger.warning(f"Timestamp drift detected: {drift}s > {self.sync_tolerance}s")
            
            # Record sync event
            sync_event = {
                'timestamp': current_time.isoformat(),
                'received_timestamp': timestamp_str,
                'drift': drift,
                'synchronized': is_synchronized,
                'tolerance': self.sync_tolerance
            }
            
            self._add_sync_history(sync_event)
            
            return {
                'valid': True,
                'synchronized': is_synchronized,
                'drift': drift,
                'tolerance': self.sync_tolerance,
                'corrected_time': current_time.isoformat(),
                'sync_status': 'synchronized' if is_synchronized else 'drift_detected'
            }
            
        except Exception as e:
            self.logger.error(f"Timestamp validation failed: {e}")
            self.metrics['sync_failures'] += 1
            
            return {
                'valid': False,
                'error': str(e),
                'synchronized': False,
                'sync_status': 'validation_error'
            }
    
    def _add_sync_history(self, sync_event: Dict[str, Any]):
        """Add sync event to history with size limit"""
        self.sync_history.append(sync_event)
        
        # Maintain history size limit
        if len(self.sync_history) > self.max_history:
            self.sync_history = self.sync_history[-self.max_history:]
    
    async def check_state_consistency(self, component: str, state_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check state consistency for a component"""
        try:
            # Generate checksum for state data
            state_json = json.dumps(state_data, sort_keys=True)
            current_checksum = hash(state_json)
            
            # Get previous state info
            previous_checksum = self.state_checksums.get(component)
            previous_version = self.state_versions.get(component, 0)
            
            # Update state tracking
            self.state_checksums[component] = current_checksum
            self.state_versions[component] = previous_version + 1
            
            # Determine consistency
            is_consistent = True
            consistency_info = {
                'component': component,
                'current_version': self.state_versions[component],
                'checksum': current_checksum,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            if previous_checksum is not None:
                # Check if state changed unexpectedly
                state_changed = current_checksum != previous_checksum
                consistency_info['state_changed'] = state_changed
                consistency_info['previous_checksum'] = previous_checksum
                
                # Log state changes
                if state_changed:
                    self.logger.info(f"State change detected for {component}")
            
            consistency_info['consistent'] = is_consistent
            
            return consistency_info
            
        except Exception as e:
            self.logger.error(f"State consistency check failed for {component}: {e}")
            return {
                'component': component,
                'consistent': False,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    async def perform_time_sync(self) -> Dict[str, Any]:
        """Perform time synchronization check and correction"""
        try:
            self.logger.debug("Performing time synchronization check")
            
            # Get current system time
            system_time = datetime.now(timezone.utc)
            
            # If we have a reference time, calculate offset
            if self.reference_time:
                time_diff = (system_time - self.reference_time).total_seconds()
                
                # Check if correction is needed
                if abs(time_diff) > self.sync_tolerance:
                    self.logger.warning(f"Time drift detected: {time_diff}s")
                    self.time_offset = time_diff
                    self.metrics['drift_corrections'] += 1
                    
                    sync_result = {
                        'corrected': True,
                        'drift': time_diff,
                        'offset': self.time_offset,
                        'reference_time': self.reference_time.isoformat(),
                        'corrected_time': system_time.isoformat()
                    }
                else:
                    sync_result = {
                        'corrected': False,
                        'drift': time_diff,
                        'within_tolerance': True
                    }
            else:
                # First sync - establish reference
                self.reference_time = system_time
                sync_result = {
                    'corrected': False,
                    'reference_established': True,
                    'reference_time': system_time.isoformat()
                }
            
            sync_result['timestamp'] = system_time.isoformat()
            sync_result['synchronized'] = True
            
            return sync_result
            
        except Exception as e:
            self.logger.error(f"Time sync failed: {e}")
            return {
                'synchronized': False,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def get_corrected_time(self) -> datetime:
        """Get time corrected for detected offset"""
        current_time = datetime.now(timezone.utc)
        if self.time_offset != 0:
            corrected_time = current_time - timedelta(seconds=self.time_offset)
            return corrected_time
        return current_time
    
    def is_synchronized(self) -> bool:
        """Check if system is currently synchronized"""
        if not self.sync_history:
            return False
        
        # Check recent sync events
        recent_events = self.sync_history[-5:]  # Last 5 events
        synchronized_count = sum(1 for event in recent_events if event.get('synchronized', False))
        
        # Consider synchronized if majority of recent events are synchronized
        return synchronized_count >= len(recent_events) / 2
    
    async def sync_check_loop(self):
        """Periodic synchronization check loop"""
        self.logger.info("Starting sync check loop")
        
        while self.running:
            try:
                # Perform time sync
                sync_result = await self.perform_time_sync()
                
                if not sync_result.get('synchronized', False):
                    self.logger.error("Time synchronization failed")
                
                # Wait for next check
                await asyncio.sleep(self.config.HEARTBEAT_INTERVAL)
                
            except asyncio.CancelledError:
                self.logger.info("Sync check loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in sync check loop: {e}")
                await asyncio.sleep(10)  # Wait before retry
    
    async def start(self):
        """Start the sync manager"""
        if self.running:
            self.logger.warning("Sync manager already running")
            return
        
        self.running = True
        self.logger.info("Starting sync manager")
        
        # Initialize reference time
        self.reference_time = datetime.now(timezone.utc)
        
        # Start sync check loop
        self.sync_task = asyncio.create_task(self.sync_check_loop())
        
        self.logger.info("Sync manager started")
    
    async def stop(self):
        """Stop the sync manager"""
        if not self.running:
            return
        
        self.logger.info("Stopping sync manager")
        self.running = False
        
        # Cancel sync task
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Sync manager stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current sync manager status"""
        return {
            'running': self.running,
            'synchronized': self.is_synchronized(),
            'reference_time': self.reference_time.isoformat() if self.reference_time else None,
            'time_offset': self.time_offset,
            'sync_tolerance': self.sync_tolerance,
            'metrics': self.metrics.copy(),
            'recent_sync_history': self.sync_history[-10:],  # Last 10 events
            'tracked_components': list(self.state_checksums.keys())
        }
    
    def get_drift_analysis(self) -> Dict[str, Any]:
        """Get detailed drift analysis"""
        if not self.sync_history:
            return {'analysis': 'No sync history available'}
        
        # Analyze drift patterns
        recent_drifts = [event.get('drift', 0) for event in self.sync_history[-20:]]
        
        analysis = {
            'total_sync_checks': len(self.sync_history),
            'recent_avg_drift': sum(recent_drifts) / len(recent_drifts) if recent_drifts else 0,
            'recent_max_drift': max(recent_drifts) if recent_drifts else 0,
            'sync_failure_rate': (
                self.metrics['sync_failures'] / max(self.metrics['sync_checks'], 1) * 100
            ),
            'drift_trend': self._analyze_drift_trend(),
            'recommendation': self._get_sync_recommendation()
        }
        
        return analysis
    
    def _analyze_drift_trend(self) -> str:
        """Analyze drift trend from recent history"""
        if len(self.sync_history) < 5:
            return "insufficient_data"
        
        recent_drifts = [event.get('drift', 0) for event in self.sync_history[-10:]]
        early_avg = sum(recent_drifts[:5]) / 5
        late_avg = sum(recent_drifts[5:]) / 5
        
        if late_avg > early_avg * 1.2:
            return "increasing"
        elif late_avg < early_avg * 0.8:
            return "decreasing"
        else:
            return "stable"
    
    def _get_sync_recommendation(self) -> str:
        """Get recommendation based on sync analysis"""
        failure_rate = self.metrics['sync_failures'] / max(self.metrics['sync_checks'], 1) * 100
        
        if failure_rate > 50:
            return "critical_sync_issues_check_time_source"
        elif failure_rate > 20:
            return "frequent_sync_failures_monitor_closely"
        elif self.metrics['max_drift'] > self.sync_tolerance * 2:
            return "large_drift_detected_investigate_time_source"
        else:
            return "sync_operating_normally"
