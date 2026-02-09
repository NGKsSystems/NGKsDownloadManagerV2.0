"""
UI Event Management - Thread-safe event delivery from engine to UI
Subscribes to event_bus and provides normalized UI-safe event handling
"""

import threading
from queue import Queue, Empty
from typing import Callable, Dict, Any, List
from dataclasses import dataclass

# Engine imports
from event_bus import EventBus


@dataclass
class UIEvent:
    """UI-safe event wrapper"""
    event_type: str
    data: Dict[str, Any]
    timestamp: float


class UIEventManager:
    """Thread-safe event management for UI"""
    
    def __init__(self):
        self.event_bus = EventBus()
        self.event_queue = Queue()
        self.subscribers = []
        self._lock = threading.Lock()
        self._subscribed = False
    
    def subscribe_to_engine(self):
        """Subscribe to engine event bus"""
        if not self._subscribed:
            self.event_bus.subscribe(self._on_engine_event)
            self._subscribed = True
    
    def _on_engine_event(self, event_type: str, data: Dict[str, Any]):
        """Handle any event from engine event bus"""
        if event_type == 'download_started':
            self._on_download_started(data)
        elif event_type == 'download_progress':
            self._on_download_progress(data)
        elif event_type == 'download_completed':
            self._on_download_completed(data)
        elif event_type == 'download_failed':
            self._on_download_failed(data)
    
    def _on_download_started(self, data):
        """Handle download started event from engine"""
        ui_event = UIEvent(
            event_type='download_started',
            data=self._normalize_download_data(data),
            timestamp=data.get('timestamp', 0)
        )
        self.event_queue.put(ui_event)
    
    def _on_download_progress(self, data):
        """Handle download progress event from engine"""
        ui_event = UIEvent(
            event_type='download_progress',
            data=self._normalize_progress_data(data),
            timestamp=data.get('timestamp', 0)
        )
        self.event_queue.put(ui_event)
    
    def _on_download_completed(self, data):
        """Handle download completed event from engine"""
        ui_event = UIEvent(
            event_type='download_completed',
            data=self._normalize_download_data(data),
            timestamp=data.get('timestamp', 0)
        )
        self.event_queue.put(ui_event)
    
    def _on_download_failed(self, data):
        """Handle download failed event from engine"""
        ui_event = UIEvent(
            event_type='download_failed',
            data=self._normalize_download_data(data),
            timestamp=data.get('timestamp', 0)
        )
        self.event_queue.put(ui_event)
    
    def _normalize_download_data(self, data: Dict) -> Dict[str, Any]:
        """Normalize download event data for UI consumption"""
        return {
            'download_id': data.get('download_id', 'unknown'),
            'filename': data.get('filename', 'Unknown'),
            'url': data.get('url', ''),
            'status': data.get('status', 'Unknown')
        }
    
    def _normalize_progress_data(self, data: Dict) -> Dict[str, Any]:
        """Normalize progress event data for UI consumption"""
        return {
            'download_id': data.get('download_id', 'unknown'),
            'filename': data.get('filename', 'Unknown'),
            'progress': data.get('progress', 0),
            'speed': data.get('speed', '0 B/s'),
            'eta': data.get('eta', 'Unknown')
        }
    
    def add_subscriber(self, callback: Callable[[UIEvent], None]):
        """Add UI event subscriber"""
        with self._lock:
            self.subscribers.append(callback)
    
    def remove_subscriber(self, callback: Callable[[UIEvent], None]):
        """Remove UI event subscriber"""
        with self._lock:
            if callback in self.subscribers:
                self.subscribers.remove(callback)
    
    def process_events(self) -> List[UIEvent]:
        """Process pending events and return them"""
        events = []
        
        try:
            while True:
                event = self.event_queue.get_nowait()
                events.append(event)
                
                # Notify all subscribers
                with self._lock:
                    for subscriber in self.subscribers:
                        try:
                            subscriber(event)
                        except Exception:
                            # Don't let subscriber errors break event processing
                            pass
                            
        except Empty:
            pass
        
        return events
    
    def poll(self, max_items: int = 100) -> List[UIEvent]:
        """Poll for events (required method for UI queue-based polling)"""
        events = []
        count = 0
        
        try:
            while count < max_items:
                event = self.event_queue.get_nowait()
                events.append(event)
                count += 1
                
                # Notify all subscribers
                with self._lock:
                    for subscriber in self.subscribers:
                        try:
                            subscriber(event)
                        except Exception:
                            # Don't let subscriber errors break event processing
                            pass
                            
        except Empty:
            pass
        
        return events
    
    def clear_events(self):
        """Clear all pending events"""
        try:
            while True:
                self.event_queue.get_nowait()
        except Empty:
            pass


# Global event manager
_event_manager = None
_event_lock = threading.Lock()


def get_event_manager() -> UIEventManager:
    """Get global UI event manager (singleton)"""
    global _event_manager
    
    with _event_lock:
        if _event_manager is None:
            _event_manager = UIEventManager()
            _event_manager.subscribe_to_engine()
        return _event_manager


def shutdown_events():
    """Shutdown global event manager"""
    global _event_manager
    
    with _event_lock:
        if _event_manager is not None:
            _event_manager.clear_events()
            _event_manager = None