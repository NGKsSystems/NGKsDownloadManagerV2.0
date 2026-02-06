#!/usr/bin/env python3
"""
V2.7 Queue Persistence Module
Universal Agent Ruleset: ASCII-only, no placeholders, no behavior changes
Handles durable queue state persistence and crash recovery
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional


class PersistenceError(Exception):
    """Raised when persistence operations fail"""
    pass


def save_queue_state(queue_manager, path: str) -> None:
    """
    Save queue manager state to disk atomically
    
    Args:
        queue_manager: QueueManager instance to save
        path: File path to save state to
        
    Raises:
        PersistenceError: If save operation fails
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Serialize tasks
        tasks_list = []
        for task_id, task in queue_manager.tasks.items():
            # Handle datetime serialization - they may already be strings
            created_at = task.created_at
            if hasattr(created_at, 'isoformat'):
                created_at = created_at.isoformat()
            
            updated_at = task.updated_at
            if hasattr(updated_at, 'isoformat'):
                updated_at = updated_at.isoformat()
            
            task_data = {
                "task_id": task.task_id,
                "url": task.url,
                "destination": task.destination,
                "priority": task.priority,
                "state": task.state.value,
                "created_at": created_at,
                "updated_at": updated_at,
                "mode": task.mode,
                "connections_used": task.connections_used,
                "error": task.error,
                "progress": task.progress,
                "speed_bps": task.speed_bps,
                "resume_state_path": task.resume_state_path,
                "history_id": task.history_id,
                # V2.8 retry fields
                "attempt": task.attempt,
                "max_attempts": task.max_attempts,
                "next_eligible_at": task.next_eligible_at,
                "last_error": task.last_error,
                "host": task.host,
                "effective_priority": task.effective_priority
            }
            tasks_list.append(task_data)
        
        # Create state object
        state = {
            "schema_version": 1,
            "saved_at": datetime.now().isoformat(),
            "config_snapshot": {
                "max_active_downloads": queue_manager.max_active_downloads,
                "persist_queue": True,  # If we're saving, it must be enabled
                "persist_history": getattr(queue_manager, 'persist_history', True)
            },
            "tasks": tasks_list,
            "scheduler_running": queue_manager.scheduler_thread is not None and queue_manager.scheduler_thread.is_alive()
        }
        
        # Validate schema before saving
        validate_state_schema(state)
        
        # Atomic write: write to temp file then replace
        temp_path = path + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
        
        # Atomic replace
        os.replace(temp_path, path)
        
    except Exception as e:
        # Clean up temp file if it exists
        temp_path = path + '.tmp'
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise PersistenceError(f"Failed to save queue state: {str(e)}")


def load_queue_state(path: str) -> Dict[str, Any]:
    """
    Load queue state from disk
    
    Args:
        path: File path to load state from
        
    Returns:
        Dictionary containing deserialized queue state
        
    Raises:
        PersistenceError: If load operation fails or schema is invalid
    """
    try:
        if not os.path.exists(path):
            raise PersistenceError(f"Queue state file not found: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        # Validate schema
        validate_state_schema(state)
        
        return state
        
    except json.JSONDecodeError as e:
        raise PersistenceError(f"Invalid JSON in queue state file: {str(e)}")
    except Exception as e:
        raise PersistenceError(f"Failed to load queue state: {str(e)}")


def validate_state_schema(state: Dict[str, Any]) -> None:
    """
    Validate queue state schema
    
    Args:
        state: State dictionary to validate
        
    Raises:
        PersistenceError: If schema is invalid
    """
    # Check required top-level fields
    required_fields = ["schema_version", "saved_at", "config_snapshot", "tasks"]
    for field in required_fields:
        if field not in state:
            raise PersistenceError(f"Missing required field in state: {field}")
    
    # Check schema version
    if state["schema_version"] != 1:
        raise PersistenceError(f"Unsupported schema version: {state['schema_version']}")
    
    # Check config snapshot
    config = state["config_snapshot"]
    if not isinstance(config, dict):
        raise PersistenceError("config_snapshot must be a dictionary")
    
    required_config_fields = ["max_active_downloads", "persist_queue", "persist_history"]
    for field in required_config_fields:
        if field not in config:
            raise PersistenceError(f"Missing required config field: {field}")
    
    # Check tasks
    tasks = state["tasks"]
    if not isinstance(tasks, list):
        raise PersistenceError("tasks must be a list")
    
    # Check each task
    required_task_fields = [
        "task_id", "url", "destination", "priority", "state", 
        "created_at", "updated_at", "mode", "connections_used"
    ]
    
    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise PersistenceError(f"Task {i} must be a dictionary")
        
        for field in required_task_fields:
            if field not in task:
                raise PersistenceError(f"Task {i} missing required field: {field}")
        
        # Validate task_id is string
        if not isinstance(task["task_id"], str) or not task["task_id"]:
            raise PersistenceError(f"Task {i} has invalid task_id")
        
        # Validate state is valid (V2.8: include RETRY_WAIT)
        valid_states = ["PENDING", "STARTING", "DOWNLOADING", "PAUSED", "RETRY_WAIT", "COMPLETED", "FAILED", "CANCELLED"]
        if task["state"] not in valid_states:
            raise PersistenceError(f"Task {i} has invalid state: {task['state']}")


def apply_crash_recovery_rules(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply crash recovery rules to loaded state
    
    Crash Recovery Rules:
    - STARTING/DOWNLOADING -> PAUSED
    - RETRY_WAIT -> PENDING (clear retry wait)
    - PENDING -> PENDING (unchanged)
    - PAUSED -> PAUSED (unchanged)  
    - COMPLETED/FAILED/CANCELLED -> unchanged (terminal states)
    
    Args:
        state: Loaded state dictionary
        
    Returns:
        State dictionary with crash recovery rules applied
    """
    recovered_state = state.copy()
    recovered_state["tasks"] = []
    
    for task in state["tasks"]:
        recovered_task = task.copy()
        
        # Apply crash recovery rules
        if task["state"] in ["STARTING", "DOWNLOADING"]:
            recovered_task["state"] = "PAUSED"
            recovered_task["updated_at"] = datetime.now().isoformat()
        elif task["state"] == "RETRY_WAIT":
            # Convert retry wait to pending
            recovered_task["state"] = "PENDING"
            recovered_task["next_eligible_at"] = None
            recovered_task["updated_at"] = datetime.now().isoformat()
        # All other states remain unchanged
        
        recovered_state["tasks"].append(recovered_task)
    
    # Update saved_at timestamp
    recovered_state["saved_at"] = datetime.now().isoformat()
    
    return recovered_state