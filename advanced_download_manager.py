"""
Advanced Download Manager V2.0
Aria2-level performance with multi-connection downloads, connection pooling,
bandwidth controls, and advanced queue management
"""

import os
import requests
import threading
import asyncio
import aiohttp
import aiofiles
from urllib.parse import urlparse, unquote
import time
import hashlib
import math
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, PriorityQueue
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
import logging
from datetime import datetime, timedelta

@dataclass
class DownloadSegment:
    """Represents a download segment for multi-connection downloads"""
    start: int
    end: int
    downloaded: int = 0
    thread_id: Optional[int] = None
    status: str = "pending"  # pending, downloading, completed, failed
    
@dataclass(order=True)
class DownloadTask:
    """Represents a download task with priority"""
    priority: int
    url: str = field(compare=False)
    destination: str = field(compare=False)
    options: Dict = field(compare=False, default_factory=dict)
    created_at: datetime = field(compare=False, default_factory=datetime.now)
    task_id: str = field(compare=False, default="")

class BandwidthController:
    """Controls download bandwidth and speed limiting"""
    
    def __init__(self):
        self.global_limit = 0  # 0 = no limit
        self.per_download_limit = 0  # 0 = no limit
        self.active_downloads = {}
        self.lock = threading.Lock()
        
    def set_global_limit(self, limit_bps: int):
        """Set global bandwidth limit in bytes per second"""
        self.global_limit = limit_bps
        
    def set_per_download_limit(self, limit_bps: int):
        """Set per-download bandwidth limit in bytes per second"""
        self.per_download_limit = limit_bps
        
    def should_throttle(self, download_id: str, bytes_transferred: int) -> float:
        """Returns delay in seconds if throttling is needed"""
        with self.lock:
            current_time = time.time()
            
            if download_id not in self.active_downloads:
                self.active_downloads[download_id] = {
                    'start_time': current_time,
                    'bytes_transferred': 0,
                    'last_check': current_time
                }
            
            download_info = self.active_downloads[download_id]
            elapsed = current_time - download_info['last_check']
            download_info['bytes_transferred'] += bytes_transferred
            download_info['last_check'] = current_time
            
            # Calculate current speed
            total_elapsed = current_time - download_info['start_time']
            if total_elapsed > 0:
                current_speed = download_info['bytes_transferred'] / total_elapsed
                
                # Check per-download limit
                if self.per_download_limit > 0 and current_speed > self.per_download_limit:
                    # Calculate required delay
                    target_time = download_info['bytes_transferred'] / self.per_download_limit
                    return max(0, target_time - total_elapsed)
            
            return 0
    
    def cleanup_download(self, download_id: str):
        """Clean up tracking for completed download"""
        with self.lock:
            self.active_downloads.pop(download_id, None)

