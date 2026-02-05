"""
UI Adapter API - Engine isolation layer for V4 UI
Thread-safe access to all download engine functionality
No UI imports - only engine communication
"""

import threading
import os
import json
import logging
import shutil
from typing import Dict, List, Optional, Any
from queue import Queue
import time
from datetime import datetime

# Engine imports (adapter only layer touches these)
from download_manager import DownloadManager
from youtube_downloader import YouTubeDownloader
# HuggingFace import moved to lazy loading
from utils import URLDetector, ConfigManager, HistoryManager
from event_bus import EventBus
from queue_manager import QueueManager


class UIAdapter:
    """Thread-safe adapter providing UI access to download engine"""
    
    def __init__(self):
        self._lock = threading.RLock()
        self.logger = logging.getLogger('ui.adapter')
        
        # Ensure logs always exist - create minimal file logger if none configured
        if not any(isinstance(h, logging.FileHandler) for h in logging.getLogger().handlers):
            self._ensure_minimal_file_logging()
        
        # Rate limiting for log spam prevention
        self._log_suppression = {}  # {message_key: {'count': int, 'last_time': float}}
        self._suppression_timeout = 30.0  # seconds
        
        # Core engine components
        self.download_manager = DownloadManager()
        self.youtube_downloader = YouTubeDownloader()
        
        # Lazy HuggingFace downloader (graceful degradation if deps missing)
        self.hf_downloader = None
        try:
            from huggingface_downloader import HuggingFaceDownloader
            self.hf_downloader = HuggingFaceDownloader()
        except Exception as e:
            self.logger.warning(f"HuggingFace disabled (dependency issue): {e}")
            
        self.url_detector = URLDetector()
        self.config_manager = ConfigManager()
        self.history_manager = HistoryManager("data/download_history_v2.json")  # V2-only history
        self.event_bus = EventBus()
        
        # Download tracking
        self.active_downloads = {}
        self.download_counter = 0
        
        # Load settings before initializing queue manager
        self._load_initial_config()
        
        # Queue Manager initialization
        self.queue_manager = None
        if self.settings.get('queue_enabled', False):
            self._initialize_queue_manager()
            
        self.logger.info("UI Adapter initialized successfully")
        
    def _ensure_minimal_file_logging(self):
        """Create minimal file logger if none exists (for CLI verification)"""
        try:
            import os
            os.makedirs("logs", exist_ok=True)
            
            handler = logging.FileHandler("logs/ui.log", encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            
            root_logger = logging.getLogger()
            root_logger.addHandler(handler)
            root_logger.setLevel(logging.INFO)
            
            self.logger.info("Minimal file logging initialized for CLI verification")
        except Exception:
            pass  # Silent failure - don't break if logging setup fails
    
    def _log_once_with_suppression(self, level: int, message: str, key: str = None):
        """Log message once, then suppress repeats with counter"""
        import time
        
        if key is None:
            key = message[:50]  # Use first 50 chars as key
        
        current_time = time.time()
        
        if key in self._log_suppression:
            suppression_info = self._log_suppression[key]
            time_since_last = current_time - suppression_info['last_time']
            
            if time_since_last < self._suppression_timeout:
                # Within suppression window - increment counter
                suppression_info['count'] += 1
                return
            else:
                # Outside window - log accumulated count and reset
                if suppression_info['count'] > 1:
                    self.logger.log(level, f"... repeated {suppression_info['count']} times (suppressed)")
                suppression_info['count'] = 1
                suppression_info['last_time'] = current_time
                self.logger.log(level, message)
        else:
            # First occurrence
            self._log_suppression[key] = {'count': 1, 'last_time': current_time}
            self.logger.log(level, message)
    
    def _initialize_queue_manager(self):
        """Initialize queue manager with config settings"""
        try:
            # Get queue config from settings
            config = self.settings
            
            # Create QueueManager with config parameters
            self.queue_manager = QueueManager(
                max_active_downloads=config.get('max_active_downloads', 2),
                persist_queue=config.get('persist_queue', False),
                queue_state_path=config.get('queue_state_path', "data/queue_state.json"),
                retry_enabled=config.get('retry_enabled', False),
                retry_max_attempts=config.get('retry_max_attempts', 3),
                retry_backoff_base_s=config.get('retry_backoff_base_s', 2.0),
                retry_backoff_max_s=config.get('retry_backoff_max_s', 300.0),
                retry_jitter_mode=config.get('retry_jitter_mode', 'none'),
                priority_aging_enabled=config.get('priority_aging_enabled', False),
                priority_aging_step=config.get('priority_aging_step', 1),
                priority_aging_interval_s=config.get('priority_aging_interval_s', 60.0),
                per_host_enabled=config.get('per_host_enabled', False),
                per_host_max_active=config.get('per_host_max_active', 1),
                event_bus=self.event_bus
            )
            
            # Set the downloader function that queue will call
            self.queue_manager.set_downloader(self._queue_downloader_wrapper)
            
            # Start the queue scheduler
            self.queue_manager.start_scheduler()
            
            # Log queue config snapshot for operational debugging
            self.logger.info(f"QUEUE CONFIG | queue_enabled=true max_active={self.queue_manager.max_active_downloads} persist_queue={self.queue_manager.persist_queue} retry_enabled={self.queue_manager.retry_enabled} max_attempts={self.queue_manager.retry_max_attempts}")
            
            self.logger.info("Queue manager initialized and started")
        except Exception as e:
            self.logger.error(f"Failed to initialize queue manager: {e}")
            self.queue_manager = None
    
    def _queue_downloader_wrapper(self, task_id: str, url: str, destination: str, 
                                progress_callback, **options):
        """Wrapper function for QueueManager to call our download methods"""            
        try:
            # Detect URL type  
            url_type = self.url_detector.detect_url_type(url)
            filename = url.split('/')[-1][:20] if '/' in url else "unknown"
            
            self.logger.info(f"TASK_STATE | {task_id} | STARTING | {filename}")
            self.logger.info(f"Queue executing download {task_id}: {url_type} - {url}")
            
            # Store in active downloads for UI tracking
            with self._lock:
                self.active_downloads[task_id] = {
                    'url': url,
                    'url_type': url_type,
                    'destination': destination, 
                    'filename': 'Preparing...',
                    'progress': 0.0,
                    'speed': '0 B/s',
                    'status': 'Starting',
                    'options': options,
                    'start_time': time.time()
                }
            
            # Execute download with the appropriate engine
            if url_type in ["YouTube", "Twitter", "Instagram", "TikTok"]:
                result = self.youtube_downloader.download(
                    url, destination, progress_callback,
                    extract_audio=options.get('extract_audio', False),
                    auto_quality=options.get('auto_quality', True)
                )
            elif url_type == "Hugging Face":
                if not self.hf_downloader:
                    raise ValueError("HuggingFace support disabled: missing dependencies")
                hf_token = self.settings.get('hf_token', '')
                result = self.hf_downloader.download(
                    url, destination, progress_callback, token=hf_token
                )
            else:
                try:
                    download_result = self.download_manager.download(
                        url, destination, progress_callback
                    )
                    # Handle possible None return or tuple return
                    if download_result is None:
                        success, info = False, {'error': 'Download method returned None'}
                    elif isinstance(download_result, tuple) and len(download_result) == 2:
                        success, info = download_result
                    else:
                        # Handle legacy single value return
                        success = bool(download_result)
                        info = {'mode': 'unknown', 'connections_used': 1, 'total_size': 0, 'download_time': 0}
                    
                    # Convert tuple result to expected dictionary format
                    if success:
                        result = {
                            'status': 'success',
                            'filename': os.path.basename(destination),
                            'info': info
                        }
                    else:
                        result = {
                            'status': 'failed',
                            'filename': os.path.basename(destination),
                            'error': info.get('error', 'Download failed'),
                            'info': info
                        }
                except Exception as download_error:
                    result = {
                        'status': 'failed',
                        'filename': os.path.basename(destination),
                        'error': f'Download exception: {str(download_error)}',
                        'info': {'error': str(download_error)}
                    }
            
            # Update final status and add to history
            if result and result.get('status') == 'success':
                with self._lock:
                    if task_id in self.active_downloads:
                        self.active_downloads[task_id]['status'] = 'Completed'
                        self.active_downloads[task_id]['filename'] = result.get('filename', 'Unknown')
                
                # Also update the queue task with the real filename
                if hasattr(self, 'queue_manager') and self.queue_manager and task_id in self.queue_manager.tasks:
                    with self.queue_manager.lock:
                        # Store the real filename in the task for UI display
                        if not hasattr(self.queue_manager.tasks[task_id], 'real_filename'):
                            self.queue_manager.tasks[task_id].real_filename = result.get('filename', 'Unknown')
                
                filename = result.get('filename', 'unknown')[:20]
                self.logger.info(f"TASK_DONE | {task_id} | {filename}")
                
                # Add to history
                self._add_to_history(task_id, result.get('filename', 'Unknown'))
                # Queue manager expects boolean return
                return True
            else:
                with self._lock:
                    if task_id in self.active_downloads:
                        self.active_downloads[task_id]['status'] = 'Failed'
                
                error_msg = str(result)[:50] if result else "unknown error"
                self.logger.info(f"TASK_FAILED | {task_id} | {error_msg}")
                # Queue manager expects boolean return
                return False
                
        except Exception as e:
            with self._lock:
                if task_id in self.active_downloads:
                    self.active_downloads[task_id]['status'] = 'Failed'
            
            error_msg = str(e)[:50]
            self.logger.info(f"TASK_FAILED | {task_id} | {error_msg}")
            self._log_once_with_suppression(logging.ERROR, f"Queue download {task_id} failed: {e}", f"download_error_{task_id}")
            # Queue manager expects boolean return, not exception
            return False
    
    def _load_initial_config(self):
        """Load initial configuration from config manager"""
        try:
            config = self.config_manager.load_config() or {}
            self.settings = config
            self._apply_settings_to_engine()
        except Exception:
            self.settings = {}
    
    def _get_setting(self, key: str, default=None):
        return self.settings.get(key, default)
    
    def _set_attr_if_exists(self, obj, attr: str, value) -> bool:
        try:
            if obj is None:
                return False
            if hasattr(obj, attr):
                setattr(obj, attr, value)
                return True
        except Exception:
            pass
        return False
    
    def _apply_settings_to_engine(self) -> None:
        """Apply current self.settings to live engine components (no-ops if not supported)."""
        import os
        
        # 1) HuggingFace token
        hf_token = self._get_setting("hf_token", "") or ""
        if hf_token:
            os.environ["HUGGINGFACE_HUB_TOKEN"] = hf_token
        else:
            # optional: do not delete env var; keep minimal and safe
            pass
        
        # 2) Queue / concurrency
        max_active = int(self._get_setting("max_active_downloads", 2) or 2)
        # Try common attachment points without assuming architecture
        qm = getattr(self, "queue_manager", None)
        if qm is None and hasattr(self.download_manager, "queue_manager"):
            qm = getattr(self.download_manager, "queue_manager", None)
        
        # max_active_downloads is the QueueManager constructor arg in your codebase
        self._set_attr_if_exists(qm, "max_active_downloads", max_active)
        
        # 3) Retry/backoff (QueueManager V2.8 fields)
        retry_enabled = bool(self._get_setting("retry_enabled", False))
        retry_max_attempts = int(self._get_setting("retry_max_attempts", 3) or 3)
        retry_backoff_base_s = float(self._get_setting("retry_backoff_base_s", 2.0) or 2.0)
        retry_backoff_max_s = float(self._get_setting("retry_backoff_max_s", 300.0) or 300.0)
        retry_jitter_mode = str(self._get_setting("retry_jitter_mode", "none") or "none")
        
        self._set_attr_if_exists(qm, "retry_enabled", retry_enabled)
        self._set_attr_if_exists(qm, "retry_max_attempts", retry_max_attempts)
        self._set_attr_if_exists(qm, "retry_backoff_base_s", retry_backoff_base_s)
        self._set_attr_if_exists(qm, "retry_backoff_max_s", retry_backoff_max_s)
        self._set_attr_if_exists(qm, "retry_jitter_mode", retry_jitter_mode)
        
        # 4) DownloadManager max_downloads (your existing UI key)
        max_dl = int(self._get_setting("max_downloads", 3) or 3)
        # Only set if DownloadManager actually has something like this
        self._set_attr_if_exists(self.download_manager, "max_downloads", max_dl)
    
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
    
    def start_download(self, url: str, destination: str, options: Optional[Dict] = None) -> Optional[str]:
        """Start a new download"""
        with self._lock:
            if not url or not url.strip():
                raise ValueError("URL cannot be empty")
            
            # Use default destination if blank
            if not destination:
                destination = self._get_setting("destination", "") or destination
            
            if not destination:
                raise ValueError("Destination cannot be empty")
            
            # Ensure destination exists
            try:
                if destination:
                    import os
                    os.makedirs(destination, exist_ok=True)
            except Exception:
                pass
            
            # Generate download ID
            download_id = f"dl_{self.download_counter}"
            self.download_counter += 1
            
            # Detect URL type
            url_type = self.url_detector.detect_url_type(url)
            
            self.logger.info(f"Starting download {download_id}: {url_type} - {url}")
            self.logger.info(f"Destination: {destination}")
            
            # Route through queue if enabled, otherwise direct download
            if self.queue_manager is not None:
                # Queue-based download - Log auto-download decision
                self.logger.info(f"AUTO-DOWNLOAD ENABLED | queue_enabled=true task_id={download_id}")
                self.logger.info(f"Adding download {download_id} to queue")
                
                # Handle None options parameter
                if options is None:
                    options = {}
                
                priority = options.get('priority', self.settings.get('queue_default_priority', 5))
                
                try:
                    success = self.queue_manager.enqueue(
                        task_id=download_id,
                        url=url,
                        destination=destination,
                        priority=priority,
                        mode=options.get('mode', 'auto'),
                        connections=options.get('connections', 1)
                    )
                    
                    if success:
                        # Extract host for logging
                        from urllib.parse import urlparse
                        url_host = urlparse(url).netloc or "unknown"
                        filename = url.split('/')[-1][:20] if '/' in url else "unknown"
                        
                        self.logger.info(f"QUEUE | ENQUEUE | task_id={download_id} | priority={priority} | url_host={url_host}")
                        self.logger.info(f"TASK_ADDED | {download_id} | {filename} | priority={priority}")
                        self._auto_save_logs_on_completion()
                        
                        # Store minimal metadata for UI tracking (queue handles the rest)
                        self.active_downloads[download_id] = {
                            'url': url,
                            'url_type': url_type,
                            'destination': destination,
                            'filename': 'Queued...',
                            'progress': 0.0,
                            'speed': '0 B/s',
                            'status': 'Queued',
                            'options': options or {},
                            'start_time': time.time()
                        }
                        
                        return download_id
                    else:
                        self.logger.error(f"Failed to enqueue download {download_id}: queue returned False")
                        # Fall through to direct download
                except Exception as e:
                    self.logger.error(f"Failed to enqueue download {download_id}: {e}")
                    # Fall through to direct download
            
            # Direct download (no queue or queue failed)
            self.logger.info(f"DIRECT DOWNLOAD | queue_enabled=false task_id={download_id}")
            # Store download metadata
            self.active_downloads[download_id] = {
                'url': url,
                'url_type': url_type,
                'destination': destination,
                'filename': 'Preparing...',
                'progress': 0.0,
                'speed': '0 B/s',
                'status': 'Starting',
                'options': options or {},
                'start_time': time.time()
            }
            
            # Start download in background thread
            def download_worker():
                try:
                    self._execute_download(download_id, url, destination, url_type, options or {})
                except Exception as e:
                    self.logger.error(f"Download {download_id} failed: {e}")
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
                if not self.hf_downloader:
                    raise ValueError("HuggingFace support disabled: missing dependencies")
                hf_token = self.settings.get('hf_token', '')
                result = self.hf_downloader.download(
                    url, destination, progress_callback, token=hf_token
                )
            else:
                download_result = self.download_manager.download(
                    url, destination, progress_callback
                )
                # Handle tuple result from download manager
                if isinstance(download_result, tuple) and len(download_result) == 2:
                    success, info = download_result
                    if success:
                        result = {
                            'status': 'success',
                            'filename': os.path.basename(destination),
                            'info': info
                        }
                    else:
                        result = {
                            'status': 'failed',
                            'filename': os.path.basename(destination),
                            'error': info.get('error', 'Download failed'),
                            'info': info
                        }
                else:
                    # Handle unexpected result format
                    result = {
                        'status': 'failed',
                        'filename': os.path.basename(destination),
                        'error': f'Unexpected result format: {type(download_result)}',
                        'info': {}
                    }
            
            if result and result.get('status') == 'success':
                self._update_download_status(download_id, 'Completed')
                # Add to history
                self._add_to_history(download_id, result.get('filename', 'Unknown'))
            else:
                self._update_download_status(download_id, 'Failed')
                
        except Exception as e:
            self._update_download_status(download_id, 'Failed', str(e))
    
    def _update_download_progress(self, download_id: str, progress_info: Dict):
        """Update download progress - fixed for yt-dlp string percentage format"""
        self.logger.info(f"PROGRESS_EVENT {download_id}: keys={list(progress_info.keys())}")
        with self._lock:
            if download_id in self.active_downloads:
                dl = self.active_downloads[download_id]
                
                # Parse progress (supports multiple hook schemas)
                progress_val = 0.0
                
                # 1) Direct percent (string "85.5%" or numeric)
                percent_val = progress_info.get('percent', None)
                if isinstance(percent_val, str) and percent_val.endswith('%'):
                    try:
                        progress_val = float(percent_val[:-1])
                    except (ValueError, TypeError):
                        progress_val = 0.0
                elif isinstance(percent_val, (int, float)):
                    progress_val = float(percent_val)
                
                # 2) If percent missing/zero, derive from bytes
                if progress_val <= 0.0:
                    downloaded = progress_info.get('downloaded_bytes', None)
                    total = (
                        progress_info.get('total_bytes', None)
                        or progress_info.get('total_bytes_estimate', None)
                    )
                    try:
                        if downloaded is not None and total:
                            progress_val = (float(downloaded) / float(total)) * 100.0
                    except (ValueError, TypeError, ZeroDivisionError):
                        progress_val = 0.0
                
                # clamp
                if progress_val < 0.0:
                    progress_val = 0.0
                elif progress_val > 100.0:
                    progress_val = 100.0
                
                # existing progress value
                prev = float(dl.get('progress', 0.0) or 0.0)
                
                # If we already reached 100, never regress
                if prev >= 100.0 and progress_val < 100.0:
                    progress_val = 100.0
                
                # If this hook carries no progress (common for final yt-dlp status hooks),
                # don't wipe the last known progress.
                # Detect "no progress" by missing percent/bytes AND computed 0.0
                has_any_progress_fields = any(
                    k in progress_info for k in ('percent', 'downloaded_bytes', 'total_bytes', 'total_bytes_estimate')
                )
                if (not has_any_progress_fields) and progress_val == 0.0 and prev > 0.0:
                    progress_val = prev
                
                # If status indicates completion, force 100
                status = str(progress_info.get('status', '')).lower()
                if status in ('finished', 'completed', 'done'):
                    progress_val = 100.0
                
                dl['progress'] = progress_val
                
                self.logger.debug(
                    f"Progress raw: percent={progress_info.get('percent')} "
                    f"downloaded_bytes={progress_info.get('downloaded_bytes')} "
                    f"total_bytes={progress_info.get('total_bytes')} "
                    f"total_bytes_estimate={progress_info.get('total_bytes_estimate')} "
                    f"-> {progress_val:.1f}%"
                )
                
                dl['speed'] = progress_info.get('speed', '0 B/s')
                dl['filename'] = progress_info.get('filename', dl['filename'])
                
                # Update status based on progress
                if progress_val > 0:
                    dl['status'] = 'Downloading'
    
    def _update_download_status(self, download_id: str, status: str, error: str = None):
        """Update download status"""
        with self._lock:
            if download_id in self.active_downloads:
                self.active_downloads[download_id]['status'] = status
                if error:
                    self.active_downloads[download_id]['error'] = error
    
    def _add_to_history(self, download_id: str, filename: str):
        """Add completed download to V2 history only"""
        try:
            if download_id in self.active_downloads:
                dl = self.active_downloads[download_id]
                
                # Create V2 history entry (native format)
                history_entry = {
                    'url': dl['url'],
                    'filename': filename,
                    'url_type': dl['url_type'],  # V2 uses url_type
                    'destination': dl['destination'],
                    'status': 'Completed',
                    'file_size': dl.get('file_size', 0),
                    'timestamp': None  # HistoryManager adds timestamp
                }
                
                self.logger.info(f"Adding to V2 history: {filename} from {dl['url']}")
                
                # Use V2 history manager with V2-only deduplication
                self.history_manager.add_download(history_entry)
                
                # Auto-save logs on task completion
                self._auto_save_logs_on_completion()

        except Exception as e:
            self.logger.error(f"Failed to add to history: {e}")
    
    def _auto_save_logs_on_completion(self):
        """Auto-save logs when a download completes"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            logs_dir = r"C:\Users\suppo\Downloads\DL Manager Logs"
            
            # Create directory if it doesn't exist
            os.makedirs(logs_dir, exist_ok=True)
            
            # Create destination filename
            log_filename = f"NGKs_DownloadManager_Log_task_complete_{timestamp}.log"
            dest_path = os.path.join(logs_dir, log_filename)
            
            # Copy log file if it exists
            log_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'ui.log')
            if os.path.exists(log_file):
                shutil.copy2(log_file, dest_path)
                self.logger.info(f"LOG AUTO-SAVED: {dest_path}")
        except Exception as e:
            self.logger.error(f"Failed to auto-save log on completion: {e}")
    
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
    
    def open_file(self, download_id: str) -> bool:
        """Open downloaded file"""
        try:
            with self._lock:
                if download_id in self.active_downloads:
                    download_info = self.active_downloads[download_id]
                    if download_info['status'] == 'Completed':
                        filepath = os.path.join(download_info['destination'], download_info['filename'])
                        if os.path.exists(filepath):
                            os.startfile(filepath)
                            return True
        except Exception:
            pass
        return False
    
    def remove(self, download_id: str) -> bool:
        """Remove download from active list (UI only, not file deletion)"""
        try:
            with self._lock:
                if download_id in self.active_downloads:
                    del self.active_downloads[download_id]
                    return True
        except Exception:
            pass
        return False
    
    def clear_all(self) -> bool:
        """Clear all completed downloads from UI list"""
        try:
            with self._lock:
                completed_ids = [
                    download_id for download_id, info in self.active_downloads.items()
                    if info['status'] in ['Completed', 'Failed', 'Cancelled']
                ]
                for download_id in completed_ids:
                    del self.active_downloads[download_id]
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
            if not self.hf_downloader:
                return False
            # Use HF downloader to test token
            return self.hf_downloader.test_token(token)
        except Exception:
            return False
    
    def set_settings(self, settings: Dict[str, Any]) -> bool:
        """Persist settings and apply to engine immediately."""
        try:
            if not isinstance(settings, dict):
                return False
            
            # sanitize / validate only the keys we care about (ignore unknown keys)
            sanitized = {}
            
            def _bool(k, default=False):
                v = settings.get(k, self.settings.get(k, default))
                return bool(v)
            
            def _int(k, default, lo=None, hi=None):
                v = settings.get(k, self.settings.get(k, default))
                try:
                    v = int(v)
                except Exception:
                    v = default
                if lo is not None: v = max(lo, v)
                if hi is not None: v = min(hi, v)
                return v
            
            def _float(k, default, lo=None, hi=None):
                v = settings.get(k, self.settings.get(k, default))
                try:
                    v = float(v)
                except Exception:
                    v = default
                if lo is not None: v = max(lo, v)
                if hi is not None: v = min(hi, v)
                return v
            
            def _str(k, default=""):
                v = settings.get(k, self.settings.get(k, default))
                return str(v) if v is not None else default
            
            sanitized["hf_token"] = _str("hf_token", "")
            sanitized["auto_quality"] = _bool("auto_quality", True)
            sanitized["extract_audio"] = _bool("extract_audio", False)
            sanitized["max_downloads"] = _int("max_downloads", 3, lo=1, hi=16)
            
            # NEW keys
            sanitized["destination"] = _str("destination", self.settings.get("destination", ""))
            sanitized["max_active_downloads"] = _int("max_active_downloads", 2, lo=1, hi=10)
            
            sanitized["retry_enabled"] = _bool("retry_enabled", False)
            sanitized["retry_max_attempts"] = _int("retry_max_attempts", 3, lo=0, hi=20)
            sanitized["retry_backoff_base_s"] = _float("retry_backoff_base_s", 2.0, lo=0.1, hi=60.0)
            sanitized["retry_backoff_max_s"] = _float("retry_backoff_max_s", 300.0, lo=1.0, hi=3600.0)
            sanitized["retry_jitter_mode"] = _str("retry_jitter_mode", "none")
            
            # apply
            self.settings.update(sanitized)
            self.save_settings()
            self._apply_settings_to_engine()
            return True
        except Exception as e:
            self.logger.error(f"set_settings failed: {e}")
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

    # Queue Management Methods (V2.0 UI exposure of existing functionality)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get queue status summary"""
        try:
            # Check if queue manager is available
            qm = self._get_queue_manager()
            if qm is None:
                return {
                    'queue_enabled': False,
                    'active_tasks': 0,
                    'pending_tasks': 0,
                    'completed_tasks': 0,
                    'error': 'Queue manager not available'
                }
            
            # Get status from queue manager
            status = qm.get_status()
            return {
                'queue_enabled': True,
                'active_tasks': status.get('active', 0),
                'pending_tasks': status.get('pending', 0),
                'completed_tasks': status.get('completed', 0),
                'total_tasks': status.get('total', 0)
            }
        except Exception as e:
            self.logger.error(f"Queue status error: {e}")
            return {
                'queue_enabled': False,
                'active_tasks': 0,
                'pending_tasks': 0,
                'completed_tasks': 0,
                'error': str(e)
            }
    
    def list_queue_tasks(self) -> List[Dict[str, Any]]:
        """Get list of all queue tasks"""
        try:
            qm = self._get_queue_manager()
            if qm is None:
                return []
            
            # Get task list from queue manager  
            tasks = qm.list_task_snapshots()
            return tasks
        except Exception as e:
            self.logger.error(f"Queue task list error: {e}")
            return []
    
    def pause_queue_task(self, task_id: str) -> bool:
        """Pause a queue task by ID"""
        try:
            qm = self._get_queue_manager()
            if qm is None:
                return False
            
            # Find task by partial ID match
            tasks = qm.list_task_snapshots()
            for task in tasks:
                if task.get('task_id', '').startswith(task_id):
                    full_task_id = task['task_id']
                    return qm.pause_task(full_task_id)
            
            return False
        except Exception as e:
            self.logger.error(f"Queue pause error: {e}")
            return False
    
    def resume_queue_task(self, task_id: str) -> bool:
        """Resume a paused queue task by ID"""
        try:
            qm = self._get_queue_manager()
            if qm is None:
                return False
            
            # Find task by partial ID match
            tasks = qm.list_task_snapshots()
            for task in tasks:
                if task.get('task_id', '').startswith(task_id):
                    full_task_id = task['task_id']
                    return qm.resume_task(full_task_id)
            
            return False
        except Exception as e:
            self.logger.error(f"Queue resume error: {e}")
            return False
    
    def cancel_queue_task(self, task_id: str) -> bool:
        """Cancel a queue task by ID"""
        try:
            qm = self._get_queue_manager()
            if qm is None:
                return False
            
            # Find task by partial ID match
            tasks = qm.list_task_snapshots()
            for task in tasks:
                if task.get('task_id', '').startswith(task_id):
                    full_task_id = task['task_id']
                    return qm.cancel_task(full_task_id)
            
            return False
        except Exception as e:
            self.logger.error(f"Queue cancel error: {e}")
            return False
    
    def get_active_downloads(self) -> Dict[str, Dict[str, Any]]:
        """Get current active downloads"""
        with self._lock:
            return self.active_downloads.copy()
    
    def list_active(self):
        """Back-compat alias for UI calls - returns list format expected by downloads table"""
        with self._lock:
            try:
                if hasattr(self, "queue_manager") and self.queue_manager:
                    # Use queue snapshots for comprehensive task info
                    return self.queue_manager.list_task_snapshots()
                else:
                    # Convert dict format to list format for UI compatibility
                    return [info for info in self.active_downloads.values()]
            except Exception as e:
                import logging
                logging.getLogger("ui_adapter").warning(f"Failed to list active downloads: {e}")
                return []
    
    def _get_queue_manager(self):
        """Get queue manager instance if available"""
        # Return the queue manager if it exists and is initialized
        return getattr(self, 'queue_manager', None)


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