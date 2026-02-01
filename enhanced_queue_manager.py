"""
Enhanced Queue Manager with Scheduling and Conditional Downloads
Provides aria2-like advanced queuing, scheduling, and conditional download features
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass, field
from queue import PriorityQueue, Queue
import json
import os
import logging
from enum import Enum

class DownloadConditionType(Enum):
    """Types of download conditions"""
    TIME_BASED = "time_based"
    SIZE_BASED = "size_based"
    BANDWIDTH_BASED = "bandwidth_based"
    DEPENDENCY_BASED = "dependency_based"
    CUSTOM = "custom"

class ScheduleType(Enum):
    """Types of schedules"""
    IMMEDIATE = "immediate"
    DELAYED = "delayed"
    RECURRING = "recurring"
    CONDITIONAL = "conditional"

@dataclass
class DownloadCondition:
    """Represents a condition for download execution"""
    type: DownloadConditionType
    parameters: Dict[str, Any]
    description: str = ""
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate if condition is met"""
        if self.type == DownloadConditionType.TIME_BASED:
            return self._evaluate_time_condition(context)
        elif self.type == DownloadConditionType.SIZE_BASED:
            return self._evaluate_size_condition(context)
        elif self.type == DownloadConditionType.BANDWIDTH_BASED:
            return self._evaluate_bandwidth_condition(context)
        elif self.type == DownloadConditionType.DEPENDENCY_BASED:
            return self._evaluate_dependency_condition(context)
        elif self.type == DownloadConditionType.CUSTOM:
            return self._evaluate_custom_condition(context)
        return True
    
    def _evaluate_time_condition(self, context: Dict) -> bool:
        """Evaluate time-based conditions"""
        current_time = datetime.now()
        
        if 'start_time' in self.parameters:
            start_time = datetime.fromisoformat(self.parameters['start_time'])
            if current_time < start_time:
                return False
        
        if 'end_time' in self.parameters:
            end_time = datetime.fromisoformat(self.parameters['end_time'])
            if current_time > end_time:
                return False
        
        if 'allowed_hours' in self.parameters:
            allowed_hours = self.parameters['allowed_hours']
            current_hour = current_time.hour
            if current_hour not in allowed_hours:
                return False
        
        if 'blocked_days' in self.parameters:
            blocked_days = self.parameters['blocked_days']
            current_weekday = current_time.weekday()
            if current_weekday in blocked_days:
                return False
        
        return True
    
    def _evaluate_size_condition(self, context: Dict) -> bool:
        """Evaluate size-based conditions"""
        file_size = context.get('file_size', 0)
        
        if 'min_size' in self.parameters:
            if file_size < self.parameters['min_size']:
                return False
        
        if 'max_size' in self.parameters:
            if file_size > self.parameters['max_size']:
                return False
        
        return True
    
    def _evaluate_bandwidth_condition(self, context: Dict) -> bool:
        """Evaluate bandwidth-based conditions"""
        current_bandwidth = context.get('available_bandwidth', float('inf'))
        
        if 'min_bandwidth' in self.parameters:
            if current_bandwidth < self.parameters['min_bandwidth']:
                return False
        
        return True
    
    def _evaluate_dependency_condition(self, context: Dict) -> bool:
        """Evaluate dependency-based conditions"""
        completed_downloads = context.get('completed_downloads', set())
        failed_downloads = context.get('failed_downloads', set())
        
        if 'requires_completed' in self.parameters:
            required = set(self.parameters['requires_completed'])
            if not required.issubset(completed_downloads):
                return False
        
        if 'blocks_if_failed' in self.parameters:
            blocked_by = set(self.parameters['blocks_if_failed'])
            if blocked_by.intersection(failed_downloads):
                return False
        
        return True
    
    def _evaluate_custom_condition(self, context: Dict) -> bool:
        """Evaluate custom condition using lambda or function"""
        if 'function' in self.parameters:
            try:
                func = self.parameters['function']
                return func(context)
            except:
                return False
        
        return True

