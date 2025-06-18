"""
NeuroSync Toggle Dispatcher
Handles on/off toggle commands and state management
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable
from enum import Enum


class ToggleState(Enum):
    """Toggle state enumeration"""
    ON = "on"
    OFF = "off"
    TRANSITIONING = "transitioning"
    ERROR = "error"
    UNKNOWN = "unknown"


class Toggle:
    """Toggle object with state management"""
    
    def __init__(self, toggle_id: str, name: str, initial_state: ToggleState = ToggleState.OFF):
        self.toggle_id = toggle_id
        self.name = name
        self.state = initial_state
        self.previous_state = None
        self.created_at = datetime.now(timezone.utc)
        self.last_changed = self.created_at
        self.change_count = 0
        self.metadata = {}
        
        # Callbacks
        self.on_callbacks = []
        self.off_callbacks = []
        self.state_change_callbacks = []
        
        # Validation
        self.validators = []
        
        # History
        self.state_history = []
        self.max_history = 100
    
    def add_state_change_callback(self, callback: Callable):
        """Add callback for state changes"""
        self.state_change_callbacks.append(callback)
    
    def add_on_callback(self, callback: Callable):
        """Add callback for ON state"""
        self.on_callbacks.append(callback)
    
    def add_off_callback(self, callback: Callable):
        """Add callback for OFF state"""
        self.off_callbacks.append(callback)
    
    def add_validator(self, validator: Callable):
        """Add state change validator"""
        self.validators.append(validator)
    
    async def change_state(self, new_state: ToggleState, source: str = "system") -> bool:
        """Change toggle state with validation and callbacks"""
        if new_state == self.state:
            return True  # No change needed
        
        # Run validators
        for validator in self.validators:
            try:
                if asyncio.iscoroutinefunction(validator):
                    valid = await validator(self, new_state)
                else:
                    valid = validator(self, new_state)
                
                if not valid:
                    return False
            except Exception as e:
                logging.error(f"Validator error for toggle {self.toggle_id}: {e}")
                return False
        
        # Store previous state
        self.previous_state = self.state
        
        # Add to history
        history_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'from_state': self.state.value,
            'to_state': new_state.value,
            'source': source,
            'change_count': self.change_count
        }
        self.state_history.append(history_entry)
        
        # Maintain history size
        if len(self.state_history) > self.max_history:
            self.state_history = self.state_history[-self.max_history:]
        
        # Update state
        self.state = new_state
        self.last_changed = datetime.now(timezone.utc)
        self.change_count += 1
        
        # Execute callbacks
        await self._execute_callbacks(new_state, source)
        
        return True
    
    async def _execute_callbacks(self, new_state: ToggleState, source: str):
        """Execute appropriate callbacks for state change"""
        # State change callbacks
        for callback in self.state_change_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self, new_state, source)
                else:
                    callback(self, new_state, source)
            except Exception as e:
                logging.error(f"State change callback error: {e}")
        
        # Specific state callbacks
        callbacks = []
        if new_state == ToggleState.ON:
            callbacks = self.on_callbacks
        elif new_state == ToggleState.OFF:
            callbacks = self.off_callbacks
        
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self, source)
                else:
                    callback(self, source)
            except Exception as e:
                logging.error(f"State-specific callback error: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert toggle to dictionary"""
        return {
            'toggle_id': self.toggle_id,
            'name': self.name,
            'state': self.state.value,
            'previous_state': self.previous_state.value if self.previous_state else None,
            'created_at': self.created_at.isoformat(),
            'last_changed': self.last_changed.isoformat(),
            'change_count': self.change_count,
            'metadata': self.metadata.copy(),
            'recent_history': self.state_history[-10:]  # Last 10 changes
        }


