"""
NeuroSync Failsafe Monitor
Monitors system health and triggers failsafe actions
"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Callable
from enum import Enum


class FailsafeLevel(Enum):
    """Failsafe severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class FailsafeCondition(Enum):
    """Types of failsafe conditions"""
    SYNC_FAILURE = "sync_failure"
    HEARTBEAT_FAILURE = "heartbeat_failure"
    COMPONENT_FAILURE = "component_failure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    COMMAND_FAILURE = "command_failure"
    NETWORK_FAILURE = "network_failure"
    CUSTOM = "custom"


class FailsafeEvent:
    """Failsafe event object"""
    
    def __init__(self, condition: FailsafeCondition, level: FailsafeLevel, 
                 message: str, component: str = "system", metadata: Dict[str, Any] = None):
        self.event_id = f"fs_{int(time.time() * 1000)}"
        self.condition = condition
        self.level = level
        self.message = message
        self.component = component
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc)
        self.acknowledged = False
        self.resolved = False
        self.actions_taken = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            'event_id': self.event_id,
            'condition': self.condition.value,
            'level': self.level.value,
            'message': self.message,
            'component': self.component,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat(),
            'acknowledged': self.acknowledged,
            'resolved': self.resolved,
            'actions_taken': self.actions_taken
        }


class FailsafeAction:
    """Failsafe action definition"""
    
    def __init__(self, action_id: str, name: str, handler: Callable, 
                 conditions: List[FailsafeCondition], level: FailsafeLevel):
        self.action_id = action_id
        self.name = name
        self.handler = handler
        self.conditions = conditions
        self.level = level
        self.enabled = True
        self.execution_count = 0
        self.last_executed = None