@dataclass
class ScheduleInfo:
    """Information about download scheduling"""
    type: ScheduleType
    parameters: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    
    def get_next_execution_time(self) -> Optional[datetime]:
        """Get next scheduled execution time"""
        if self.type == ScheduleType.IMMEDIATE:
            return datetime.now()
        
        elif self.type == ScheduleType.DELAYED:
            delay_seconds = self.parameters.get('delay_seconds', 0)
            return self.created_at + timedelta(seconds=delay_seconds)
        
        elif self.type == ScheduleType.RECURRING:
            interval_seconds = self.parameters.get('interval_seconds', 3600)
            last_execution = self.parameters.get('last_execution', self.created_at)
            return last_execution + timedelta(seconds=interval_seconds)
        
        elif self.type == ScheduleType.CONDITIONAL:
            # For conditional schedules, check every minute
            return datetime.now() + timedelta(minutes=1)
        
        return None

@dataclass(order=True)
class EnhancedDownloadTask:
    """Enhanced download task with scheduling and conditions"""
    priority: int
    url: str = field(compare=False)
    destination: str = field(compare=False)
    options: Dict = field(compare=False, default_factory=dict)
    
    # Enhanced features
    task_id: str = field(compare=False, default="")
    created_at: datetime = field(compare=False, default_factory=datetime.now)
    schedule: Optional[ScheduleInfo] = field(compare=False, default=None)
    conditions: List[DownloadCondition] = field(compare=False, default_factory=list)
    dependencies: List[str] = field(compare=False, default_factory=list)
    retry_count: int = field(compare=False, default=0)
    max_retries: int = field(compare=False, default=3)
    tags: List[str] = field(compare=False, default_factory=list)
    metadata: Dict[str, Any] = field(compare=False, default_factory=dict)
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        """Check if task can be executed based on conditions"""
        # Check schedule
        if self.schedule:
            next_time = self.schedule.get_next_execution_time()
            if next_time and datetime.now() < next_time:
                return False
        
        # Check conditions
        for condition in self.conditions:
            if not condition.evaluate(context):
                return False
        
        # Check dependencies
        completed_downloads = context.get('completed_downloads', set())
        for dependency in self.dependencies:
            if dependency not in completed_downloads:
                return False
        
        return True

