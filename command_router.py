# command_router.py
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable, Union
from enum import Enum

# These class/enum definitions need to exist before CommandRouter uses them.
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
    
    def __init__(self, config, services: dict):
        self.config = config
        self.services = services
        self.logger = logging.getLogger(__name__)
        
        # Router state
        self.running = False
        self.command_handlers = {}
        
        # Command queue and processing
        queue_size = getattr(config, 'MAX_COMMAND_QUEUE', 100)
        self.command_queue = asyncio.Queue(maxsize=queue_size)
        self.active_commands = {}
        self.command_history = []
        self.max_history = 1000
        
        # Processing task
        self.processing_task = None

    async def handle_command(self, data: str) -> str:
        """Handles an incoming command string (e.g., from a WebSocket)."""
        # This is a placeholder for your actual command parsing logic.
        # It should parse the string and then queue a command.
        # For now, it just echoes.
        self.logger.info(f"Received command data: {data}")
        # In a real implementation, you would call:
        # await self.queue_command(command_type, target, payload)
        return f"Acknowledged: {data}"

    async def queue_command(self, command_type: str, target: str, 
                            payload: Dict[str, Any], source: str = "system") -> str:
        """Queue a command for execution"""
        command_id = f"{int(time.time() * 1000)}_{len(self.active_commands)}"
        command = Command(command_id, command_type, target, payload, source)
        await self.command_queue.put(command)
        self.active_commands[command_id] = command
        self.logger.info(f"Queued command: {command_id} ({command_type} -> {target})")
        return command_id

    async def execute_command(self, command: Command) -> Dict[str, Any]:
        """Execute a single command"""
        try:
            command.status = CommandStatus.PROCESSING
            command.started_at = datetime.now(timezone.utc)
            self.logger.info(f"Executing command: {command.command_id}")

            # This is placeholder logic. You will need to implement your
            # handler discovery logic (e.g., based on command.target).
            handler = self.services.get(command.target)
            if not handler or not hasattr(handler, command.command_type):
                raise Exception(f"No handler found for {command.command_type} on target {command.target}")

            # Get the actual method to call from the service
            handler_method = getattr(handler, command.command_type)
            result = await handler_method(command.payload)

            command.status = CommandStatus.COMPLETED
            command.result = result
            command.completed_at = datetime.now(timezone.utc)
            self.logger.info(f"Command completed: {command.command_id}")
            return {'success': True, 'result': result}

        except Exception as e:  # pylint: disable=broad-except
            command.error = str(e)
            command.status = CommandStatus.FAILED
            command.completed_at = datetime.now(timezone.utc)
            self.logger.error(f"Command failed: {command.command_id} - {e}")
            return {'success': False, 'error': str(e)}
        
        finally:
            self._add_to_history(command)
            if command.command_id in self.active_commands:
                self.active_commands.pop(command.command_id)

    def _add_to_history(self, command: Command):
        """Add command to history and trim if necessary"""
        self.command_history.append(command.to_dict())
        if len(self.command_history) > self.max_history:
            self.command_history.pop(0)

    async def process_commands(self):
        """Main loop to process commands from the queue"""
        self.running = True
        self.logger.info("Command processor started.")
        while self.running:
            try:
                command = await self.command_queue.get()
                await self.execute_command(command)
                self.command_queue.task_done()
            except asyncio.CancelledError:
                break
        self.logger.info("Command processor stopped.")

    async def start(self):
        """Start the command router's processing loop"""
        if not self.running:
            self.processing_task = asyncio.create_task(self.process_commands())

    async def stop(self):
        """Stop the command router's processing loop"""
        if self.running and self.processing_task:
            self.running = False
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass # Expected
