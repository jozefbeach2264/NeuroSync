"""
NeuroSync Load Balancer
Handles task distribution and load balancing across system components
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
import heapq


class TaskPriority(Enum):
    """Task priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class Task:
    """Task object for load balancing"""
    
    def __init__(self, task_id: str, task_type: str, payload: Dict[str, Any], 
                 priority: TaskPriority = TaskPriority.NORMAL):
        self.task_id = task_id
        self.task_type = task_type
        self.payload = payload
        self.priority = priority
        self.created_at = datetime.now(timezone.utc)
        self.assigned_at = None
        self.completed_at = None
        self.worker_id = None
        self.result = None
        self.error = None
        self.retries = 0
    
    def __lt__(self, other):
        """Compare tasks for priority queue (higher priority first)"""
        return self.priority.value > other.priority.value


class Worker:
    """Worker representation for load balancing"""
    
    def __init__(self, worker_id: str, handler: Callable, max_concurrent: int = 1):
        self.worker_id = worker_id
        self.handler = handler
        self.max_concurrent = max_concurrent
        self.active_tasks = {}
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.last_activity = datetime.now(timezone.utc)
        self.load_score = 0.0
        self.available = True


class LoadBalancer:
    """Load balancer for task distribution"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Load balancer state
        self.running = False
        self.workers = {}
        self.task_queue = []  # Priority queue
        self.active_tasks = {}
        self.completed_tasks = []
        self.max_completed_history = 1000
        
        # Load balancing strategies
        self.strategies = {
            'round_robin': self._round_robin_strategy,
            'least_loaded': self._least_loaded_strategy,
            'priority_first': self._priority_first_strategy,
            'resource_aware': self._resource_aware_strategy
        }
        self.current_strategy = 'least_loaded'
        
        # Metrics
        self.metrics = {
            'tasks_queued': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'avg_processing_time': 0.0,
            'avg_queue_wait_time': 0.0,
            'worker_utilization': {},
            'load_distribution': {}
        }
        
        # Processing task
        self.processing_task = None
        self.monitor_task = None
    
    def register_worker(self, worker_id: str, handler: Callable, 
                       max_concurrent: int = 1, task_types: List[str] = None):
        """Register a worker for task processing"""
        worker = Worker(worker_id, handler, max_concurrent)
        worker.task_types = task_types or ['*']  # * means all task types
        
        self.workers[worker_id] = worker
        self.metrics['worker_utilization'][worker_id] = 0.0
        self.metrics['load_distribution'][worker_id] = 0
        
        self.logger.info(f"Registered worker: {worker_id} (max_concurrent: {max_concurrent})")
    
    def unregister_worker(self, worker_id: str):
        """Unregister a worker"""
        if worker_id in self.workers:
            worker = self.workers[worker_id]
            
            # Cancel active tasks
            for task_id in list(worker.active_tasks.keys()):
                if task_id in self.active_tasks:
                    task = self.active_tasks[task_id]
                    task.error = f"Worker {worker_id} unregistered"
                    self._complete_task(task)
            
            # Remove worker
            del self.workers[worker_id]
            self.metrics['worker_utilization'].pop(worker_id, None)
            self.metrics['load_distribution'].pop(worker_id, None)
            
            self.logger.info(f"Unregistered worker: {worker_id}")
    
    async def submit_task(self, task_type: str, payload: Dict[str, Any], 
                         priority: TaskPriority = TaskPriority.NORMAL) -> str:
        """Submit a task for processing"""
        task_id = f"task_{int(time.time() * 1000)}_{len(self.active_tasks)}"
        
        task = Task(task_id, task_type, payload, priority)
        
        # Add to priority queue
        heapq.heappush(self.task_queue, task)
        self.active_tasks[task_id] = task
        
        self.metrics['tasks_queued'] += 1
        
        self.logger.info(f"Submitted task: {task_id} ({task_type}, priority: {priority.name})")
        
        return task_id
    
    def _get_available_workers(self, task_type: str) -> List[Worker]:
        """Get workers available for a specific task type"""
        available = []
        
        for worker in self.workers.values():
            if not worker.available:
                continue
            
            # Check if worker handles this task type
            if '*' not in worker.task_types and task_type not in worker.task_types:
                continue
            
            # Check if worker has capacity
            if len(worker.active_tasks) >= worker.max_concurrent:
                continue
            
            available.append(worker)
        
        return available
    
    def _round_robin_strategy(self, workers: List[Worker], task: Task) -> Optional[Worker]:
        """Round-robin worker selection"""
        if not workers:
            return None
        
        # Simple round-robin based on completed tasks
        min_completed = min(worker.completed_tasks for worker in workers)
        for worker in workers:
            if worker.completed_tasks == min_completed:
                return worker
        
        return workers[0]
    
    def _least_loaded_strategy(self, workers: List[Worker], task: Task) -> Optional[Worker]:
        """Select worker with least current load"""
        if not workers:
            return None
        
        return min(workers, key=lambda w: len(w.active_tasks))
    
    def _priority_first_strategy(self, workers: List[Worker], task: Task) -> Optional[Worker]:
        """Select worker optimized for task priority"""
        if not workers:
            return None
        
        # For high priority tasks, prefer workers with fewer active tasks
        if task.priority in [TaskPriority.HIGH, TaskPriority.CRITICAL]:
            return min(workers, key=lambda w: len(w.active_tasks))
        
        # For normal/low priority, use load balancing
        return self._least_loaded_strategy(workers, task)
    
    def _resource_aware_strategy(self, workers: List[Worker], task: Task) -> Optional[Worker]:
        """Resource-aware worker selection"""
        if not workers:
            return None
        
        # Calculate load scores
        for worker in workers:
            utilization = len(worker.active_tasks) / worker.max_concurrent
            worker.load_score = utilization
        
        return min(workers, key=lambda w: w.load_score)
    
    def select_worker(self, task: Task) -> Optional[Worker]:
        """Select best worker for task using current strategy"""
        available_workers = self._get_available_workers(task.task_type)
        
        if not available_workers:
            return None
        
        strategy_func = self.strategies.get(self.current_strategy, self._least_loaded_strategy)
        return strategy_func(available_workers, task)
    
    async def assign_task(self, task: Task, worker: Worker) -> bool:
        """Assign task to worker"""
        try:
            task.assigned_at = datetime.now(timezone.utc)
            task.worker_id = worker.worker_id
            
            # Add to worker's active tasks
            worker.active_tasks[task.task_id] = task
            worker.last_activity = datetime.now(timezone.utc)
            
            self.logger.info(f"Assigned task {task.task_id} to worker {worker.worker_id}")
            
            # Execute task
            asyncio.create_task(self._execute_task(task, worker))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to assign task {task.task_id}: {e}")
            return False
    
    async def _execute_task(self, task: Task, worker: Worker):
        """Execute task on worker"""
        try:
            self.logger.debug(f"Executing task {task.task_id} on worker {worker.worker_id}")
            
            # Call worker handler
            if asyncio.iscoroutinefunction(worker.handler):
                result = await asyncio.wait_for(
                    worker.handler(task.task_type, task.payload),
                    timeout=self.config.TASK_TIMEOUT
                )
            else:
                result = worker.handler(task.task_type, task.payload)
            
            # Task completed successfully
            task.result = result
            task.completed_at = datetime.now(timezone.utc)
            
            self.logger.info(f"Task {task.task_id} completed successfully")
            
            # Update worker stats
            worker.completed_tasks += 1
            
            # Update metrics
            self.metrics['tasks_completed'] += 1
            self._update_processing_metrics(task)
            
        except asyncio.TimeoutError:
            task.error = "Task execution timeout"
            task.completed_at = datetime.now(timezone.utc)
            
            self.logger.error(f"Task {task.task_id} timed out")
            worker.failed_tasks += 1
            self.metrics['tasks_failed'] += 1
            
        except Exception as e:
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc)
            
            self.logger.error(f"Task {task.task_id} failed: {e}")
            worker.failed_tasks += 1
            self.metrics['tasks_failed'] += 1
        
        finally:
            # Clean up
            self._complete_task(task)
    
    def _complete_task(self, task: Task):
        """Complete task and clean up"""
        # Remove from active tasks
        self.active_tasks.pop(task.task_id, None)
        
        # Remove from worker's active tasks
        if task.worker_id and task.worker_id in self.workers:
            worker = self.workers[task.worker_id]
            worker.active_tasks.pop(task.task_id, None)
        
        # Add to completed history
        self.completed_tasks.append(task)
        if len(self.completed_tasks) > self.max_completed_history:
            self.completed_tasks = self.completed_tasks[-self.max_completed_history:]
    
    def _update_processing_metrics(self, task: Task):
        """Update processing time metrics"""
        if task.assigned_at and task.completed_at:
            processing_time = (task.completed_at - task.assigned_at).total_seconds()
            self.metrics['avg_processing_time'] = (
                (self.metrics['avg_processing_time'] + processing_time) / 2
            )
        
        if task.created_at and task.assigned_at:
            wait_time = (task.assigned_at - task.created_at).total_seconds()
            self.metrics['avg_queue_wait_time'] = (
                (self.metrics['avg_queue_wait_time'] + wait_time) / 2
            )
    
    async def process_queue(self):
        """Main queue processing loop"""
        self.logger.info("Starting load balancer queue processing")
        
        while self.running:
            try:
                if not self.task_queue:
                    await asyncio.sleep(0.1)
                    continue
                
                # Get highest priority task
                task = heapq.heappop(self.task_queue)
                
                # Find available worker
                worker = self.select_worker(task)
                
                if worker:
                    # Assign task to worker
                    await self.assign_task(task, worker)
                else:
                    # No available worker, put task back in queue
                    heapq.heappush(self.task_queue, task)
                    await asyncio.sleep(1)  # Wait before retrying
                
            except asyncio.CancelledError:
                self.logger.info("Load balancer queue processing cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in queue processing: {e}")
                await asyncio.sleep(1)
    
    async def monitor_workers(self):
        """Monitor worker health and performance"""
        self.logger.info("Starting worker monitoring")
        
        while self.running:
            try:
                current_time = datetime.now(timezone.utc)
                
                for worker_id, worker in self.workers.items():
                    # Update utilization metrics
                    utilization = len(worker.active_tasks) / worker.max_concurrent * 100
                    self.metrics['worker_utilization'][worker_id] = utilization
                    self.metrics['load_distribution'][worker_id] = len(worker.active_tasks)
                    
                    # Check for inactive workers
                    time_since_activity = (current_time - worker.last_activity).total_seconds()
                    if time_since_activity > 300:  # 5 minutes
                        self.logger.warning(f"Worker {worker_id} inactive for {time_since_activity}s")
                
                await asyncio.sleep(30)  # Monitor every 30 seconds
                
            except asyncio.CancelledError:
                self.logger.info("Worker monitoring cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in worker monitoring: {e}")
                await asyncio.sleep(30)
    
    def set_strategy(self, strategy: str):
        """Set load balancing strategy"""
        if strategy not in self.strategies:
            raise ValueError(f"Unknown strategy: {strategy}")
        
        self.current_strategy = strategy
        self.logger.info(f"Load balancing strategy set to: {strategy}")
    
    async def start(self):
        """Start the load balancer"""
        if self.running:
            self.logger.warning("Load balancer already running")
            return
        
        self.running = True
        self.logger.info("Starting load balancer")
        
        # Start processing and monitoring tasks
        self.processing_task = asyncio.create_task(self.process_queue())
        self.monitor_task = asyncio.create_task(self.monitor_workers())
        
        self.logger.info("Load balancer started")
    
    async def stop(self):
        """Stop the load balancer"""
        if not self.running:
            return
        
        self.logger.info("Stopping load balancer")
        self.running = False
        
        # Cancel tasks
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Load balancer stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get load balancer status"""
        return {
            'running': self.running,
            'strategy': self.current_strategy,
            'workers': {
                worker_id: {
                    'active_tasks': len(worker.active_tasks),
                    'max_concurrent': worker.max_concurrent,
                    'completed_tasks': worker.completed_tasks,
                    'failed_tasks': worker.failed_tasks,
                    'task_types': worker.task_types,
                    'available': worker.available,
                    'utilization': self.metrics['worker_utilization'].get(worker_id, 0)
                }
                for worker_id, worker in self.workers.items()
            },
            'queue_size': len(self.task_queue),
            'active_tasks': len(self.active_tasks),
            'metrics': self.metrics.copy()
        }
    
    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific task"""
        # Check active tasks
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            return {
                'task_id': task.task_id,
                'task_type': task.task_type,
                'priority': task.priority.name,
                'status': 'active',
                'worker_id': task.worker_id,
                'created_at': task.created_at.isoformat(),
                'assigned_at': task.assigned_at.isoformat() if task.assigned_at else None
            }
        
        # Check completed tasks
        for task in reversed(self.completed_tasks):
            if task.task_id == task_id:
                return {
                    'task_id': task.task_id,
                    'task_type': task.task_type,
                    'priority': task.priority.name,
                    'status': 'completed' if task.result else 'failed',
                    'worker_id': task.worker_id,
                    'created_at': task.created_at.isoformat(),
                    'assigned_at': task.assigned_at.isoformat() if task.assigned_at else None,
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                    'result': task.result,
                    'error': task.error
                }
        
        return None