class EnhancedQueueManager:
    """Enhanced queue manager with scheduling and conditional downloads"""
    
    def __init__(self, max_concurrent_downloads: int = 5):
        self.max_concurrent_downloads = max_concurrent_downloads
        
        # Queues
        self.high_priority_queue = PriorityQueue()
        self.normal_priority_queue = PriorityQueue()
        self.low_priority_queue = PriorityQueue()
        self.scheduled_queue = PriorityQueue()  # For scheduled downloads
        self.waiting_queue = Queue()  # For downloads waiting for conditions
        
        # Tracking
        self.active_downloads = {}
        self.completed_downloads = set()
        self.failed_downloads = set()
        self.paused_downloads = {}
        
        # Statistics
        self.stats = {
            'total_queued': 0,
            'total_completed': 0,
            'total_failed': 0,
            'queue_sizes': {
                'high': 0,
                'normal': 0,
                'low': 0,
                'scheduled': 0,
                'waiting': 0
            }
        }
        
        # Control
        self.running = False
        self.threads = []
        self.lock = threading.RLock()
        
        # Configuration
        self.bandwidth_monitor = BandwidthMonitor()
        
        self.logger = logging.getLogger(__name__)
    
    def start(self):
        """Start the queue manager"""
        if self.running:
            return
        
        self.running = True
        
        # Start scheduler thread
        scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        scheduler_thread.start()
        self.threads.append(scheduler_thread)
        
        # Start condition checker thread
        condition_thread = threading.Thread(target=self._condition_checker_loop, daemon=True)
        condition_thread.start()
        self.threads.append(condition_thread)
        
        # Start queue processor thread
        processor_thread = threading.Thread(target=self._queue_processor_loop, daemon=True)
        processor_thread.start()
        self.threads.append(processor_thread)
        
        self.logger.info("Enhanced queue manager started")
    
    def stop(self):
        """Stop the queue manager"""
        self.running = False
        
        # Wait for threads to finish
        for thread in self.threads:
            thread.join(timeout=5)
        
        self.logger.info("Enhanced queue manager stopped")
    
    def add_download(self, url: str, destination: str, priority: int = 5,
                    schedule: Optional[ScheduleInfo] = None,
                    conditions: Optional[List[DownloadCondition]] = None,
                    dependencies: Optional[List[str]] = None,
                    tags: Optional[List[str]] = None,
                    **options) -> str:
        """Add a download to the queue with advanced features"""
        import hashlib
        task_id = hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()[:16]
        
        task = EnhancedDownloadTask(
            priority=priority,
            url=url,
            destination=destination,
            options=options,
            task_id=task_id,
            schedule=schedule,
            conditions=conditions or [],
            dependencies=dependencies or [],
            tags=tags or []
        )
        
        with self.lock:
            # Determine which queue to use
            if schedule and schedule.type != ScheduleType.IMMEDIATE:
                self._add_to_scheduled_queue(task)
            elif conditions or dependencies:
                self._add_to_waiting_queue(task)
            else:
                self._add_to_priority_queue(task, priority)
            
            self.stats['total_queued'] += 1
            self._update_queue_stats()
        
        self.logger.info(f"Added download task {task_id} with priority {priority}")
        return task_id
    
    def _add_to_priority_queue(self, task: EnhancedDownloadTask, priority: int):
        """Add task to appropriate priority queue"""
        if priority <= 2:
            self.high_priority_queue.put(task)
        elif priority <= 7:
            self.normal_priority_queue.put(task)
        else:
            self.low_priority_queue.put(task)
    
    def _add_to_scheduled_queue(self, task: EnhancedDownloadTask):
        """Add task to scheduled queue with execution time as priority"""
        next_time = task.schedule.get_next_execution_time()
        if next_time:
            # Use timestamp as priority (earlier = higher priority)
            priority = int(next_time.timestamp())
            scheduled_task = (priority, task)
            self.scheduled_queue.put(scheduled_task)
    
    def _add_to_waiting_queue(self, task: EnhancedDownloadTask):
        """Add task to waiting queue for condition checking"""
        self.waiting_queue.put(task)
    
    def _scheduler_loop(self):
        """Process scheduled downloads"""
        while self.running:
            try:
                if not self.scheduled_queue.empty():
                    priority, task = self.scheduled_queue.get_nowait()
                    
                    # Check if it's time to execute
                    execution_time = datetime.fromtimestamp(priority)
                    if datetime.now() >= execution_time:
                        # Move to appropriate queue
                        context = self._get_current_context()
                        if task.can_execute(context):
                            self._add_to_priority_queue(task, task.priority)
                        else:
                            self._add_to_waiting_queue(task)
                    else:
                        # Put back in queue
                        self.scheduled_queue.put((priority, task))
                
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Scheduler error: {e}")
                time.sleep(1)
    
    def _condition_checker_loop(self):
        """Check waiting downloads for condition fulfillment"""
        while self.running:
            try:
                waiting_tasks = []
                
                # Collect all waiting tasks
                while not self.waiting_queue.empty():
                    waiting_tasks.append(self.waiting_queue.get_nowait())
                
                # Check each task
                context = self._get_current_context()
                
                for task in waiting_tasks:
                    if task.can_execute(context):
                        self._add_to_priority_queue(task, task.priority)
                    else:
                        self.waiting_queue.put(task)
                
                time.sleep(5)  # Check conditions every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Condition checker error: {e}")
                time.sleep(5)
    
    def _queue_processor_loop(self):
        """Process download queues"""
        while self.running:
            try:
                with self.lock:
                    if len(self.active_downloads) >= self.max_concurrent_downloads:
                        time.sleep(0.1)
                        continue
                    
                    # Get next task (high priority first)
                    task = self._get_next_task()
                    
                    if task:
                        # Start download
                        self._start_download(task)
                
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Queue processor error: {e}")
                time.sleep(1)
    
    def _get_next_task(self) -> Optional[EnhancedDownloadTask]:
        """Get the next task to execute"""
        # Try high priority queue first
        if not self.high_priority_queue.empty():
            return self.high_priority_queue.get_nowait()
        
        # Then normal priority
        if not self.normal_priority_queue.empty():
            return self.normal_priority_queue.get_nowait()
        
        # Finally low priority
        if not self.low_priority_queue.empty():
            return self.low_priority_queue.get_nowait()
        
        return None
    
    def _start_download(self, task: EnhancedDownloadTask):
        """Start a download task"""
        # This would integrate with the AdvancedDownloadManager
        # For now, just track it
        self.active_downloads[task.task_id] = {
            'task': task,
            'status': 'downloading',
            'started_at': datetime.now()
        }
        
        self.logger.info(f"Started download {task.task_id}")
    
    def _get_current_context(self) -> Dict[str, Any]:
        """Get current context for condition evaluation"""
        return {
            'current_time': datetime.now(),
            'completed_downloads': self.completed_downloads.copy(),
            'failed_downloads': self.failed_downloads.copy(),
            'active_downloads': len(self.active_downloads),
            'available_bandwidth': self.bandwidth_monitor.get_available_bandwidth(),
            'queue_sizes': self._get_queue_sizes()
        }
    
    def _get_queue_sizes(self) -> Dict[str, int]:
        """Get current queue sizes"""
        return {
            'high': self.high_priority_queue.qsize(),
            'normal': self.normal_priority_queue.qsize(),
            'low': self.low_priority_queue.qsize(),
            'scheduled': self.scheduled_queue.qsize(),
            'waiting': self.waiting_queue.qsize()
        }
    
    def _update_queue_stats(self):
        """Update queue statistics"""
        self.stats['queue_sizes'] = self._get_queue_sizes()
    
    def complete_download(self, task_id: str):
        """Mark a download as completed"""
        with self.lock:
            if task_id in self.active_downloads:
                task_info = self.active_downloads.pop(task_id)
                self.completed_downloads.add(task_id)
                self.stats['total_completed'] += 1
                
                # Handle recurring downloads
                task = task_info['task']
                if task.schedule and task.schedule.type == ScheduleType.RECURRING:
                    task.schedule.parameters['last_execution'] = datetime.now()
                    self._add_to_scheduled_queue(task)
    
    def fail_download(self, task_id: str, error: str = ""):
        """Mark a download as failed"""
        with self.lock:
            if task_id in self.active_downloads:
                task_info = self.active_downloads.pop(task_id)
                task = task_info['task']
                
                # Try retry if available
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    self._add_to_priority_queue(task, task.priority + 1)  # Lower priority for retry
                    self.logger.info(f"Retrying download {task_id} (attempt {task.retry_count})")
                else:
                    self.failed_downloads.add(task_id)
                    self.stats['total_failed'] += 1
                    self.logger.error(f"Download {task_id} failed permanently: {error}")
    
    def pause_download(self, task_id: str):
        """Pause a download"""
        with self.lock:
            if task_id in self.active_downloads:
                task_info = self.active_downloads.pop(task_id)
                self.paused_downloads[task_id] = task_info
    
    def resume_download(self, task_id: str):
        """Resume a paused download"""
        with self.lock:
            if task_id in self.paused_downloads:
                task_info = self.paused_downloads.pop(task_id)
                task = task_info['task']
                self._add_to_priority_queue(task, task.priority)
    
    def cancel_download(self, task_id: str):
        """Cancel a download"""
        with self.lock:
            # Remove from active downloads
            self.active_downloads.pop(task_id, None)
            
            # Remove from paused downloads
            self.paused_downloads.pop(task_id, None)
            
            # Remove from queues (more complex, would need queue modification)
            # For now, just mark as failed
            self.failed_downloads.add(task_id)
    
    def get_queue_status(self) -> Dict:
        """Get current queue status"""
        with self.lock:
            return {
                'active_downloads': len(self.active_downloads),
                'paused_downloads': len(self.paused_downloads),
                'queue_sizes': self._get_queue_sizes(),
                'stats': self.stats.copy(),
                'max_concurrent': self.max_concurrent_downloads
            }
    
    def search_downloads(self, query: str, tags: Optional[List[str]] = None) -> List[Dict]:
        """Search downloads by URL, filename, or tags"""
        results = []
        
        # Search active downloads
        for task_id, info in self.active_downloads.items():
            task = info['task']
            if self._matches_search(task, query, tags):
                results.append({
                    'task_id': task_id,
                    'url': task.url,
                    'status': 'active',
                    'tags': task.tags
                })
        
        # Search paused downloads
        for task_id, info in self.paused_downloads.items():
            task = info['task']
            if self._matches_search(task, query, tags):
                results.append({
                    'task_id': task_id,
                    'url': task.url,
                    'status': 'paused',
                    'tags': task.tags
                })
        
        return results
    
    def _matches_search(self, task: EnhancedDownloadTask, query: str, tags: Optional[List[str]]) -> bool:
        """Check if task matches search criteria"""
        # Check URL or destination
        if query.lower() in task.url.lower() or query.lower() in task.destination.lower():
            return True
        
        # Check tags
        if tags:
            if any(tag in task.tags for tag in tags):
                return True
        
        return False