class FailsafeMonitor:
    """Monitors system health and executes failsafe actions"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Monitor state
        self.running = False
        self.components = {}
        self.halt_requested = False
        
        # Failsafe configuration
        self.conditions_config = {
            FailsafeCondition.SYNC_FAILURE: {
                'threshold': config.MAX_SYNC_FAILURES,
                'window_minutes': 10,
                'level': FailsafeLevel.CRITICAL
            },
            FailsafeCondition.HEARTBEAT_FAILURE: {
                'threshold': 3,
                'window_minutes': 5,
                'level': FailsafeLevel.CRITICAL
            },
            FailsafeCondition.COMPONENT_FAILURE: {
                'threshold': 1,
                'window_minutes': 1,
                'level': FailsafeLevel.WARNING
            },
            FailsafeCondition.COMMAND_FAILURE: {
                'threshold': config.MAX_COMMAND_FAILURES,
                'window_minutes': 15,
                'level': FailsafeLevel.WARNING
            }
        }
        
        # Event tracking
        self.events = []
        self.max_events = 1000
        self.event_counters = {}
        
        # Actions
        self.actions = {}
        self.action_history = []
        
        # Health checks
        self.health_checks = {}
        self.health_status = {}
        
        # Monitoring task
        self.monitor_task = None
        
        # Initialize default actions
        self._initialize_default_actions()
    
    def register_components(self, components: Dict[str, Any]):
        """Register system components for monitoring"""
        self.components = components
        self.logger.info(f"Registered {len(components)} components for monitoring")
        
        # Initialize health status
        for component_name in components:
            self.health_status[component_name] = {
                'healthy': True,
                'last_check': datetime.now(timezone.utc),
                'consecutive_failures': 0
            }
    
    def register_health_check(self, component: str, check_func: Callable):
        """Register a health check function for a component"""
        self.health_checks[component] = check_func
        self.logger.info(f"Registered health check for component: {component}")
    
    def register_action(self, action: FailsafeAction):
        """Register a failsafe action"""
        self.actions[action.action_id] = action
        self.logger.info(f"Registered failsafe action: {action.action_id} ({action.name})")
    
    def _initialize_default_actions(self):
        """Initialize default failsafe actions"""
        
        # Component restart action
        restart_action = FailsafeAction(
            'restart_component',
            'Restart Failed Component',
            self._action_restart_component,
            [FailsafeCondition.COMPONENT_FAILURE],
            FailsafeLevel.WARNING
        )
        self.register_action(restart_action)
        
        # System halt action
        halt_action = FailsafeAction(
            'system_halt',
            'Emergency System Halt',
            self._action_system_halt,
            [FailsafeCondition.SYNC_FAILURE, FailsafeCondition.HEARTBEAT_FAILURE],
            FailsafeLevel.EMERGENCY
        )
        self.register_action(halt_action)
        
        # Alert action
        alert_action = FailsafeAction(
            'send_alert',
            'Send Alert Notification',
            self._action_send_alert,
            list(FailsafeCondition),  # All conditions
            FailsafeLevel.INFO
        )
        self.register_action(alert_action)
        
        # Log action
        log_action = FailsafeAction(
            'log_event',
            'Log Failsafe Event',
            self._action_log_event,
            list(FailsafeCondition),  # All conditions
            FailsafeLevel.INFO
        )
        self.register_action(log_action)
    
    async def trigger_event(self, condition: FailsafeCondition, level: FailsafeLevel,
                           message: str, component: str = "system", 
                           metadata: Dict[str, Any] = None) -> str:
        """Trigger a failsafe event"""
        event = FailsafeEvent(condition, level, message, component, metadata)
        
        # Add to events list
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
        
        # Update counters
        counter_key = f"{condition.value}_{component}"
        if counter_key not in self.event_counters:
            self.event_counters[counter_key] = []
        
        self.event_counters[counter_key].append(event.timestamp)
        
        # Clean old counter entries
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
        self.event_counters[counter_key] = [
            ts for ts in self.event_counters[counter_key] if ts > cutoff_time
        ]
        
        self.logger.warning(f"Failsafe event triggered: {event.event_id} - {message}")
        
        # Execute appropriate actions
        await self._execute_actions(event)
        
        return event.event_id
    
    async def _execute_actions(self, event: FailsafeEvent):
        """Execute failsafe actions for an event"""
        executed_actions = []
        
        for action in self.actions.values():
            if not action.enabled:
                continue
            
            # Check if action applies to this condition and level
            if event.condition not in action.conditions:
                continue
            
            if event.level.value != action.level.value and action.level != FailsafeLevel.INFO:
                continue
            
            try:
                self.logger.info(f"Executing failsafe action: {action.name}")
                
                # Execute action
                if asyncio.iscoroutinefunction(action.handler):
                    result = await action.handler(event)
                else:
                    result = action.handler(event)
                
                # Record execution
                action.execution_count += 1
                action.last_executed = datetime.now(timezone.utc)
                
                executed_actions.append({
                    'action_id': action.action_id,
                    'name': action.name,
                    'result': result,
                    'executed_at': action.last_executed.isoformat()
                })
                
                # Add to action history
                self.action_history.append({
                    'event_id': event.event_id,
                    'action_id': action.action_id,
                    'executed_at': action.last_executed.isoformat(),
                    'result': result
                })
                
            except Exception as e:
                self.logger.error(f"Failsafe action failed: {action.name} - {e}")
                executed_actions.append({
                    'action_id': action.action_id,
                    'name': action.name,
                    'error': str(e),
                    'executed_at': datetime.now(timezone.utc).isoformat()
                })
        
        event.actions_taken = executed_actions
    
    async def _action_restart_component(self, event: FailsafeEvent) -> Dict[str, Any]:
        """Action: Restart failed component"""
        component_name = event.component
        
        if component_name in self.components:
            component = self.components[component_name]
            
            try:
                # Stop component
                if hasattr(component, 'stop'):
                    await component.stop()
                
                # Wait briefly
                await asyncio.sleep(2)
                
                # Start component
                if hasattr(component, 'start'):
                    await component.start()
                
                self.logger.info(f"Component {component_name} restarted")
                return {'success': True, 'component': component_name}
                
            except Exception as e:
                self.logger.error(f"Failed to restart component {component_name}: {e}")
                return {'success': False, 'error': str(e)}
        
        return {'success': False, 'error': 'Component not found'}
    
    async def _action_system_halt(self, event: FailsafeEvent) -> Dict[str, Any]:
        """Action: Emergency system halt"""
        self.logger.critical(f"EMERGENCY HALT TRIGGERED: {event.message}")
        self.halt_requested = True
        
        # Could trigger additional emergency procedures here
        # such as saving state, sending alerts, etc.
        
        return {'success': True, 'halt_requested': True}
    
    async def _action_send_alert(self, event: FailsafeEvent) -> Dict[str, Any]:
        """Action: Send alert notification"""
        try:
            # If Telegram integration is available, send alert
            if 'telegram' in self.components:
                telegram = self.components['telegram']
                if hasattr(telegram, 'send_alert'):
                    await telegram.send_alert(
                        f"🚨 Failsafe Alert\n"
                        f"Condition: {event.condition.value}\n"
                        f"Level: {event.level.value}\n"
                        f"Component: {event.component}\n"
                        f"Message: {event.message}\n"
                        f"Time: {event.timestamp.isoformat()}"
                    )
            
            return {'success': True, 'alert_sent': True}
            
        except Exception as e:
            self.logger.error(f"Failed to send alert: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _action_log_event(self, event: FailsafeEvent) -> Dict[str, Any]:
        """Action: Log failsafe event"""
        try:
            # If audit logger is available, log event
            if 'audit_logger' in self.components:
                audit_logger = self.components['audit_logger']
                if hasattr(audit_logger, 'log_event'):
                    await audit_logger.log_event('failsafe', event.to_dict())
            
            return {'success': True, 'logged': True}
            
        except Exception as e:
            self.logger.error(f"Failed to log event: {e}")
            return {'success': False, 'error': str(e)}
    
    async def check_component_health(self, component_name: str) -> bool:
        """Check health of a specific component"""
        try:
            if component_name not in self.components:
                return False
            
            component = self.components[component_name]
            
            # Use custom health check if available
            if component_name in self.health_checks:
                check_func = self.health_checks[component_name]
                if asyncio.iscoroutinefunction(check_func):
                    health_info = await check_func()
                else:
                    health_info = check_func()
                
                return health_info.get('healthy', False)
            
            # Use component's health method if available
            if hasattr(component, 'get_health_info'):
                health_info = component.get_health_info()
                return health_info.get('healthy', False)
            
            # Basic check - component exists and has running attribute
            if hasattr(component, 'running'):
                return component.running
            
            return True  # Assume healthy if no checks available
            
        except Exception as e:
            self.logger.error(f"Health check failed for {component_name}: {e}")
            return False
    
    async def monitor_system_health(self):
        """Monitor overall system health"""
        self.logger.info("Starting system health monitoring")
        
        while self.running:
            try:
                current_time = datetime.now(timezone.utc)
                
                # Check each component
                for component_name in self.components:
                    is_healthy = await self.check_component_health(component_name)
                    
                    health_status = self.health_status[component_name]
                    previous_health = health_status['healthy']
                    
                    health_status['healthy'] = is_healthy
                    health_status['last_check'] = current_time
                    
                    if is_healthy:
                        health_status['consecutive_failures'] = 0
                    else:
                        health_status['consecutive_failures'] += 1
                        
                        # Trigger failsafe event for unhealthy component
                        if health_status['consecutive_failures'] == 1:  # First failure
                            await self.trigger_event(
                                FailsafeCondition.COMPONENT_FAILURE,
                                FailsafeLevel.WARNING,
                                f"Component {component_name} health check failed",
                                component_name
                            )
                        elif health_status['consecutive_failures'] >= 3:  # Multiple failures
                            await self.trigger_event(
                                FailsafeCondition.COMPONENT_FAILURE,
                                FailsafeLevel.CRITICAL,
                                f"Component {component_name} has {health_status['consecutive_failures']} consecutive failures",
                                component_name
                            )
                
                # Check for threshold breaches
                await self._check_condition_thresholds()
                
                # Wait for next check
                await asyncio.sleep(self.config.FAILSAFE_CHECK_INTERVAL)
                
            except asyncio.CancelledError:
                self.logger.info("System health monitoring cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in health monitoring: {e}")
                await asyncio.sleep(10)
    
    async def _check_condition_thresholds(self):
        """Check if any condition thresholds have been breached"""
        current_time = datetime.now(timezone.utc)
        
        for condition, config in self.conditions_config.items():
            threshold = config['threshold']
            window_minutes = config['window_minutes']
            level = config['level']
            
            # Check event counts in time window
            cutoff_time = current_time - timedelta(minutes=window_minutes)
            
            for counter_key, timestamps in self.event_counters.items():
                if not counter_key.startswith(condition.value):
                    continue
                
                recent_events = [ts for ts in timestamps if ts > cutoff_time]
                
                if len(recent_events) >= threshold:
                    component = counter_key.split('_', 1)[1] if '_' in counter_key else 'system'
                    
                    await self.trigger_event(
                        condition,
                        level,
                        f"Threshold breach: {len(recent_events)} {condition.value} events in {window_minutes} minutes",
                        component,
                        {
                            'threshold': threshold,
                            'actual_count': len(recent_events),
                            'window_minutes': window_minutes
                        }
                    )
    
    def should_halt(self) -> bool:
        """Check if system halt has been requested"""
        return self.halt_requested
    
    def acknowledge_event(self, event_id: str) -> bool:
        """Acknowledge a failsafe event"""
        for event in self.events:
            if event.event_id == event_id:
                event.acknowledged = True
                self.logger.info(f"Failsafe event acknowledged: {event_id}")
                return True
        return False
    
    def resolve_event(self, event_id: str) -> bool:
        """Mark a failsafe event as resolved"""
        for event in self.events:
            if event.event_id == event_id:
                event.resolved = True
                self.logger.info(f"Failsafe event resolved: {event_id}")
                return True
        return False
    
    async def start(self):
        """Start the failsafe monitor"""
        if self.running:
            self.logger.warning("Failsafe monitor already running")
            return
        
        self.running = True
        self.halt_requested = False
        self.logger.info("Starting failsafe monitor")
        
        # Start monitoring task
        self.monitor_task = asyncio.create_task(self.monitor_system_health())
        
        self.logger.info("Failsafe monitor started")
    
    async def stop(self):
        """Stop the failsafe monitor"""
        if not self.running:
            return
        
        self.logger.info("Stopping failsafe monitor")
        self.running = False
        
        # Cancel monitoring task
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Failsafe monitor stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get failsafe monitor status"""
        return {
            'running': self.running,
            'halt_requested': self.halt_requested,
            'registered_components': list(self.components.keys()),
            'health_status': {
                name: {
                    'healthy': status['healthy'],
                    'consecutive_failures': status['consecutive_failures'],
                    'last_check': status['last_check'].isoformat()
                }
                for name, status in self.health_status.items()
            },
            'recent_events': [event.to_dict() for event in self.events[-10:]],
            'event_counts': {
                condition.value: len([
                    e for e in self.events[-100:] 
                    if e.condition == condition and 
                    e.timestamp > datetime.now(timezone.utc) - timedelta(hours=1)
                ])
                for condition in FailsafeCondition
            },
            'actions_available': [
                {
                    'action_id': action.action_id,
                    'name': action.name,
                    'enabled': action.enabled,
                    'execution_count': action.execution_count
                }
                for action in self.actions.values()
            ]
        }
    
    def get_event_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent failsafe event history"""
        return [event.to_dict() for event in self.events[-limit:]]
    
    def get_action_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent action execution history"""
        return self.action_history[-limit:]
