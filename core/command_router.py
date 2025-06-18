"""
NeuroSync Command Router
Handles command routing and execution between system components
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
from enum import Enum


class CommandStatus(Enum):
    """Command execution status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class Command:
    """Command object with metadata"""
    
    def __init__(self, command_id: str, command_type: str, target: str, 
                 payload: Dict[str, Any], source: str = "unknown"):
        self.command_id = command_id
        self.command_type = command_type
        self.target = target
        self.payload = payload
        self.source = source
        self.status = CommandStatus.PENDING
        self.created_at = datetime.now(timezone.utc)
        self.started_at = None
        self.completed_at = None
        self.result = None
        self.error = None
        self.retry_count = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert command to dictionary"""
        return {
            'command_id': self.command_id,
            'command_type': self.command_type,
            'target': self.target,
            'payload': self.payload,
            'source': self.source,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'result': self.result,
            'error': self.error,
            'retry_count': self.retry_count
        }


class CommandRouter:
    """Command routing and execution system"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Router state
        self.running = False
        self.components = {}
        self.command_handlers = {}
        
        # Command queue and processing
        self.command_queue = asyncio.Queue(maxsize=config.MAX_COMMAND_QUEUE)
        self.active_commands = {}
        self.command_history = []
        self.max_history = 1000
        
        # Routing rules
        self.routing_rules = {}
        self.default_handlers = {}
        
        # Metrics
        self.metrics = {
            'commands_processed': 0,
            'commands_failed': 0,
            'commands_timeout': 0,
            'avg_processing_time': 0.0,
            'queue_size': 0,
            'active_commands': 0
        }
        
        # Processing task
        self.processing_task = None
    
    def register_component(self, name: str, component: Any):
        """Register a component for command routing"""
        self.components[name] = component
        self.logger.info(f"Registered component: {name}")
        
        # Auto-register component methods as handlers
        self._auto_register_handlers(name, component)
    
    def _auto_register_handlers(self, component_name: str, component: Any):
        """Automatically register component methods as command handlers"""
        # Look for methods that start with 'handle_' or 'execute_'
        for attr_name in dir(component):
            if attr_name.startswith(('handle_', 'execute_')) and callable(getattr(component, attr_name)):
                method = getattr(component, attr_name)
                command_type = attr_name.replace('handle_', '').replace('execute_', '')
                handler_key = f"{component_name}.{command_type}"
                self.command_handlers[handler_key] = method
                self.logger.debug(f"Auto-registered handler: {handler_key}")
    
    def register_handler(self, command_type: str, target: str, handler: Callable):
        """Register a custom command handler"""
        handler_key = f"{target}.{command_type}"
        self.command_handlers[handler_key] = handler
        self.logger.info(f"Registered handler: {handler_key}")
    
    def add_routing_rule(self, pattern: str, target: str):
        """Add a routing rule for command patterns"""
        self.routing_rules[pattern] = target
        self.logger.info(f"Added routing rule: {pattern} -> {target}")
    
    def set_default_handler(self, target: str, handler: Callable):
        """Set default handler for a target"""
        self.default_handlers[target] = handler
        self.logger.info(f"Set default handler for target: {target}")
    
    async def queue_command(self, command_type: str, target: str, 
                          payload: Dict[str, Any], source: str = "system") -> str:
        """Queue a command for execution"""
        try:
            # Generate command ID
            command_id = f"{int(time.time() * 1000)}_{len(self.active_commands)}"
            
            # Create command object
            command = Command(command_id, command_type, target, payload, source)
            
            # Queue command
            await self.command_queue.put(command)
            self.active_commands[command_id] = command
            
            self.logger.info(f"Queued command: {command_id} ({command_type} -> {target})")
            
            # Update metrics
            self.metrics['queue_size'] = self.command_queue.qsize()
            self.metrics['active_commands'] = len(self.active_commands)
            
            return command_id
            
        except asyncio.QueueFull:
            self.logger.error(f"Command queue full, dropping command: {command_type}")
            raise Exception("Command queue is full")
        except Exception as e:
            self.logger.error(f"Failed to queue command: {e}")
            raise
    
    async def execute_command(self, command: Command) -> Dict[str, Any]:
        """Execute a single command"""
        try:
            command.status = CommandStatus.PROCESSING
            command.started_at = datetime.now(timezone.utc)
            
            self.logger.info(f"Executing command: {command.command_id}")
            
            # Find appropriate handler
            handler = self._find_handler(command)
            
            if not handler:
                raise Exception(f"No handler found for {command.command_type} -> {command.target}")
            
            # Execute command with timeout
            try:
                result = await asyncio.wait_for(
                    self._call_handler(handler, command),
                    timeout=self.config.COMMAND_TIMEOUT
                )
                
                # Command completed successfully
                command.status = CommandStatus.COMPLETED
                command.result = result
                command.completed_at = datetime.now(timezone.utc)
                
                self.logger.info(f"Command completed: {command.command_id}")
                
                # Update metrics
                processing_time = (command.completed_at - command.started_at).total_seconds()
                self.metrics['commands_processed'] += 1
                self.metrics['avg_processing_time'] = (
                    (self.metrics['avg_processing_time'] + processing_time) / 2
                )
                
                return {'success': True, 'result': result}
                
            except asyncio.TimeoutError:
                command.status = CommandStatus.TIMEOUT
                command.error = "Command execution timeout"
                command.completed_at = datetime.now(timezone.utc)
                
                self.logger.error(f"Command timeout: {command.command_id}")
                self.metrics['commands_timeout'] += 1
                
                return {'success': False, 'error': 'timeout'}
            
        except Exception as e:
            command.status = CommandStatus.FAILED
            command.error = str(e)
            command.completed_at = datetime.now(timezone.utc)
            
            self.logger.error(f"Command failed: {command.command_id} - {e}")
            self.metrics['commands_failed'] += 1
            
            return {'success': False, 'error': str(e)}
        
        finally:
            # Move to history and clean up
            self._add_to_history(command)
            self.active_commands.pop(command.command_id, None)
            self.metrics['active_commands'] = len(self.active_commands)
    
    def _find_handler(self, command: Command) -> Optional[Callable]:
        """Find appropriate handler for command"""
        # Try specific handler first
        handler_key = f"{command.target}.{command.command_type}"
        if handler_key in self.command_handlers:
            return self.command_handlers[handler_key]
        
        # Try routing rules
        for pattern, target in self.routing_rules.items():
            if command.command_type.startswith(pattern):
                handler_key = f"{target}.{command.command_type}"
                if handler_key in self.command_handlers:
                    return self.command_handlers[handler_key]
        
        # Try default handler for target
        if command.target in self.default_handlers:
            return self.default_handlers[command.target]
        
        return None
    
    async def _call_handler(self, handler: Callable, command: Command) -> Any:
        """Call command handler with appropriate arguments"""
        try:
            # Check if handler is async
            if asyncio.iscoroutinefunction(handler):
                # Try different call patterns
                try:
                    # Pattern 1: handler(command)
                    return await handler(command)
                except TypeError:
                    try:
                        # Pattern 2: handler(command_type, payload)
                        return await handler(command.command_type, command.payload)
                    except TypeError:
                        # Pattern 3: handler(payload)
                        return await handler(command.payload)
            else:
                # Synchronous handler
                try:
                    return handler(command)
                except TypeError:
                    try:
                        return handler(command.command_type, command.payload)
                    except TypeError:
                        return handler(command.payload)
                        
        except Exception as e:
            self.logger.error(f"Handler execution failed: {e}")
            raise
    
    def _add_to_history(self, command: Command):
        """Add command to history with size limit"""
        self.command_history.append(command.to_dict())
        
        # Maintain history size limit
        if len(self.command_history) > self.max_history:
            self.command_history = self.command_history[-self.max_history:]
    
    async def process_commands(self):
        """Main command processing loop"""
        self.logger.info("Starting command processing loop")
        
        while self.running:
            try:
                # Get command from queue
                command = await self.command_queue.get()
                
                # Execute command
                await self.execute_command(command)
                
                # Mark task as done
                self.command_queue.task_done()
                
            except asyncio.CancelledError:
                self.logger.info("Command processing loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in command processing loop: {e}")
                await asyncio.sleep(1)  # Brief pause before continuing
    
    async def start(self):
        """Start the command router"""
        if self.running:
            self.logger.warning("Command router already running")
            return
        
        self.running = True
        self.logger.info("Starting command router")
        
        # Setup default handlers
        self._setup_default_handlers()
        
        # Start command processing
        self.processing_task = asyncio.create_task(self.process_commands())
        
        self.logger.info("Command router started")
    
    def _setup_default_handlers(self):
        """Setup default system command handlers"""
        
        async def handle_status(command):
            """Handle status commands"""
            target = command.target
            if target in self.components:
                component = self.components[target]
                if hasattr(component, 'get_status'):
                    return component.get_status()
                else:
                    return {'status': 'active', 'component': target}
            return {'error': f'Component {target} not found'}
        
        async def handle_health(command):
            """Handle health check commands"""
            target = command.target
            if target in self.components:
                component = self.components[target]
                if hasattr(component, 'get_health_info'):
                    return component.get_health_info()
                else:
                    return {'healthy': True, 'component': target}
            return {'healthy': False, 'error': f'Component {target} not found'}
        
        # Register default handlers
        self.register_handler('status', 'system', handle_status)
        self.register_handler('health', 'system', handle_health)
    
    async def stop(self):
        """Stop the command router"""
        if not self.running:
            return
        
        self.logger.info("Stopping command router")
        self.running = False
        
        # Cancel processing task
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all active commands
        for command in self.active_commands.values():
            command.status = CommandStatus.CANCELLED
            command.error = "System shutdown"
            command.completed_at = datetime.now(timezone.utc)
        
        self.logger.info("Command router stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get command router status"""
        return {
            'running': self.running,
            'registered_components': list(self.components.keys()),
            'registered_handlers': list(self.command_handlers.keys()),
            'routing_rules': self.routing_rules.copy(),
            'metrics': self.metrics.copy(),
            'queue_size': self.command_queue.qsize(),
            'active_commands': len(self.active_commands),
            'command_history_size': len(self.command_history)
        }
    
    def get_command_info(self, command_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific command"""
        # Check active commands
        if command_id in self.active_commands:
            return self.active_commands[command_id].to_dict()
        
        # Check history
        for cmd_dict in reversed(self.command_history):
            if cmd_dict['command_id'] == command_id:
                return cmd_dict
        
        return None
    
    def get_recent_commands(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent command history"""
        return self.command_history[-limit:]
