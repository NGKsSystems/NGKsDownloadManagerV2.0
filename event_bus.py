#!/usr/bin/env python3
"""
Event Bus for NGK's DL Manager V2.9
Thread-safe in-process pub/sub system for UI integration
Universal Agent Ruleset: ASCII-only, no placeholders, engine-only
"""

import threading
import uuid
from typing import Dict, Callable, Any


class EventBus:
    """Thread-safe in-process pub/sub event bus"""
    
    def __init__(self):
        self._subscribers: Dict[str, Callable] = {}
        self._lock = threading.RLock()
    
    def subscribe(self, callback: Callable[[str, Dict[str, Any]], None]) -> str:
        """
        Subscribe to events
        
        Args:
            callback: Function that takes (event_type, payload)
            
        Returns:
            Token for unsubscribing
        """
        with self._lock:
            token = str(uuid.uuid4())
            self._subscribers[token] = callback
            return token
    
    def unsubscribe(self, token: str) -> bool:
        """
        Unsubscribe from events
        
        Args:
            token: Token from subscribe()
            
        Returns:
            True if token was found and removed, False otherwise
        """
        with self._lock:
            return self._subscribers.pop(token, None) is not None
    
    def emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Emit an event to all subscribers
        
        Args:
            event_type: Type of event (e.g., 'TASK_ADDED', 'TASK_UPDATED')
            payload: Event data dictionary
        """
        with self._lock:
            # Take a snapshot of subscribers to avoid issues if callbacks modify the dict
            subscribers = list(self._subscribers.values())
        
        # Call subscribers outside the lock to prevent deadlock
        for callback in subscribers:
            try:
                callback(event_type, payload)
            except Exception:
                # Silently ignore callback errors to prevent one bad subscriber
                # from breaking the entire event system
                pass
    
    def get_subscriber_count(self) -> int:
        """Get number of active subscribers"""
        with self._lock:
            return len(self._subscribers)
    
    def clear_subscribers(self) -> None:
        """Remove all subscribers"""
        with self._lock:
            self._subscribers.clear()