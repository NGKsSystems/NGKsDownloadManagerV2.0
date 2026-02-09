#!/usr/bin/env python3
"""
UI Contract for NGK's DL Manager V2.9
Defines stable snapshot format and validation for UI integration
Universal Agent Ruleset: ASCII-only, no placeholders, engine-only
"""

from typing import Dict, Any, List


# Required keys for task snapshot validation
REQUIRED_KEYS = [
    'task_id',
    'url', 
    'destination',
    'priority',
    'state',
    'created_at',
    'updated_at',
    'progress',
    'speed_bps',
    'error',
    'attempt',
    'max_attempts',
    'host',
    'effective_priority'
]


def validate_snapshot(snapshot: Dict[str, Any]) -> None:
    """
    Validate task snapshot contains all required fields
    
    Args:
        snapshot: Task snapshot dictionary to validate
        
    Raises:
        RuntimeError: If any required key is missing
    """
    missing_keys = []
    
    for key in REQUIRED_KEYS:
        if key not in snapshot:
            missing_keys.append(key)
    
    if missing_keys:
        raise RuntimeError(f"Snapshot validation failed: missing required keys: {missing_keys}")


def build_task_snapshot(task) -> Dict[str, Any]:
    """
    Build a validated task snapshot for UI consumption
    
    Args:
        task: QueueTask instance
        
    Returns:
        Dictionary containing all required fields for UI
    """
    # Use real filename if available, otherwise extract from URL
    real_filename = getattr(task, 'real_filename', None)
    if not real_filename and hasattr(task, 'url'):
        url = task.url
        # Extract meaningful filename from URL
        if any(domain in url for domain in ['youtu.be', 'youtube.com', 'twitter.com', 'instagram.com', 'tiktok.com']):
            if 'youtu.be/' in url:
                video_id = url.split('youtu.be/')[-1].split('?')[0]
                real_filename = f"Video_{video_id[:11]}"
            elif 'youtube.com/watch' in url:
                video_id = url.split('v=')[-1].split('&')[0] if 'v=' in url else 'unknown'
                real_filename = f"Video_{video_id[:11]}"
            else:
                real_filename = "Social_Media_Video"
        else:
            real_filename = url.split('/')[-1].split('?')[0] or 'Unknown'
    
    snapshot = {
        'task_id': task.task_id,
        'url': task.url,
        'destination': task.destination,
        'priority': task.priority,
        'state': task.state.value if hasattr(task.state, 'value') else str(task.state),
        'created_at': task.created_at,
        'updated_at': task.updated_at,
        'progress': float(task.progress) if task.progress is not None else 0.0,
        'speed_bps': float(task.speed_bps) if task.speed_bps is not None else 0.0,
        'error': task.error if task.error is not None else "",
        'attempt': getattr(task, 'attempt', 1),
        'max_attempts': getattr(task, 'max_attempts', 1),
        'host': getattr(task, 'host', ""),
        'effective_priority': getattr(task, 'effective_priority', task.priority),
        # Add computed fields for UI compatibility
        'filename': real_filename or 'Processing...',
        'url_type': 'YouTube' if any(domain in task.url for domain in ['youtu.be', 'youtube.com']) else 'Unknown'
    }
    
    # Validate before returning
    validate_snapshot(snapshot)
    
    return snapshot


def build_queue_status_snapshot(queue_manager) -> Dict[str, Any]:
    """
    Build a validated queue status snapshot for UI consumption
    
    Args:
        queue_manager: QueueManager instance
        
    Returns:
        Dictionary containing queue status information
    """
    status = queue_manager.get_status()
    
    snapshot = {
        'total_tasks': status.get('total_tasks', 0),
        'state_counts': status.get('state_counts', {}),
        'active_count': status.get('active_count', 0),
        'max_active': queue_manager.max_active_downloads,
        'scheduler_running': queue_manager.scheduler_running
    }
    
    return snapshot