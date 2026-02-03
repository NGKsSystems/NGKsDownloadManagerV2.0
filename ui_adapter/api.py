"""
UI Adapter API - Engine isolation stubs for V4 UI
Thread-safe access to engine functionality (stubs only - no engine edits)
"""

import threading
import os
from typing import Dict, List, Optional, Tuple, Any


class UIAdapter:
    """Thread-safe adapter providing UI access to download engine"""
    
    def __init__(self):
        self._lock = threading.RLock()
        # Initialize engine components here (stubs for now)
        
    def validate_url(self, url: str) -> Tuple[bool, str]:
        """
        Validate and detect URL type
        
        Args:
            url: URL to validate
            
        Returns:
            Tuple of (is_valid, message/type)
        """
        # Stub implementation
        if not url or not url.strip():
            return False, "Empty URL"
        return True, "Valid URL"
    
    def get_default_dest(self) -> str:
        """Get default destination directory"""
        return os.path.expanduser("~/Downloads")
    
    def start_download(self, url: str, dest: str, options: Optional[Dict] = None) -> str:
        """
        Start a new download
        
        Args:
            url: URL to download
            dest: Destination directory  
            options: Optional download options
            
        Returns:
            Download ID (string)
        """
        # Stub implementation
        return "dl_stub_001"
    
    def pause(self, download_id: str) -> bool:
        """
        Pause download
        
        Args:
            download_id: Download ID to pause
            
        Returns:
            True if paused successfully
        """
        # Stub implementation
        return True
    
    def resume(self, download_id: str) -> bool:
        """
        Resume download
        
        Args:
            download_id: Download ID to resume
            
        Returns:
            True if resumed successfully
        """
        # Stub implementation
        return True
    
    def cancel(self, download_id: str) -> bool:
        """
        Cancel download
        
        Args:
            download_id: Download ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        # Stub implementation
        return True
    
    def remove(self, download_id: str) -> bool:
        """
        Remove download from list
        
        Args:
            download_id: Download ID to remove
            
        Returns:
            True if removed successfully
        """
        # Stub implementation
        return True
    
    def clear_all(self) -> bool:
        """
        Clear all completed downloads
        
        Returns:
            True if cleared successfully
        """
        # Stub implementation
        return True
    
    def open_folder(self, path: str) -> bool:
        """
        Open folder in system explorer
        
        Args:
            path: Folder path to open
            
        Returns:
            True if opened successfully
        """
        # Stub implementation
        try:
            os.startfile(path)
            return True
        except Exception:
            return False
    
    def set_settings(self, settings: Dict[str, Any]) -> bool:
        """
        Update application settings
        
        Args:
            settings: Settings dictionary
            
        Returns:
            True if settings saved successfully
        """
        # Stub implementation
        return True
    
    def get_history(self) -> List[Dict[str, Any]]:
        """
        Get download history
        
        Returns:
            List of history entries
        """
        # Stub implementation
        return []
    
    def clear_history(self) -> bool:
        """
        Clear download history
        
        Returns:
            True if history cleared successfully
        """
        # Stub implementation
        return True
    
    def export_history(self, path: str) -> bool:
        """
        Export history to file
        
        Args:
            path: Export file path
            
        Returns:
            True if exported successfully
        """
        # Stub implementation
        return True


# Global adapter instance
_adapter_instance = None
_adapter_lock = threading.Lock()


def get_adapter() -> UIAdapter:
    """Get global UI adapter instance (singleton)"""
    global _adapter_instance
    
    with _adapter_lock:
        if _adapter_instance is None:
            _adapter_instance = UIAdapter()
        return _adapter_instance


def shutdown_adapter():
    """Shutdown global adapter instance"""
    global _adapter_instance
    
    with _adapter_lock:
        if _adapter_instance is not None:
            _adapter_instance = None