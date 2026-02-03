"""
UI Adapter API - Engine isolation layer for V4 UI
Thread-safe access to all download engine functionality
No UI imports - only engine communication
"""

import threading
import os
import json
from typing import Dict, List, Optional, Any
from queue import Queue
import time

# Engine imports (adapter only layer touches these)
from download_manager import DownloadManager
from youtube_downloader import YouTubeDownloader
from huggingface_downloader import HuggingFaceDownloader
from utils import URLDetector, ConfigManager, HistoryManager
from event_bus import EventBus


class UIAdapter:
    """Thread-safe adapter providing UI access to download engine"""
    
    def __init__(self):
        self._lock = threading.RLock()
        
        # Core engine components
        self.download_manager = DownloadManager()
        self.youtube_downloader = YouTubeDownloader()
        self.hf_downloader = HuggingFaceDownloader()
        self.url_detector = URLDetector()
        self.config_manager = ConfigManager()
        self.history_manager = HistoryManager()
        self.event_bus = EventBus()
        
        # Download tracking
        self.active_downloads = {}
        self.download_counter = 0
        
        # Load configuration
        self._load_initial_config()
    
    def _load_initial_config(self):
        """Load initial configuration from config manager"""
        try:
            config = self.config_manager.load_config() or {}
            self.settings = config
        except Exception:
            self.settings = {}
    
    def validate_url(self, url: str) -> Dict[str, Any]:
        """Validate and detect URL type"""
        if not url or not url.strip():
            return {'valid': False, 'type': 'Unknown', 'error': 'Empty URL'}
        
        try:
            url_type = self.url_detector.detect_url_type(url.strip())
            return {'valid': True, 'type': url_type, 'error': None}
        except Exception as e:
            return {'valid': False, 'type': 'Unknown', 'error': str(e)}
    
    def get_default_dest(self) -> str:
        """Get default destination directory"""
        return self.settings.get('destination', os.path.expanduser("~/Downloads"))
    
    def start_download(self, url: str, destination: str, options: Optional[Dict] = None) -> str:
        """Start a new download"""
        with self._lock:
            if not url or not url.strip():
                raise ValueError("URL cannot be empty")
            
            if not destination:
                raise ValueError("Destination cannot be empty")
            
            # Generate download ID
            download_id = f"dl_{self.download_counter}"
            self.download_counter += 1
            
            # Detect URL type
            url_type = self.url_detector.detect_url_type(url)
            
            # Store download metadata
            self.active_downloads[download_id] = {
                'url': url,
                'url_type': url_type,
                'destination': destination,
                'filename': 'Preparing...',
                'progress': 0,
                'speed': '0 B/s',
                'status': 'Starting',
                'options': options or {}
            }
            
            # Start download in background thread
            def download_worker():
                try:
                    self._execute_download(download_id, url, destination, url_type, options or {})
                except Exception as e:
                    self._update_download_status(download_id, 'Failed', str(e))
            
            thread = threading.Thread(target=download_worker, daemon=True)
            thread.start()
            
            return download_id
    
    def _execute_download(self, download_id: str, url: str, destination: str, url_type: str, options: Dict):
        """Execute download using appropriate downloader"""
        def progress_callback(progress_info):
            self._update_download_progress(download_id, progress_info)
        
        try:
            if url_type in ["YouTube", "Twitter", "Instagram", "TikTok"]:
                result = self.youtube_downloader.download(
                    url, destination, progress_callback,
                    extract_audio=options.get('extract_audio', False),
                    auto_quality=options.get('auto_quality', True)
                )
            elif url_type == "Hugging Face":
                hf_token = self.settings.get('hf_token', '')
                result = self.hf_downloader.download(
                    url, destination, progress_callback, token=hf_token
                )
            else:
                result = self.download_manager.download(
                    url, destination, progress_callback
                )
            
            if result and result.get('status') == 'success':
                self._update_download_status(download_id, 'Completed')
                # Add to history
                self._add_to_history(download_id, result.get('filename', 'Unknown'))
            else:
                self._update_download_status(download_id, 'Failed')
                
        except Exception as e:
            self._update_download_status(download_id, 'Failed', str(e))
    
    def _update_download_progress(self, download_id: str, progress_info: Dict):
        """Update download progress"""
        with self._lock:
            if download_id in self.active_downloads:
                dl = self.active_downloads[download_id]
                dl['progress'] = progress_info.get('percent', 0)
                dl['speed'] = progress_info.get('speed', '0 B/s')
                dl['filename'] = progress_info.get('filename', dl['filename'])
                if progress_info.get('percent', 0) > 0:
                    dl['status'] = 'Downloading'
    
    def _update_download_status(self, download_id: str, status: str, error: str = None):
        """Update download status"""
        with self._lock:
            if download_id in self.active_downloads:
                self.active_downloads[download_id]['status'] = status
                if error:
                    self.active_downloads[download_id]['error'] = error
    
    def _add_to_history(self, download_id: str, filename: str):
        """Add completed download to history"""
        try:
            if download_id in self.active_downloads:
                dl = self.active_downloads[download_id]
                self.history_manager.add_download({
                    'url': dl['url'],
                    'filename': filename,
                    'destination': dl['destination'],
                    'url_type': dl['url_type'],
                    'timestamp': None  # HistoryManager adds timestamp
                })
        except Exception:
            pass
    
    def list_active(self) -> List[Dict[str, Any]]:
        """Get list of active downloads"""
        with self._lock:
            return [
                {
                    'download_id': dl_id,
                    'filename': dl['filename'],
                    'url_type': dl['url_type'],
                    'progress': f"{dl['progress']:.1f}%",
                    'speed': dl['speed'],
                    'status': dl['status']
                }
                for dl_id, dl in self.active_downloads.items()
            ]
    
    def pause(self, download_id: str) -> bool:
        """Pause download (placeholder for V1 parity)"""
        # TODO: Implement actual pause functionality
        with self._lock:
            if download_id in self.active_downloads:
                self.active_downloads[download_id]['status'] = 'Paused'
                return True
        return False
    
    def resume(self, download_id: str) -> bool:
        """Resume download (placeholder for V1 parity)"""
        # TODO: Implement actual resume functionality
        with self._lock:
            if download_id in self.active_downloads:
                self.active_downloads[download_id]['status'] = 'Downloading'
                return True
        return False
    
    def cancel(self, download_id: str) -> bool:
        """Cancel download (placeholder for V1 parity)"""
        # TODO: Implement actual cancel functionality
        with self._lock:
            if download_id in self.active_downloads:
                self.active_downloads[download_id]['status'] = 'Cancelled'
                return True
        return False
    
    def open_folder(self, download_id: str) -> bool:
        """Open download folder"""
        try:
            with self._lock:
                if download_id in self.active_downloads:
                    folder = self.active_downloads[download_id]['destination']
                    os.startfile(folder)
                    return True
        except Exception:
            pass
        return False
    
    def set_hf_token(self, token: str) -> bool:
        """Set Hugging Face token"""
        try:
            self.settings['hf_token'] = token
            return True
        except Exception:
            return False
    
    def test_hf_token(self, token: str) -> bool:
        """Test Hugging Face token validity"""
        try:
            # Use HF downloader to test token
            return self.hf_downloader.test_token(token)
        except Exception:
            return False
    
    def set_settings(self, settings: Dict[str, Any]) -> bool:
        """Update settings"""
        try:
            self.settings.update(settings)
            return True
        except Exception:
            return False
    
    def get_settings(self) -> Dict[str, Any]:
        """Get current settings"""
        return self.settings.copy()
    
    def save_settings(self) -> bool:
        """Save settings to config manager"""
        try:
            self.config_manager.save_config(self.settings)
            return True
        except Exception:
            return False
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get download history"""
        try:
            return self.history_manager.get_history()
        except Exception:
            return []
    
    def clear_history(self) -> bool:
        """Clear download history"""
        try:
            self.history_manager.clear_history()
            return True
        except Exception:
            return False
    
    def export_history(self, filename: str) -> bool:
        """Export history to file"""
        try:
            history = self.get_history()
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False


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