class AdvancedDownloadManager:
    """Advanced download manager with aria2-level capabilities"""
    
    def __init__(self, max_connections_per_download=16, max_concurrent_downloads=5,
                 max_chunk_size=1024*1024, connection_timeout=30, read_timeout=300):
        """
        Initialize the advanced download manager
        
        Args:
            max_connections_per_download: Maximum connections per single download
            max_concurrent_downloads: Maximum concurrent downloads
            max_chunk_size: Chunk size for downloads
            connection_timeout: Connection timeout in seconds
            read_timeout: Read timeout in seconds
        """
        self.max_connections_per_download = max_connections_per_download
        self.max_concurrent_downloads = max_concurrent_downloads
        self.max_chunk_size = max_chunk_size
        self.connection_timeout = connection_timeout
        self.read_timeout = read_timeout
        
        # Download tracking
        self.active_downloads = {}
        self.download_queue = PriorityQueue()
        self.download_history = []
        
        # Threading
        self.download_executor = ThreadPoolExecutor(max_workers=max_concurrent_downloads)
        self.queue_thread = None
        self.running = False
        
        # Bandwidth control
        self.bandwidth_controller = BandwidthController()
        
        # Connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Statistics
        self.stats = {
            'total_downloaded': 0,
            'downloads_completed': 0,
            'downloads_failed': 0,
            'average_speed': 0
        }
        
        # Start queue processor
        self.start_queue_processor()
        
        # Setup logging
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging for the download manager"""
        from logging.handlers import RotatingFileHandler
        log_dir = os.path.join(os.path.dirname(__file__), 'logs', 'runtime')
        os.makedirs(log_dir, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, 'download_manager.log'),
            maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                file_handler,
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def start_queue_processor(self):
        """Start the download queue processor"""
        self.running = True
        self.queue_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.queue_thread.start()
    
    def stop(self):
        """Stop the download manager and cleanup resources"""
        self.running = False
        if self.queue_thread:
            self.queue_thread.join(timeout=5)
        
        # Cancel active downloads
        for download_id in list(self.active_downloads.keys()):
            self.cancel_download(download_id)
        
        self.download_executor.shutdown(wait=True)
        self.session.close()
    
    def _process_queue(self):
        """Process the download queue"""
        while self.running:
            try:
                if not self.download_queue.empty() and len(self.active_downloads) < self.max_concurrent_downloads:
                    task = self.download_queue.get(timeout=1)
                    
                    # Submit download task
                    future = self.download_executor.submit(self._download_task, task)
                    self.active_downloads[task.task_id] = {
                        'task': task,
                        'future': future,
                        'status': 'starting',
                        'progress': 0,
                        'speed': 0,
                        'segments': []
                    }
                else:
                    time.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Queue processing error: {e}")
                time.sleep(1)
    
    def add_download(self, url: str, destination: str, priority: int = 5,
                    max_connections: Optional[int] = None, 
                    progress_callback: Optional[Callable] = None,
                    **options) -> str:
        """
        Add a download to the queue
        
        Args:
            url: URL to download
            destination: Destination path
            priority: Download priority (1-10, lower = higher priority)
            max_connections: Override default max connections for this download
            progress_callback: Progress callback function
            **options: Additional download options
            
        Returns:
            str: Download task ID
        """
        task_id = hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()[:16]
        
        download_options = {
            'max_connections': max_connections or self.max_connections_per_download,
            'progress_callback': progress_callback,
            'resume': options.get('resume', True),
            'verify_ssl': options.get('verify_ssl', True),
            'headers': options.get('headers', {}),
            **options
        }
        
        task = DownloadTask(
            priority=priority,
            url=url,
            destination=destination,
            options=download_options,
            task_id=task_id
        )
        
        self.download_queue.put(task)
        self.logger.info(f"Added download task {task_id} for {url}")
        
        return task_id
    
    def _download_task(self, task: DownloadTask) -> bool:
        """Execute a download task"""
        try:
            # Get file info
            file_info = self.get_file_info(task.url)
            if not file_info:
                self.logger.error(f"Failed to get file info for {task.url}")
                return False
            
            # Determine if we can use multi-connection
            supports_range = file_info.get('supports_resume', False)
            file_size = file_info.get('size', 0)
            
            if supports_range and file_size > self.max_chunk_size and task.options['max_connections'] > 1:
                return self._multi_connection_download(task, file_info)
            else:
                return self._single_connection_download(task, file_info)
        
        except Exception as e:
            self.logger.error(f"Download task {task.task_id} failed: {e}")
            self._update_download_status(task.task_id, 'failed', error=str(e))
            return False
        finally:
            # Cleanup
            self.active_downloads.pop(task.task_id, None)
            self.bandwidth_controller.cleanup_download(task.task_id)
    
    def _multi_connection_download(self, task: DownloadTask, file_info: Dict) -> bool:
        """Perform multi-connection segmented download"""
        try:
            filepath = self._get_filepath(task.destination, file_info['filename'])
            file_size = file_info['size']
            max_connections = min(task.options['max_connections'], 16)  # Cap at 16 like aria2
            
            # Create directory if needed
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Calculate segments
            segment_size = max(file_size // max_connections, self.max_chunk_size)
            segments = []
            
            for i in range(max_connections):
                start = i * segment_size
                end = min((i + 1) * segment_size - 1, file_size - 1)
                
                if start < file_size:
                    segments.append(DownloadSegment(start=start, end=end))
            
            # Store segments in active downloads
            self.active_downloads[task.task_id]['segments'] = segments
            
            # Create temporary files for segments
            temp_files = []
            for i, segment in enumerate(segments):
                temp_file = f"{filepath}.part{i}"
                temp_files.append(temp_file)
            
            # Download segments in parallel
            with ThreadPoolExecutor(max_workers=max_connections) as executor:
                futures = []
                
                for i, segment in enumerate(segments):
                    future = executor.submit(
                        self._download_segment,
                        task.task_id,
                        task.url,
                        segment,
                        temp_files[i],
                        task.options
                    )
                    futures.append(future)
                
                # Wait for all segments to complete
                completed = 0
                while completed < len(segments):
                    for i, future in enumerate(futures):
                        if future.done() and not future.exception():
                            if segments[i].status == 'downloading':
                                segments[i].status = 'completed'
                                completed += 1
                    
                    # Update progress
                    total_downloaded = sum(segment.downloaded for segment in segments)
                    progress = (total_downloaded / file_size * 100) if file_size > 0 else 0
                    
                    self._update_download_progress(task.task_id, progress, total_downloaded)
                    
                    time.sleep(0.1)
            
            # Merge segments
            self._merge_segments(filepath, temp_files)
            
            # Cleanup temp files
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
            
            self._update_download_status(task.task_id, 'completed')
            self.stats['downloads_completed'] += 1
            self.stats['total_downloaded'] += file_size
            
            return True
        
        except Exception as e:
            self.logger.error(f"Multi-connection download failed: {e}")
            self._update_download_status(task.task_id, 'failed', error=str(e))
            return False
    
    def _download_segment(self, task_id: str, url: str, segment: DownloadSegment, 
                         temp_file: str, options: Dict):
        """Download a single segment"""
        try:
            segment.status = 'downloading'
            
            headers = {
                'Range': f'bytes={segment.start}-{segment.end}',
                **options.get('headers', {})
            }
            
            response = self.session.get(
                url,
                headers=headers,
                stream=True,
                verify=options.get('verify_ssl', True),
                timeout=(self.connection_timeout, self.read_timeout)
            )
            response.raise_for_status()
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        segment.downloaded += len(chunk)
                        
                        # Apply bandwidth throttling
                        delay = self.bandwidth_controller.should_throttle(task_id, len(chunk))
                        if delay > 0:
                            time.sleep(delay)
            
            segment.status = 'completed'
            
        except Exception as e:
            segment.status = 'failed'
            self.logger.error(f"Segment download failed: {e}")
            raise
    
    def _single_connection_download(self, task: DownloadTask, file_info: Dict) -> bool:
        """Fallback to single connection download"""
        try:
            filepath = self._get_filepath(task.destination, file_info['filename'])
            
            # Create directory if needed
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Check for resume
            existing_size = 0
            if os.path.exists(filepath) and task.options.get('resume', True):
                existing_size = os.path.getsize(filepath)
            
            headers = {}
            if existing_size > 0:
                headers['Range'] = f'bytes={existing_size}-'
            
            headers.update(task.options.get('headers', {}))
            
            response = self.session.get(
                task.url,
                headers=headers,
                stream=True,
                verify=task.options.get('verify_ssl', True),
                timeout=(self.connection_timeout, self.read_timeout)
            )
            response.raise_for_status()
            
            total_size = file_info['size']
            if existing_size > 0 and response.status_code == 206:
                total_size = existing_size + int(response.headers.get('content-length', 0))
            
            downloaded = existing_size
            mode = 'ab' if existing_size > 0 else 'wb'
            
            with open(filepath, mode) as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update progress
                        progress = (downloaded / total_size * 100) if total_size > 0 else 0
                        self._update_download_progress(task.task_id, progress, downloaded)
                        
                        # Apply bandwidth throttling
                        delay = self.bandwidth_controller.should_throttle(task.task_id, len(chunk))
                        if delay > 0:
                            time.sleep(delay)
            
            self._update_download_status(task.task_id, 'completed')
            self.stats['downloads_completed'] += 1
            self.stats['total_downloaded'] += downloaded
            
            return True
        
        except Exception as e:
            self.logger.error(f"Single connection download failed: {e}")
            self._update_download_status(task.task_id, 'failed', error=str(e))
            return False
    
    def _merge_segments(self, output_file: str, temp_files: List[str]):
        """Merge downloaded segments into final file"""
        with open(output_file, 'wb') as output:
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    with open(temp_file, 'rb') as temp:
                        while True:
                            chunk = temp.read(8192)
                            if not chunk:
                                break
                            output.write(chunk)
    
    def _update_download_progress(self, task_id: str, progress: float, downloaded: int):
        """Update download progress"""
        if task_id in self.active_downloads:
            download_info = self.active_downloads[task_id]
            download_info['progress'] = progress
            
            # Calculate speed
            task = download_info['task']
            elapsed = (datetime.now() - task.created_at).total_seconds()
            if elapsed > 0:
                speed = downloaded / elapsed
                download_info['speed'] = speed
                
                # Call progress callback if provided
                if task.options.get('progress_callback'):
                    task.options['progress_callback']({
                        'task_id': task_id,
                        'filename': os.path.basename(task.destination),
                        'progress': f"{progress:.1f}%",
                        'speed': self._format_speed(speed),
                        'status': 'downloading',
                        'downloaded': downloaded
                    })
    
    def _update_download_status(self, task_id: str, status: str, error: Optional[str] = None):
        """Update download status"""
        if task_id in self.active_downloads:
            download_info = self.active_downloads[task_id]
            download_info['status'] = status
            
            if error:
                download_info['error'] = error
            
            task = download_info['task']
            if task.options.get('progress_callback'):
                task.options['progress_callback']({
                    'task_id': task_id,
                    'filename': os.path.basename(task.destination),
                    'progress': "100%" if status == 'completed' else "0%",
                    'speed': "0 B/s",
                    'status': status,
                    'error': error
                })
    
    def get_file_info(self, url: str) -> Optional[Dict]:
        """Get file information from URL"""
        try:
            response = self.session.head(url, allow_redirects=True, timeout=10)
            response.raise_for_status()
            
            size = int(response.headers.get('content-length', 0))
            content_type = response.headers.get('content-type', 'Unknown')
            filename = self._get_filename_from_url(url, response)
            
            return {
                'filename': filename,
                'size': size,
                'size_formatted': self._format_size(size),
                'content_type': content_type,
                'supports_resume': 'accept-ranges' in response.headers.get('accept-ranges', '').lower()
            }
        except Exception as e:
            self.logger.error(f"Failed to get file info: {e}")
            return None
    
    def _get_filename_from_url(self, url: str, response: Optional[requests.Response] = None) -> str:
        """Extract filename from URL or response headers"""
        # Try Content-Disposition header first
        if response and 'content-disposition' in response.headers:
            content_disposition = response.headers['content-disposition']
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[1].strip('"\'')
                return unquote(filename)
        
        # Extract from URL
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        
        if not filename or '.' not in filename:
            filename = f"download_{hashlib.md5(url.encode()).hexdigest()[:8]}"
        
        return unquote(filename)
    
    def _get_filepath(self, destination: str, filename: str) -> str:
        """Get the full file path"""
        if os.path.isdir(destination):
            return os.path.join(destination, filename)
        return destination
    
    def _format_size(self, bytes_size: int) -> str:
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"
    
    def _format_speed(self, bytes_per_second: float) -> str:
        """Format download speed in human readable format"""
        return f"{self._format_size(bytes_per_second)}/s"
    
    def cancel_download(self, task_id: str) -> bool:
        """Cancel a download"""
        if task_id in self.active_downloads:
            download_info = self.active_downloads[task_id]
            future = download_info.get('future')
            
            if future and not future.done():
                future.cancel()
                
            self._update_download_status(task_id, 'cancelled')
            return True
        
        return False
    
    def pause_download(self, task_id: str) -> bool:
        """Pause a download (implementation depends on specific requirements)"""
        # For now, this cancels the download
        # In a full implementation, you'd need to track pause state
        return self.cancel_download(task_id)
    
    def get_download_status(self, task_id: str) -> Optional[Dict]:
        """Get download status"""
        return self.active_downloads.get(task_id)
    
    def get_active_downloads(self) -> Dict:
        """Get all active downloads"""
        return self.active_downloads.copy()
    
    def get_stats(self) -> Dict:
        """Get download statistics"""
        return self.stats.copy()
    
    def set_global_bandwidth_limit(self, limit_bps: int):
        """Set global bandwidth limit"""
        self.bandwidth_controller.set_global_limit(limit_bps)
    
    def set_per_download_bandwidth_limit(self, limit_bps: int):
        """Set per-download bandwidth limit"""
        self.bandwidth_controller.set_per_download_limit(limit_bps)
    
    def validate_url(self, url: str) -> bool:
        """Validate if URL is downloadable"""
        try:
            response = self.session.head(url, allow_redirects=True, timeout=10)
            return response.status_code == 200
        except:
            return False