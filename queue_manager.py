#!/usr/bin/env python3
"""
Queue Manager for NGK's DL Manager V2.7
Handles download queue with priority, concurrency control, state management, and persistence
Universal Agent Ruleset: ASCII-only, no placeholders, engine-only
"""

import threading
import time
import json
import os
import random
import math
from enum import Enum
from datetime import datetime, timedelta
from urllib.parse import urlparse
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict

# STEP 5: Policy Engine Integration (Policy Layer Only)
try:
    from policy_engine import get_policy_engine, PolicyDecision
    POLICY_ENGINE_AVAILABLE = True
except ImportError:
    POLICY_ENGINE_AVAILABLE = False
    PolicyDecision = None


class TaskState(Enum):
    """Task state enumeration with valid transitions"""
    PENDING = "PENDING"
    STARTING = "STARTING"
    DOWNLOADING = "DOWNLOADING"
    PAUSED = "PAUSED"
    RETRY_WAIT = "RETRY_WAIT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class QueueTask:
    """Download task model"""
    task_id: str
    url: str
    destination: str
    priority: int
    state: TaskState
    created_at: str
    updated_at: str
    mode: str = "auto"
    connections_used: int = 1
    error: Optional[str] = None
    progress: float = 0.0
    speed_bps: float = 0.0
    resume_state_path: Optional[str] = None
    history_id: Optional[str] = None
    # V2.8 retry/backoff fields
    attempt: int = 0
    max_attempts: int = 3
    next_eligible_at: Optional[str] = None
    last_error: Optional[str] = None
    # V2.8 fairness fields
    host: Optional[str] = None
    effective_priority: int = 5
    # Phase 10.4: Type-specific options for unified pipeline
    type_options: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize default values after dataclass creation"""
        if self.type_options is None:
            self.type_options = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['state'] = self.state.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueTask':
        """Create from dictionary"""
        data = data.copy()
        data['state'] = TaskState(data['state'])
        return cls(**data)


class QueueManager:
    """Download queue manager with concurrency control"""
    
    def __init__(self, max_active_downloads: int = 2, persist_queue: bool = False, 
                 queue_state_path: str = "data/runtime/queue_state.json",
                 # V2.8 retry/backoff config
                 retry_enabled: bool = False, retry_max_attempts: int = 3,
                 retry_backoff_base_s: float = 2.0, retry_backoff_max_s: float = 300.0,
                 retry_jitter_mode: str = "none",
                 # V2.8 fairness config  
                 priority_aging_enabled: bool = False, priority_aging_step: int = 1,
                 priority_aging_interval_s: float = 60.0,
                 # V2.8 per-host config
                 per_host_enabled: bool = False, per_host_max_active: int = 1,
                 # V2.9 event bus
                 event_bus=None):
        self.max_active_downloads = max_active_downloads
        self.persist_queue = persist_queue
        self.queue_state_path = queue_state_path
        self.persist_history = True  # Default from config
        # V2.8 retry/backoff config
        self.retry_enabled = retry_enabled
        self.retry_max_attempts = retry_max_attempts
        self.retry_backoff_base_s = retry_backoff_base_s
        self.retry_backoff_max_s = retry_backoff_max_s
        self.retry_jitter_mode = retry_jitter_mode
        # V2.8 fairness config
        self.priority_aging_enabled = priority_aging_enabled
        self.priority_aging_step = priority_aging_step
        self.priority_aging_interval_s = priority_aging_interval_s
        # V2.8 per-host config
        self.per_host_enabled = per_host_enabled
        self.per_host_max_active = per_host_max_active
        # V2.9 event bus
        self.event_bus = event_bus
        # Core state
        self.tasks: Dict[str, QueueTask] = {}
        self.active_workers: Dict[str, threading.Thread] = {}
        self.cancel_events: Dict[str, threading.Event] = {}
        self.lock = threading.RLock()
        self.scheduler_running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.downloader_func: Optional[Callable] = None
        self.history: List[Dict[str, Any]] = []
        # V2.9 progress throttling (avoid UI spam)
        self._last_progress_emit: Dict[str, float] = {}
        self._progress_throttle_interval = 0.5  # seconds
        
        # Load persisted state if enabled
        if self.persist_queue:
            self._load_persisted_state_on_startup()
        
    def _load_persisted_state_on_startup(self):
        """Load persisted state during queue manager initialization with recovery"""
        if not os.path.exists(self.queue_state_path):
            import logging
            logger = logging.getLogger("queue")
            logger.info(f"QUEUEPERSIST | LOAD_OK | tasks=0 | path={self.queue_state_path} | reason=no_state_file")
            return
            
        try:
            from queue_persistence import load_queue_state, apply_crash_recovery_rules, PersistenceError
            
            # Load state from disk
            state = load_queue_state(self.queue_state_path)
            
            # Apply crash recovery rules
            recovered_state = apply_crash_recovery_rules(state)
            
            # Load tasks and apply recovery
            loaded_count = 0
            resumable_count = 0
            restarting_count = 0
            
            import logging
            logger = logging.getLogger("queue")
            
            for task_data in recovered_state["tasks"]:
                task = QueueTask(
                    task_id=task_data["task_id"],
                    url=task_data["url"],
                    destination=task_data["destination"],
                    priority=task_data["priority"],
                    state=TaskState(task_data["state"]),
                    created_at=task_data["created_at"],
                    updated_at=task_data["updated_at"],
                    mode=task_data["mode"],
                    connections_used=task_data["connections_used"],
                    error=task_data.get("error"),
                    progress=task_data.get("progress", 0.0),
                    speed_bps=task_data.get("speed_bps", 0.0),
                    resume_state_path=task_data.get("resume_state_path"),
                    history_id=task_data.get("history_id"),
                    # V2.8 fields with defaults
                    attempt=task_data.get("attempt", 0),
                    max_attempts=task_data.get("max_attempts", self.retry_max_attempts),
                    next_eligible_at=task_data.get("next_eligible_at"),
                    last_error=task_data.get("last_error"),
                    host=task_data.get("host"),
                    effective_priority=task_data.get("effective_priority", task_data["priority"]),
                    # Phase 10.4: Type-specific options for unified pipeline
                    type_options=task_data.get("type_options", {})
                )
                
                self.tasks[task.task_id] = task
                self.cancel_events[task.task_id] = threading.Event()
                loaded_count += 1
                
                # Log recovery action taken per task
                if task.state == TaskState.PAUSED and task_data["state"] in ["STARTING", "DOWNLOADING"]:
                    logger.info(f"RECOVERY | TASK | task_id={task.task_id} | from={task_data['state']} -> PAUSED | action=resume")
                    resumable_count += 1
                elif task.state == TaskState.PENDING and task_data["state"] == "RETRY_WAIT":
                    logger.info(f"RECOVERY | TASK | task_id={task.task_id} | from=RETRY_WAIT -> PENDING | action=restart")
                    restarting_count += 1
                else:
                    logger.info(f"RECOVERY | TASK | task_id={task.task_id} | from={task_data['state']} -> {task.state.value} | action=skip")
                
                # Add terminal tasks to history
                if task.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
                    self._add_to_history(task)
            
            logger.info(f"QUEUEPERSIST | LOAD_OK | tasks={loaded_count} | path={self.queue_state_path}")
            logger.info(f"RECOVERY | SUMMARY | loaded={loaded_count} | resumable={resumable_count} | restarting={restarting_count}")
            
        except Exception as e:
            import logging
            logger = logging.getLogger("queue")
            logger.error(f"QUEUEPERSIST | LOAD_FAIL | error={str(e)}")
            # Don't fail startup, just log and continue with empty queue
            logger.warning(f"Starting with empty queue due to persistence load failure")
        
    def _log_task(self, level: int, task_id: str, msg: str, **extra):
        """Structured task logging with consistent format"""
        import logging
        logger = logging.getLogger("queue")
        extra_str = " | ".join(f"{k}={v}" for k, v in extra.items()) if extra else ""
        full_msg = f"TASK {task_id} | {msg}"
        if extra_str:
            full_msg += f" | {extra_str}"
        logger.log(level, full_msg)
        
    def _log_scheduler(self, level: int, msg: str, **extra):
        """Structured scheduler logging"""
        import logging
        logger = logging.getLogger("queue")
        extra_str = " | ".join(f"{k}={v}" for k, v in extra.items()) if extra else ""
        full_msg = f"SCHEDULER | {msg}"
        if extra_str:
            full_msg += f" | {extra_str}"
        logger.log(level, full_msg)
        
    def set_downloader(self, downloader_func: Callable):
        """Set the downloader function to use"""
        self.downloader_func = downloader_func
        
    def enqueue(self, task_id: str, url: str, destination: str, 
               priority: int = 5, mode: str = "auto", connections: int = 1, **type_options) -> bool:
        """Enqueue a download task with structured logging, policy gates, and type-specific options (Phase 10.4)"""
        with self.lock:
            if task_id in self.tasks:
                self._log_task(30, task_id, "DUPLICATE ENQUEUE REJECTED", priority=priority)  # WARNING
                return False
                
            # STEP 5: Policy Gate - Enqueue Decision
            if POLICY_ENGINE_AVAILABLE:
                try:
                    policy_engine = get_policy_engine()
                    decision = policy_engine.check_enqueue_policy(task_id, url, destination, 
                                                                 priority=priority, mode=mode, connections=connections)
                    policy_engine.apply_policy_decision(decision, task_id)
                    
                    if decision.action == 'DENY':
                        self._log_task(30, task_id, "POLICY_DENIED", reason=decision.reason)  # WARNING
                        return False
                except Exception as e:
                    # Policy errors should not break enqueue - log and continue
                    import logging
                    logging.getLogger("policy").error(f"POLICY | ERROR | enqueue_check | task_id={task_id} | error={str(e)}")
                
            now = datetime.now().isoformat()
            
            # V2.8: Extract host from URL
            host = self._extract_host(url)
            
            task = QueueTask(
                task_id=task_id,
                url=url,
                destination=destination,
                priority=priority,
                state=TaskState.PENDING,
                created_at=now,
                updated_at=now,
                mode=mode,
                connections_used=connections,
                # V2.8 fields
                attempt=0,
                max_attempts=self.retry_max_attempts,
                host=host,
                effective_priority=priority,
                # Phase 10.4: Store type-specific options for unified pipeline
                type_options=type_options
            )
            
            self.tasks[task_id] = task
            self.cancel_events[task_id] = threading.Event()
            
            # Structured logging with key details
            url_display = url[:50] + "..." if len(url) > 50 else url
            self._log_task(20, task_id, "CREATED", priority=priority, url=url_display, 
                          mode=mode, connections=connections, queue_size=len(self.tasks))  # INFO
            
            # V2.9: Emit TASK_ADDED event
            self._emit_task_event("TASK_ADDED", task_id)
            
            # Persist state if enabled
            self._persist_state_if_enabled()
            
            return True
    
    def start_scheduler(self):
        """Start the scheduler thread with logging"""
        with self.lock:
            if not self.scheduler_running:
                self.scheduler_running = True
                self.stop_event.clear()
                self.scheduler_thread = threading.Thread(target=self._scheduler_loop)
                self.scheduler_thread.daemon = True
                self.scheduler_thread.start()
                self._log_scheduler(20, "STARTED", max_active=self.max_active_downloads, 
                                  retry_enabled=self.retry_enabled)  # INFO
    
    def stop_scheduler(self):
        """Stop the scheduler thread"""
        with self.lock:
            self.scheduler_running = False
            self.stop_event.set()
            
            # Cancel all active downloads
            for task_id in list(self.active_workers.keys()):
                self._cancel_worker(task_id)
                
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5.0)
    
    def _scheduler_loop(self):
        """Main scheduler loop with decision visibility"""
        self._log_scheduler(20, "LOOP_STARTED", thread=threading.current_thread().name)  # INFO
        
        while self.scheduler_running and not self.stop_event.is_set():
            try:
                self._process_queue()
                time.sleep(0.1)
            except Exception as e:
                print(f"Scheduler error: {e}")
                time.sleep(1.0)
    
    def _process_queue(self):
        """Process eligible tasks with detailed decision logging"""
        with self.lock:
            # Clean up completed workers
            for task_id in list(self.active_workers.keys()):
                if not self.active_workers[task_id].is_alive():
                    del self.active_workers[task_id]
            
            # Get current state for logging
            active_count = len(self.active_workers)
            pending_tasks = [t for t in self.tasks.values() if t.state == TaskState.PENDING]
            total_tasks = len(self.tasks)
            
            # ALWAYS log queue processing state for debugging (every 30 seconds)
            current_time = time.time()
            if not hasattr(self, '_last_debug_log') or current_time - self._last_debug_log > 30:
                self._last_debug_log = current_time
                all_task_states = {state.value: len([t for t in self.tasks.values() if t.state == state]) 
                                 for state in TaskState}
                self._log_scheduler(20, "DEBUG_QUEUE_STATE", active=active_count, pending=len(pending_tasks), 
                                  total=total_tasks, max_active=self.max_active_downloads, 
                                  states=str(all_task_states))  # INFO
            
            # Log queue processing state for debugging
            if pending_tasks:
                self._log_scheduler(20, "QUEUE_STATE", active=active_count, pending=len(pending_tasks), 
                                  max_active=self.max_active_downloads)  # INFO
            
            # Check global concurrency limit
            if active_count >= self.max_active_downloads:
                if pending_tasks:  # Only log if there's work waiting
                    self._log_scheduler(10, "MAX_ACTIVE_REACHED", active=active_count, 
                                      waiting=len(pending_tasks), max_active=self.max_active_downloads)  # DEBUG
                return
                
            # Get eligible tasks (includes retry-wait timeout processing)
            eligible_tasks = self._get_eligible_tasks()
            
            if not eligible_tasks and pending_tasks:
                self._log_scheduler(30, "NO_ELIGIBLE_TASKS", pending=len(pending_tasks))  # WARNING
                return
            elif not eligible_tasks:
                return
                
            # Log scheduler decision making
            self._log_scheduler(20, "PROCESSING", active=active_count, 
                              pending=len(pending_tasks), eligible=len(eligible_tasks))  # INFO
                
            # Find next task that can start (respecting per-host limits)
            for task in eligible_tasks:
                if self._can_start_task_for_host(task.host):
                    if len(self.active_workers) < self.max_active_downloads:
                        self._start_worker(task)
                        break
    
    def _start_worker(self, task: QueueTask):
        """Start a worker thread for a task with structured logging and policy gates"""
        # STEP 5: Policy Gate - Start Decision  
        if POLICY_ENGINE_AVAILABLE:
            try:
                policy_engine = get_policy_engine()
                decision = policy_engine.check_start_policy(task.task_id, task.url)
                policy_engine.apply_policy_decision(decision, task.task_id)
                
                if decision.action == 'DENY':
                    self._log_task(30, task.task_id, "POLICY_START_DENIED", reason=decision.reason)  # WARNING
                    task.state = TaskState.FAILED
                    task.error = f"Policy denied start: {decision.reason}"
                    task.updated_at = datetime.now().isoformat()
                    self._persist_state_if_enabled()
                    return
            except Exception as e:
                # Policy errors should not break start - log and continue
                import logging
                logging.getLogger("policy").error(f"POLICY | ERROR | start_check | task_id={task.task_id} | error={str(e)}")
        
        task.state = TaskState.STARTING
        task.updated_at = datetime.now().isoformat()
        task.attempt += 1  # V2.8: Increment attempt counter
        
        worker = threading.Thread(target=self._worker_thread, args=(task.task_id,))
        worker.daemon = True
        self.active_workers[task.task_id] = worker
        
        # Log task start with context
        self._log_task(20, task.task_id, "STARTED", priority=task.priority, 
                      attempt=task.attempt, worker=worker.name, 
                      active_count=len(self.active_workers))  # INFO
        
        worker.start()
    
    def _worker_thread(self, task_id: str):
        """Worker thread for downloading"""
        try:
            task = self.tasks[task_id]
            cancel_event = self.cancel_events[task_id]
            
            # Update state to DOWNLOADING
            with self.lock:
                task.state = TaskState.DOWNLOADING
                task.updated_at = datetime.now().isoformat()
            
            if not self.downloader_func:
                raise RuntimeError("No downloader function set")
            
            # Create progress callback
            def progress_callback(progress_info):
                with self.lock:
                    if task_id in self.tasks and isinstance(progress_info, dict):
                        # Extract progress percentage
                        progress_str = progress_info.get('progress', '0%')
                        if isinstance(progress_str, str) and progress_str.endswith('%'):
                            try:
                                progress_val = float(progress_str.replace('%', ''))
                            except ValueError:
                                progress_val = 0.0
                        else:
                            progress_val = 0.0
                        
                        self.tasks[task_id].progress = progress_val
                        
                        # Parse speed string to bytes/sec
                        speed_str = progress_info.get('speed', '0 B/s')
                        speed_bps = 0.0
                        if isinstance(speed_str, str):
                            try:
                                # Parse speeds like "1.5 MB/s", "500 KB/s", "1024 B/s"
                                speed_parts = speed_str.replace('B/s', '').strip().split()
                                if len(speed_parts) >= 2:
                                    value = float(speed_parts[0])
                                    unit = speed_parts[1].upper()
                                    if unit == 'MB':
                                        speed_bps = value * 1024 * 1024
                                    elif unit == 'KB':
                                        speed_bps = value * 1024
                                    else:  # Assume bytes
                                        speed_bps = value
                                elif len(speed_parts) == 1:
                                    speed_bps = float(speed_parts[0])  # Just a number
                            except (ValueError, IndexError):
                                speed_bps = 0.0
                        
                        self.tasks[task_id].speed_bps = speed_bps
                        self.tasks[task_id].updated_at = datetime.now().isoformat()
            
            # Execute download
            failure_reason = None
            try:
                success = self.downloader_func(
                    task.url,
                    task.destination,
                    task_id=task_id,
                    progress_callback=progress_callback,
                    max_connections=task.connections_used,
                    mode=task.mode,
                    cancel_event=cancel_event,
                )
                if not success:
                    failure_reason = "Download returned False"
                self._log_task(20, task_id, "DOWNLOAD_COMPLETE", success=success)  # INFO
            except Exception as download_error:
                success = False
                failure_reason = str(download_error)
                self._log_task(40, task_id, "DOWNLOAD_ERROR", error=failure_reason)  # ERROR
            
            # Update final state with V2.8 retry logic
            with self.lock:
                start_time = datetime.fromisoformat(task.created_at) if hasattr(task, 'created_at') else datetime.now()
                duration = (datetime.now() - start_time).total_seconds()
                
                if cancel_event.is_set():
                    task.state = TaskState.CANCELLED
                    self._log_task(30, task_id, "CANCELLED", duration=f"{duration:.2f}s")  # WARNING
                elif success:
                    task.state = TaskState.COMPLETED
                    task.progress = 100.0
                    task.speed_bps = 0.0  # Clear speed on completion
                    self._handle_task_success(task)
                    self._log_task(20, task_id, "COMPLETED", duration=f"{duration:.2f}s", 
                                  progress="100%")  # INFO
                else:
                    # Handle failure with retry logic
                    if failure_reason is None:
                        failure_reason = "Download failed"
                    self._handle_task_failure(task, failure_reason)
                    if task.state == TaskState.RETRY_WAIT:
                        self._log_task(30, task_id, "RETRY_WAIT", duration=f"{duration:.2f}s", 
                                      error=failure_reason)  # WARNING
                    else:
                        self._log_task(40, task_id, "FAILED", duration=f"{duration:.2f}s", 
                                      error=failure_reason)  # ERROR
                
                task.updated_at = datetime.now().isoformat()
                
                # Only add to history if in terminal state
                if task.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
                    self._add_to_history(task)
                
                # V2.9: Emit events for all state changes
                self._emit_task_event("TASK_UPDATED", task_id)
                if task.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
                    self._emit_queue_status_event()
                
                # Persist state if enabled
                self._persist_state_if_enabled()
                
        except Exception as e:
            with self.lock:
                task = self.tasks[task_id]
                start_time = datetime.fromisoformat(task.created_at) if hasattr(task, 'created_at') else datetime.now()
                duration = (datetime.now() - start_time).total_seconds()
                
                # Handle exception with retry logic
                self._handle_task_failure(task, str(e))
                self._log_task(40, task_id, "EXCEPTION", duration=f"{duration:.2f}s", 
                              error=str(e)[:100])  # ERROR - truncate long errors
                task.updated_at = datetime.now().isoformat()
                
                # Only add to history if in terminal state
                if task.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
                    self._add_to_history(task)
                
                # V2.9: Emit events for exception handling
                self._emit_task_event("TASK_UPDATED", task_id)
                if task.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
                    self._emit_queue_status_event()
                
                # Persist state if enabled
                self._persist_state_if_enabled()
    
    def pause_task(self, task_id: str) -> bool:
        """Pause a specific task"""
        with self.lock:
            if task_id not in self.tasks:
                return False
                
            task = self.tasks[task_id]
            if task.state == TaskState.DOWNLOADING:
                self._cancel_worker(task_id)
                task.state = TaskState.PAUSED
                task.updated_at = datetime.now().isoformat()
                
                # V2.9: Emit TASK_UPDATED event
                self._emit_task_event("TASK_UPDATED", task_id)
                
                # Persist state if enabled
                self._persist_state_if_enabled()
                
                return True
                
            return False
    
    def resume_task(self, task_id: str) -> bool:
        """Resume a paused task"""
        with self.lock:
            if task_id not in self.tasks:
                return False
                
            task = self.tasks[task_id]
            if task.state == TaskState.PAUSED:
                task.state = TaskState.PENDING
                task.updated_at = datetime.now().isoformat()
                
                # V2.9: Emit TASK_UPDATED event
                self._emit_task_event("TASK_UPDATED", task_id)
                
                # Persist state if enabled
                self._persist_state_if_enabled()
                
                return True
                
            return False
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task"""
        with self.lock:
            if task_id not in self.tasks:
                return False
                
            task = self.tasks[task_id]
            
            if task.state in [TaskState.DOWNLOADING, TaskState.STARTING]:
                self._cancel_worker(task_id)
                
            if task.state not in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
                task.state = TaskState.CANCELLED
                task.updated_at = datetime.now().isoformat()
                self._add_to_history(task)
                
                # V2.9: Emit TASK_UPDATED and QUEUE_STATUS events
                self._emit_task_event("TASK_UPDATED", task_id)
                self._emit_queue_status_event()
                
                # Persist state if enabled
                self._persist_state_if_enabled()
                
            return True
    
    def _cancel_worker(self, task_id: str):
        """Cancel a worker thread"""
        if task_id in self.cancel_events:
            self.cancel_events[task_id].set()
        
        if task_id in self.active_workers:
            worker = self.active_workers[task_id]
            # Don't join here to avoid deadlock, let scheduler clean up
    
    def pause_all(self) -> int:
        """Pause all active downloads"""
        count = 0
        with self.lock:
            for task_id, task in self.tasks.items():
                if task.state == TaskState.DOWNLOADING:
                    if self.pause_task(task_id):
                        count += 1
        return count
    
    def resume_all(self) -> int:
        """Resume all paused downloads"""
        count = 0
        with self.lock:
            for task_id, task in self.tasks.items():
                if task.state == TaskState.PAUSED:
                    if self.resume_task(task_id):
                        count += 1
        return count
    
    def get_status(self) -> Dict[str, Any]:
        """Get queue status"""
        with self.lock:
            state_counts = {}
            for state in TaskState:
                state_counts[state.value] = 0
                
            for task in self.tasks.values():
                state_counts[task.state.value] += 1
                
            return {
                'total_tasks': len(self.tasks),
                'active_downloads': len(self.active_workers),
                'max_active_downloads': self.max_active_downloads,
                'state_counts': state_counts,
                'scheduler_running': self.scheduler_running
            }
    
    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all tasks"""
        with self.lock:
            return [task.to_dict() for task in self.tasks.values()]
    
    def _add_to_history(self, task: QueueTask):
        """Add task to history if in terminal state"""
        if task.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
            # Check if task already in history and update, or add new
            existing_idx = None
            for i, entry in enumerate(self.history):
                if entry['task_id'] == task.task_id:
                    existing_idx = i
                    break
            
            history_entry = task.to_dict()
            
            if existing_idx is not None:
                self.history[existing_idx] = history_entry
            else:
                self.history.append(history_entry)
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get download history"""
        with self.lock:
            return self.history.copy()
    
    def _persist_state_if_enabled(self):
        """Persist queue state if persistence is enabled"""
        if self.persist_queue:
            try:
                from queue_persistence import save_queue_state
                save_queue_state(self, self.queue_state_path)
                import logging
                logger = logging.getLogger("queue")
                logger.info(f"QUEUEPERSIST | SAVE_OK | tasks={len(self.tasks)} | path={self.queue_state_path}")
            except Exception as e:
                import logging
                logger = logging.getLogger("queue")
                logger.error(f"QUEUEPERSIST | SAVE_FAIL | error={str(e)}")
                # FAIL LOUDLY when persistence is enabled
                raise RuntimeError(f"Queue persistence failed: {e}")
    
    def _extract_host(self, url: str) -> Optional[str]:
        """Extract hostname from URL"""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower() if parsed.netloc else None
        except Exception:
            return None
    
    def _is_retryable_error(self, error: str) -> bool:
        """Determine if error is retryable"""
        if not error:
            return False
        error_lower = error.lower()
        # Network/temporary errors are retryable
        retryable_patterns = [
            "timeout", "connection", "network", "temporary", "503", "502", "504"
        ]
        return any(pattern in error_lower for pattern in retryable_patterns)
    
    def _calculate_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter"""
        if attempt <= 0:
            return 0.0
        
        # Exponential backoff: base^(attempt-1)
        delay = self.retry_backoff_base_s ** (attempt - 1)
        delay = min(delay, self.retry_backoff_max_s)
        
        # Apply jitter if enabled
        if self.retry_jitter_mode == "full":
            # Full jitter: random [0, delay]
            delay = random.uniform(0, delay)
        elif self.retry_jitter_mode == "equal":
            # Equal jitter: delay/2 + random [0, delay/2]
            delay = delay * 0.5 + random.uniform(0, delay * 0.5)
        
        return delay
    
    def _update_priority_aging(self):
        """Update effective priorities based on aging"""
        if not self.priority_aging_enabled:
            return
        
        now = datetime.now()
        for task in self.tasks.values():
            if task.state == TaskState.PENDING:
                created = datetime.fromisoformat(task.created_at)
                age_seconds = (now - created).total_seconds()
                age_intervals = int(age_seconds / self.priority_aging_interval_s)
                priority_boost = age_intervals * self.priority_aging_step
                task.effective_priority = min(task.priority + priority_boost, 10)
    
    def _get_active_count_by_host(self) -> Dict[str, int]:
        """Get count of active downloads by host"""
        host_counts = {}
        for task in self.tasks.values():
            if task.state == TaskState.DOWNLOADING and task.host:
                host_counts[task.host] = host_counts.get(task.host, 0) + 1
        return host_counts
    
    def _can_start_task_for_host(self, host: Optional[str]) -> bool:
        """Check if we can start another task for the given host"""
        if not self.per_host_enabled or not host:
            return True
        
        host_counts = self._get_active_count_by_host()
        current_count = host_counts.get(host, 0)
        return current_count < self.per_host_max_active
    
    def _get_eligible_tasks(self) -> List[QueueTask]:
        """Get tasks eligible for execution with V2.8 filtering"""
        eligible = []
        now = datetime.now()
        
        for task in self.tasks.values():
            if task.state == TaskState.PENDING:
                eligible.append(task)
            elif task.state == TaskState.RETRY_WAIT:
                # Check if retry wait period has elapsed
                if task.next_eligible_at:
                    eligible_time = datetime.fromisoformat(task.next_eligible_at)
                    if now >= eligible_time:
                        # Transition RETRY_WAIT -> PENDING
                        task.state = TaskState.PENDING
                        task.updated_at = now.isoformat()
                        eligible.append(task)
        
        # Update priority aging
        self._update_priority_aging()
        
        # Sort by effective priority (higher first), then by created_at (FIFO)
        eligible.sort(key=lambda t: (-t.effective_priority, t.created_at))
        
        return eligible
    
    def _handle_task_failure(self, task: QueueTask, error_msg: str):
        """Handle task failure with V2.8 retry logic and policy gates"""
        task.last_error = error_msg
        
        import logging
        logger = logging.getLogger("queue")
        
        # STEP 5: Policy Gate - Retry Decision
        retry_allowed_by_policy = True
        if POLICY_ENGINE_AVAILABLE:
            try:
                policy_engine = get_policy_engine()
                decision = policy_engine.check_retry_policy(task.task_id, task.attempt, task.max_attempts, error_msg)
                policy_engine.apply_policy_decision(decision, task.task_id)
                
                if decision.action == 'DENY':
                    retry_allowed_by_policy = False
                    logger.info(f"POLICY | RETRY_DENIED | task_id={task.task_id} | reason={decision.reason}")
            except Exception as e:
                # Policy errors should not break retry logic - log and continue
                logger.error(f"POLICY | ERROR | retry_check | task_id={task.task_id} | error={str(e)}")
        
        # Check if retry is enabled and we have attempts left (with policy override)
        if (retry_allowed_by_policy and 
            self.retry_enabled and 
            task.attempt < task.max_attempts and
            self._is_retryable_error(error_msg)):
            
            # Calculate backoff delay
            delay = self._calculate_backoff_delay(task.attempt)
            next_time = datetime.now() + timedelta(seconds=delay)
            
            # Transition to RETRY_WAIT
            task.state = TaskState.RETRY_WAIT
            task.next_eligible_at = next_time.isoformat()
            
            # Log retry scheduling
            logger.info(f"RETRY | SCHEDULED | task_id={task.task_id} | attempt={task.attempt}/{task.max_attempts} | in={delay:.1f}s | reason={error_msg[:50]}")
            
        else:
            # No more retries - final failure
            task.state = TaskState.FAILED
            task.error = error_msg
            
            if self.retry_enabled and task.attempt >= task.max_attempts:
                # Exhausted retries
                logger.info(f"RETRY | EXHAUSTED | task_id={task.task_id} | attempts={task.attempt} | final_error={error_msg[:50]}")
            else:
                # Not retryable or retries disabled
                logger.info(f"RETRY | NOT_RETRYABLE | task_id={task.task_id} | error={error_msg[:50]}")
    
    def _handle_task_success(self, task: QueueTask):
        """Handle task success with retry reset logging"""
        import logging
        logger = logging.getLogger("queue")
        
        if task.attempt > 1:
            # This task succeeded after previous failures
            logger.info(f"RETRY | RESET | task_id={task.task_id} | reason=success")
    
    @classmethod
    def restore_from_disk(cls, path: str) -> 'QueueManager':
        """
        Restore QueueManager from persisted state with crash recovery
        
        Args:
            path: Path to queue state file
            
        Returns:
            QueueManager instance with restored state
        """
        from queue_persistence import load_queue_state, apply_crash_recovery_rules, PersistenceError
        
        try:
            # Load state from disk
            state = load_queue_state(path)
            
            # Apply crash recovery rules
            recovered_state = apply_crash_recovery_rules(state)
            
            # Create new queue manager
            config = recovered_state["config_snapshot"]
            queue_mgr = cls(
                max_active_downloads=config["max_active_downloads"],
                persist_queue=config["persist_queue"],
                queue_state_path=path
            )
            queue_mgr.persist_history = config["persist_history"]
            
            # Restore tasks
            for task_data in recovered_state["tasks"]:
                task = QueueTask(
                    task_id=task_data["task_id"],
                    url=task_data["url"],
                    destination=task_data["destination"],
                    priority=task_data["priority"],
                    state=TaskState(task_data["state"]),
                    created_at=task_data["created_at"],
                    updated_at=task_data["updated_at"],
                    mode=task_data["mode"],
                    connections_used=task_data["connections_used"],
                    error=task_data.get("error"),
                    progress=task_data.get("progress", 0.0),
                    speed_bps=task_data.get("speed_bps", 0.0),
                    resume_state_path=task_data.get("resume_state_path"),
                    history_id=task_data.get("history_id"),
                    # V2.8 fields with defaults
                    attempt=task_data.get("attempt", 0),
                    max_attempts=task_data.get("max_attempts", 3),
                    next_eligible_at=task_data.get("next_eligible_at"),
                    last_error=task_data.get("last_error"),
                    host=task_data.get("host"),
                    effective_priority=task_data.get("effective_priority", task_data["priority"])
                )
                
                queue_mgr.tasks[task.task_id] = task
                queue_mgr.cancel_events[task.task_id] = threading.Event()
                
                # Add terminal tasks to history
                if task.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
                    queue_mgr._add_to_history(task)
            
            return queue_mgr
            
        except PersistenceError as e:
            raise RuntimeError(f"Failed to restore queue from disk: {e}")
    
    def clear_persisted_state(self):
        """Clear persisted state file"""
        if os.path.exists(self.queue_state_path):
            os.remove(self.queue_state_path)
    
    # V2.9 UI Contract and Event Bus Methods
    
    def _emit_task_event(self, event_type: str, task_id: str, throttle_progress: bool = False):
        """Emit task event with validated snapshot"""
        if not self.event_bus:
            return
            
        task = self.tasks.get(task_id)
        if not task:
            return
            
        # Progress throttling to avoid UI spam
        if throttle_progress and event_type == "TASK_UPDATED":
            import time
            now = time.time()
            last_emit = self._last_progress_emit.get(task_id, 0)
            if now - last_emit < self._progress_throttle_interval:
                return
            self._last_progress_emit[task_id] = now
        
        try:
            from ui_contract import build_task_snapshot
            snapshot = build_task_snapshot(task)
            self.event_bus.emit(event_type, snapshot)
        except Exception:
            # Don't let event emission break core functionality
            pass
    
    def _emit_queue_status_event(self):
        """Emit queue status update event"""
        if not self.event_bus:
            return
            
        try:
            from ui_contract import build_queue_status_snapshot
            snapshot = build_queue_status_snapshot(self)
            self.event_bus.emit("QUEUE_STATUS", snapshot)
        except Exception:
            # Don't let event emission break core functionality
            pass
    
    def get_task_snapshot(self, task_id: str) -> Dict[str, Any]:
        """Get validated snapshot for a specific task"""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                raise KeyError(f"Task {task_id} not found")
            
            from ui_contract import build_task_snapshot
            return build_task_snapshot(task)
    
    def list_task_snapshots(self) -> List[Dict[str, Any]]:
        """Get validated snapshots for all tasks"""
        with self.lock:
            from ui_contract import build_task_snapshot
            snapshots = []
            for task in self.tasks.values():
                try:
                    snapshot = build_task_snapshot(task)
                    snapshots.append(snapshot)
                except Exception:
                    # Skip invalid tasks
                    continue
            return snapshots