class BandwidthMonitor:
    """Monitor available bandwidth for conditional downloads"""
    
    def __init__(self):
        self.measurements = []
        self.measurement_window = 300  # 5 minutes
    
    def record_usage(self, bytes_per_second: float):
        """Record bandwidth usage"""
        now = time.time()
        self.measurements.append((now, bytes_per_second))
        
        # Clean old measurements
        cutoff = now - self.measurement_window
        self.measurements = [(t, bps) for t, bps in self.measurements if t > cutoff]
    
    def get_average_usage(self) -> float:
        """Get average bandwidth usage"""
        if not self.measurements:
            return 0
        
        total_bps = sum(bps for _, bps in self.measurements)
        return total_bps / len(self.measurements)
    
    def get_available_bandwidth(self, total_bandwidth: float = float('inf')) -> float:
        """Get estimated available bandwidth"""
        if total_bandwidth == float('inf'):
            return float('inf')
        
        used = self.get_average_usage()
        return max(0, total_bandwidth - used)

# Factory functions for creating common conditions and schedules

def create_time_condition(start_time: Optional[str] = None,
                         end_time: Optional[str] = None,
                         allowed_hours: Optional[List[int]] = None,
                         blocked_days: Optional[List[int]] = None) -> DownloadCondition:
    """Create a time-based download condition"""
    params = {}
    if start_time:
        params['start_time'] = start_time
    if end_time:
        params['end_time'] = end_time
    if allowed_hours:
        params['allowed_hours'] = allowed_hours
    if blocked_days:
        params['blocked_days'] = blocked_days
    
    return DownloadCondition(
        type=DownloadConditionType.TIME_BASED,
        parameters=params,
        description=f"Time condition: {params}"
    )