class ToggleDispatcher:
    """Handles toggle commands and state management"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Dispatcher state
        self.running = False
        self.toggles = {}
        
        # Command processing
        self.command_queue = asyncio.Queue()
        self.command_handlers = {
            'toggle_on': self._handle_toggle_on,
            'toggle_off': self._handle_toggle_off,
            'toggle_state': self._handle_toggle_state,
            'toggle_info': self._handle_toggle_info,
            'list_toggles': self._handle_list_toggles
        }
        
        # Metrics
        self.metrics = {
            'commands_processed': 0,
            'state_changes': 0,
            'validation_failures': 0,
            'callback_errors': 0
        }
        
        # Processing task
        self.processing_task = None
        
        # Initialize default toggles
        self._initialize_default_toggles()
    
    def _initialize_default_toggles(self):
        """Initialize default system toggles"""
        default_toggles = [
            ('system_active', 'System Active'),
            ('heartbeat_enabled', 'Heartbeat Enabled'),
            ('sync_enabled', 'Sync Enabled'),
            ('monitoring_enabled', 'Monitoring Enabled'),
            ('telegram_enabled', 'Telegram Integration'),
            ('failsafe_enabled', 'Failsafe Monitoring'),
            ('load_balancing_enabled', 'Load Balancing'),
            ('audit_logging_enabled', 'Audit Logging')
        ]
        
        for toggle_id, name in default_toggles:
            self.create_toggle(toggle_id, name, ToggleState.ON)
    
    def create_toggle(self, toggle_id: str, name: str, 
                     initial_state: ToggleState = ToggleState.OFF,
                     metadata: Dict[str, Any] = None) -> Toggle:
        """Create a new toggle"""
        if toggle_id in self.toggles:
            self.logger.warning(f"Toggle {toggle_id} already exists")
            return self.toggles[toggle_id]
        
        toggle = Toggle(toggle_id, name, initial_state)
        if metadata:
            toggle.metadata.update(metadata)
        
        self.toggles[toggle_id] = toggle
        
        self.logger.info(f"Created toggle: {toggle_id} ({name}) - {initial_state.value}")
        
        return toggle
    
    def get_toggle(self, toggle_id: str) -> Optional[Toggle]:
        """Get toggle by ID"""
        return self.toggles.get(toggle_id)
    
    def delete_toggle(self, toggle_id: str) -> bool:
        """Delete a toggle"""
        if toggle_id in self.toggles:
            del self.toggles[toggle_id]
            self.logger.info(f"Deleted toggle: {toggle_id}")
            return True
        return False
    
    async def execute_command(self, command_type: str, payload: Dict[str, Any], 
                            source: str = "system") -> Dict[str, Any]:
        """Execute toggle command"""
        try:
            if command_type not in self.command_handlers:
                return {'success': False, 'error': f'Unknown command: {command_type}'}
            
            handler = self.command_handlers[command_type]
            result = await handler(payload, source)
            
            self.metrics['commands_processed'] += 1
            
            return {'success': True, 'result': result}
            
        except Exception as e:
            self.logger.error(f"Command execution failed: {command_type} - {e}")
            return {'success': False, 'error': str(e)}
    
    async def _handle_toggle_on(self, payload: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Handle toggle ON command"""
        toggle_id = payload.get('toggle_id')
        if not toggle_id:
            return {'error': 'toggle_id required'}
        
        toggle = self.get_toggle(toggle_id)
        if not toggle:
            return {'error': f'Toggle {toggle_id} not found'}
        
        success = await toggle.change_state(ToggleState.ON, source)
        
        if success:
            self.metrics['state_changes'] += 1
            return {
                'toggle_id': toggle_id,
                'state': ToggleState.ON.value,
                'changed': True
            }
        else:
            self.metrics['validation_failures'] += 1
            return {
                'toggle_id': toggle_id,
                'error': 'State change validation failed'
            }
    
    async def _handle_toggle_off(self, payload: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Handle toggle OFF command"""
        toggle_id = payload.get('toggle_id')
        if not toggle_id:
            return {'error': 'toggle_id required'}
        
        toggle = self.get_toggle(toggle_id)
        if not toggle:
            return {'error': f'Toggle {toggle_id} not found'}
        
        success = await toggle.change_state(ToggleState.OFF, source)
        
        if success:
            self.metrics['state_changes'] += 1
            return {
                'toggle_id': toggle_id,
                'state': ToggleState.OFF.value,
                'changed': True
            }
        else:
            self.metrics['validation_failures'] += 1
            return {
                'toggle_id': toggle_id,
                'error': 'State change validation failed'
            }
    
    async def _handle_toggle_state(self, payload: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Handle toggle state query"""
        toggle_id = payload.get('toggle_id')
        if not toggle_id:
            return {'error': 'toggle_id required'}
        
        toggle = self.get_toggle(toggle_id)
        if not toggle:
            return {'error': f'Toggle {toggle_id} not found'}
        
        return {
            'toggle_id': toggle_id,
            'state': toggle.state.value,
            'last_changed': toggle.last_changed.isoformat(),
            'change_count': toggle.change_count
        }
    
    async def _handle_toggle_info(self, payload: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Handle toggle info request"""
        toggle_id = payload.get('toggle_id')
        if not toggle_id:
            return {'error': 'toggle_id required'}
        
        toggle = self.get_toggle(toggle_id)
        if not toggle:
            return {'error': f'Toggle {toggle_id} not found'}
        
        return toggle.to_dict()
    
    async def _handle_list_toggles(self, payload: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Handle list toggles request"""
        return {
            'toggles': [toggle.to_dict() for toggle in self.toggles.values()],
            'count': len(self.toggles)
        }
    
    async def toggle_on(self, toggle_id: str, source: str = "system") -> bool:
        """Turn toggle ON"""
        toggle = self.get_toggle(toggle_id)
        if not toggle:
            return False
        
        return await toggle.change_state(ToggleState.ON, source)
    
    async def toggle_off(self, toggle_id: str, source: str = "system") -> bool:
        """Turn toggle OFF"""
        toggle = self.get_toggle(toggle_id)
        if not toggle:
            return False
        
        return await toggle.change_state(ToggleState.OFF, source)
    
    def is_toggle_on(self, toggle_id: str) -> bool:
        """Check if toggle is ON"""
        toggle = self.get_toggle(toggle_id)
        return toggle.state == ToggleState.ON if toggle else False
    
    def is_toggle_off(self, toggle_id: str) -> bool:
        """Check if toggle is OFF"""
        toggle = self.get_toggle(toggle_id)
        return toggle.state == ToggleState.OFF if toggle else False
    
    def get_toggle_state(self, toggle_id: str) -> Optional[ToggleState]:
        """Get toggle state"""
        toggle = self.get_toggle(toggle_id)
        return toggle.state if toggle else None
    
    async def process_commands(self):
        """Process queued commands"""
        self.logger.info("Starting toggle command processing")
        
        while self.running:
            try:
                # Get command from queue
                command = await self.command_queue.get()
                
                # Execute command
                result = await self.execute_command(
                    command['type'], 
                    command['payload'], 
                    command.get('source', 'system')
                )
                
                # Store result if callback provided
                if 'callback' in command:
                    try:
                        if asyncio.iscoroutinefunction(command['callback']):
                            await command['callback'](result)
                        else:
                            command['callback'](result)
                    except Exception as e:
                        self.logger.error(f"Command callback error: {e}")
                        self.metrics['callback_errors'] += 1
                
                self.command_queue.task_done()
                
            except asyncio.CancelledError:
                self.logger.info("Toggle command processing cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in command processing: {e}")
                await asyncio.sleep(1)
    
    async def queue_command(self, command_type: str, payload: Dict[str, Any], 
                          source: str = "system", callback: Callable = None):
        """Queue a toggle command"""
        command = {
            'type': command_type,
            'payload': payload,
            'source': source,
            'callback': callback,
            'queued_at': datetime.now(timezone.utc).isoformat()
        }
        
        await self.command_queue.put(command)
    
    def setup_system_toggle_callbacks(self):
        """Setup callbacks for system toggles"""
        
        # System active toggle
        system_toggle = self.get_toggle('system_active')
        if system_toggle:
            system_toggle.add_state_change_callback(self._system_active_changed)
        
        # Heartbeat toggle
        heartbeat_toggle = self.get_toggle('heartbeat_enabled')
        if heartbeat_toggle:
            heartbeat_toggle.add_state_change_callback(self._heartbeat_enabled_changed)
        
        # Add more system callbacks as needed
    
    async def _system_active_changed(self, toggle: Toggle, new_state: ToggleState, source: str):
        """Handle system active state change"""
        self.logger.info(f"System active state changed to {new_state.value} by {source}")
        
        if new_state == ToggleState.OFF:
            # System deactivation - could trigger shutdown procedures
            self.logger.warning("System deactivated - consider shutdown procedures")
    
    async def _heartbeat_enabled_changed(self, toggle: Toggle, new_state: ToggleState, source: str):
        """Handle heartbeat enabled state change"""
        self.logger.info(f"Heartbeat enabled state changed to {new_state.value} by {source}")
    
    async def start(self):
        """Start the toggle dispatcher"""
        if self.running:
            self.logger.warning("Toggle dispatcher already running")
            return
        
        self.running = True
        self.logger.info("Starting toggle dispatcher")
        
        # Setup system callbacks
        self.setup_system_toggle_callbacks()
        
        # Start command processing
        self.processing_task = asyncio.create_task(self.process_commands())
        
        self.logger.info("Toggle dispatcher started")
    
    async def stop(self):
        """Stop the toggle dispatcher"""
        if not self.running:
            return
        
        self.logger.info("Stopping toggle dispatcher")
        self.running = False
        
        # Cancel processing task
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Toggle dispatcher stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get toggle dispatcher status"""
        return {
            'running': self.running,
            'toggle_count': len(self.toggles),
            'queue_size': self.command_queue.qsize(),
            'metrics': self.metrics.copy(),
            'toggle_states': {
                toggle_id: toggle.state.value 
                for toggle_id, toggle in self.toggles.items()
            }
        }
    
    def get_toggle_summary(self) -> Dict[str, Any]:
        """Get summary of all toggles"""
        states_count = {}
        for toggle in self.toggles.values():
            state = toggle.state.value
            states_count[state] = states_count.get(state, 0) + 1
        
        return {
            'total_toggles': len(self.toggles),
            'states_distribution': states_count,
            'recent_changes': [
                {
                    'toggle_id': toggle.toggle_id,
                    'name': toggle.name,
                    'last_changed': toggle.last_changed.isoformat(),
                    'change_count': toggle.change_count
                }
                for toggle in sorted(
                    self.toggles.values(), 
                    key=lambda t: t.last_changed, 
                    reverse=True
                )[:10]
            ]
        }