def create_size_condition(min_size: Optional[int] = None,
                         max_size: Optional[int] = None) -> DownloadCondition:
    """Create a size-based download condition"""
    params = {}
    if min_size:
        params['min_size'] = min_size
    if max_size:
        params['max_size'] = max_size
    
    return DownloadCondition(
        type=DownloadConditionType.SIZE_BASED,
        parameters=params,
        description=f"Size condition: {params}"
    )

def create_dependency_condition(requires_completed: Optional[List[str]] = None,
                              blocks_if_failed: Optional[List[str]] = None) -> DownloadCondition:
    """Create a dependency-based download condition"""
    params = {}
    if requires_completed:
        params['requires_completed'] = requires_completed
    if blocks_if_failed:
        params['blocks_if_failed'] = blocks_if_failed
    
    return DownloadCondition(
        type=DownloadConditionType.DEPENDENCY_BASED,
        parameters=params,
        description=f"Dependency condition: {params}"
    )

def create_immediate_schedule() -> ScheduleInfo:
    """Create an immediate schedule"""
    return ScheduleInfo(
        type=ScheduleType.IMMEDIATE,
        parameters={}
    )

def create_delayed_schedule(delay_seconds: int) -> ScheduleInfo:
    """Create a delayed schedule"""
    return ScheduleInfo(
        type=ScheduleType.DELAYED,
        parameters={'delay_seconds': delay_seconds}
    )

def create_recurring_schedule(interval_seconds: int) -> ScheduleInfo:
    """Create a recurring schedule"""
    return ScheduleInfo(
        type=ScheduleType.RECURRING,
        parameters={'interval_seconds': interval_seconds}
    )