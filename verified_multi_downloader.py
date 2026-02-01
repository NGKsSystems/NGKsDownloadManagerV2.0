"""
True Multi-Connection HTTP Downloader V2.1
Implements verified multi-connection downloads with proper server capability detection
"""

import os
import requests
import threading
import time
import hashlib
import json
import logging
from urllib.parse import urlparse
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import socket

@dataclass
class SegmentState:
    """Represents the state of a download segment"""
    segment_id: int
    start_byte: int
    end_byte: int
    downloaded_bytes: int
    status: str  # pending, downloading, completed, failed, stalled
    thread_id: Optional[str] = None
    start_time: Optional[float] = None
    last_activity: Optional[float] = None
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)

class ServerCapability:
    """Detects and validates server capabilities for multi-connection downloads"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.ServerCapability")
    
    def check_multi_connection_support(self, url: str) -> Tuple[bool, Dict]:
        """
        Explicitly check if server supports multi-connection downloads
        
        Returns:
            (supports_multi_conn, capability_info)
        """
        self.logger.info(f"Checking server capabilities for: {url}")
        
        try:
            # Perform HEAD request to check capabilities
            response = requests.head(url, allow_redirects=True, timeout=10)
            response.raise_for_status()
            
            headers = response.headers
            
            # Check for Accept-Ranges header
            accept_ranges = headers.get('accept-ranges', '').lower()
            content_length = headers.get('content-length')
            
            capability_info = {
                'url': url,
                'final_url': response.url,
                'status_code': response.status_code,
                'accept_ranges': accept_ranges,
                'content_length': content_length,
                'supports_ranges': accept_ranges == 'bytes',
                'has_content_length': content_length is not None,
                'headers': dict(headers)
            }
            
            # Multi-connection requirements
            supports_multi = (
                capability_info['supports_ranges'] and 
                capability_info['has_content_length'] and
                int(content_length or 0) > 0
            )
            
            if supports_multi:
                self.logger.info(f"✅ Multi-connection supported: {url}")
                self.logger.info(f"   Accept-Ranges: {accept_ranges}")
                self.logger.info(f"   Content-Length: {content_length}")
            else:
                self.logger.warning(f"❌ Multi-connection NOT supported: {url}")
                self.logger.warning(f"   Accept-Ranges: {accept_ranges}")
                self.logger.warning(f"   Content-Length: {content_length}")
            
            return supports_multi, capability_info
            
        except Exception as e:
            self.logger.error(f"Failed to check server capabilities: {e}")
            return False, {'error': str(e)}

class SegmentCoordinator:
    """Central coordinator for managing download segments"""
    
    def __init__(self, file_size: int, max_connections: int = 4):
        self.file_size = file_size
        self.max_connections = min(max_connections, 8)  # Cap at 8
        self.segments: List[SegmentState] = []
        self.lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.SegmentCoordinator")
        
        # Performance tracking
        self.active_connections = 0
        self.completed_segments = 0
        self.stall_timeout = 30.0  # seconds
        
        self._create_segments()
    
    def _create_segments(self):
        """Create download segments based on file size and connection count"""
        if self.file_size <= 0:
            self.logger.error("Cannot create segments for unknown file size")
            return
        
        # Calculate segment size
        segment_size = self.file_size // self.max_connections
        
        self.logger.info(f"Creating {self.max_connections} segments for {self.file_size} bytes")
        self.logger.info(f"Segment size: {segment_size} bytes")
        
        for i in range(self.max_connections):
            start_byte = i * segment_size
            
            if i == self.max_connections - 1:
                # Last segment gets remainder
                end_byte = self.file_size - 1
            else:
                end_byte = start_byte + segment_size - 1
            
            segment = SegmentState(
                segment_id=i,
                start_byte=start_byte,
                end_byte=end_byte,
                downloaded_bytes=0,
                status='pending'
            )
            
            self.segments.append(segment)
            self.logger.debug(f"Created segment {i}: bytes {start_byte}-{end_byte}")
    
    def get_next_segment(self, thread_id: str) -> Optional[SegmentState]:
        """Get next available segment for download"""
        with self.lock:
            for segment in self.segments:
                if segment.status == 'pending':
                    segment.status = 'downloading'
                    segment.thread_id = thread_id
                    segment.start_time = time.time()
                    segment.last_activity = time.time()
                    self.active_connections += 1
                    
                    self.logger.info(f"Assigned segment {segment.segment_id} to thread {thread_id}")
                    return segment
            
            return None
    
    def update_segment_progress(self, segment_id: int, downloaded_bytes: int):
        """Update segment download progress"""
        with self.lock:
            if segment_id < len(self.segments):
                segment = self.segments[segment_id]
                segment.downloaded_bytes = downloaded_bytes
                segment.last_activity = time.time()
    
    def complete_segment(self, segment_id: int, thread_id: str):
        """Mark segment as completed"""
        with self.lock:
            if segment_id < len(self.segments):
                segment = self.segments[segment_id]
                segment.status = 'completed'
                self.active_connections = max(0, self.active_connections - 1)
                self.completed_segments += 1
                
                self.logger.info(f"Segment {segment_id} completed by thread {thread_id}")
                self.logger.info(f"Progress: {self.completed_segments}/{len(self.segments)} segments")
    
    def fail_segment(self, segment_id: int, thread_id: str, error: str):
        """Mark segment as failed"""
        with self.lock:
            if segment_id < len(self.segments):
                segment = self.segments[segment_id]
                segment.status = 'failed'
                self.active_connections = max(0, self.active_connections - 1)
                
                self.logger.error(f"Segment {segment_id} failed by thread {thread_id}: {error}")
    
    def check_for_stalled_segments(self) -> List[SegmentState]:
        """Detect and reassign stalled segments"""
        stalled = []
        current_time = time.time()
        
        with self.lock:
            for segment in self.segments:
                if (segment.status == 'downloading' and 
                    segment.last_activity and 
                    current_time - segment.last_activity > self.stall_timeout):
                    
                    self.logger.warning(f"Segment {segment.segment_id} stalled, reassigning")
                    segment.status = 'pending'
                    segment.thread_id = None
                    self.active_connections = max(0, self.active_connections - 1)
                    stalled.append(segment)
        
        return stalled
    
    def is_complete(self) -> bool:
        """Check if all segments are completed"""
        with self.lock:
            return self.completed_segments == len(self.segments)
    
    def get_progress_info(self) -> Dict:
        """Get current progress information"""
        with self.lock:
            total_downloaded = sum(s.downloaded_bytes for s in self.segments)
            
            return {
                'total_segments': len(self.segments),
                'completed_segments': self.completed_segments,
                'active_connections': self.active_connections,
                'total_downloaded': total_downloaded,
                'file_size': self.file_size,
                'progress_percent': (total_downloaded / self.file_size * 100) if self.file_size > 0 else 0,
                'segments': [s.to_dict() for s in self.segments]
            }

class MultiConnectionDownloader:
    """True multi-connection HTTP downloader with verification"""
    
    def __init__(self, max_connections: int = 4, chunk_size: int = 8192):
        self.max_connections = min(max_connections, 8)  # Cap at 8
        self.chunk_size = chunk_size
        self.logger = logging.getLogger(f"{__name__}.MultiConnectionDownloader")
        
        # Components
        self.capability_checker = ServerCapability()
        
        # Session configuration for connection reuse
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NGKs-Download-Manager-V2.1'
        })
        
        # Performance tracking
        self.download_stats = {}
    
    def download_file(self, url: str, output_path: str, 
                     progress_callback=None) -> Tuple[bool, Dict]:
        """
        Download file with multi-connection support and verification
        
        Returns:
            (success, detailed_info)
        """
        download_id = hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()[:12]
        self.logger.info(f"Starting download {download_id}: {url}")
        
        # Check server capabilities
        supports_multi, capability_info = self.capability_checker.check_multi_connection_support(url)
        
        if not supports_multi:
            self.logger.info("Falling back to single-connection download")
            return self._single_connection_download(url, output_path, download_id, capability_info)
        
        # Multi-connection download
        file_size = int(capability_info['content_length'])
        self.logger.info(f"Starting multi-connection download: {file_size} bytes with {self.max_connections} connections")
        
        return self._multi_connection_download(url, output_path, file_size, download_id, capability_info, progress_callback)
    
    def _multi_connection_download(self, url: str, output_path: str, file_size: int, 
                                  download_id: str, capability_info: Dict, progress_callback=None) -> Tuple[bool, Dict]:
        """Perform verified multi-connection download"""
        
        # Create segment coordinator
        coordinator = SegmentCoordinator(file_size, self.max_connections)
        
        # Create temporary files for segments
        temp_dir = os.path.dirname(output_path)
        os.makedirs(temp_dir, exist_ok=True)
        
        segment_files = []
        for i in range(self.max_connections):
            temp_file = f"{output_path}.part{i}.tmp"
            segment_files.append(temp_file)
        
        # Start download threads
        download_start = time.time()
        success = False
        
        try:
            with ThreadPoolExecutor(max_workers=self.max_connections, 
                                  thread_name_prefix=f"DL-{download_id}") as executor:
                
                # Submit download tasks
                futures = []
                for i in range(self.max_connections):
                    future = executor.submit(
                        self._download_segment_worker,
                        url, coordinator, segment_files[i], download_id, progress_callback
                    )
                    futures.append(future)
                
                # Monitor progress
                while not coordinator.is_complete():
                    # Check for stalled segments
                    coordinator.check_for_stalled_segments()
                    
                    # Log progress
                    progress_info = coordinator.get_progress_info()
                    self.logger.info(f"Download {download_id} progress: {progress_info['progress_percent']:.1f}% "
                                   f"({progress_info['active_connections']} active connections)")
                    
                    if progress_callback:
                        progress_callback(progress_info)
                    
                    time.sleep(1)
                
                # Wait for all futures to complete
                for future in as_completed(futures, timeout=60):
                    try:
                        future.result()
                    except Exception as e:
                        self.logger.error(f"Segment download failed: {e}")
            
            # Merge segments
            success = self._merge_segments(segment_files, output_path, file_size)
            
        except Exception as e:
            self.logger.error(f"Multi-connection download failed: {e}")
            success = False
        
        finally:
            # Cleanup temporary files
            for temp_file in segment_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
        
        download_time = time.time() - download_start
        
        # Compile detailed info
        final_progress = coordinator.get_progress_info()
        detailed_info = {
            'download_id': download_id,
            'success': success,
            'download_time': download_time,
            'file_size': file_size,
            'connections_used': self.max_connections,
            'throughput_bps': file_size / download_time if download_time > 0 else 0,
            'capability_info': capability_info,
            'final_progress': final_progress,
            'mode': 'multi-connection'
        }
        
        if success:
            self.logger.info(f"Multi-connection download completed: {download_time:.2f}s, "
                           f"{final_progress['total_downloaded']} bytes, "
                           f"{detailed_info['throughput_bps']:.0f} B/s")
        else:
            self.logger.error(f"Multi-connection download failed after {download_time:.2f}s")
        
        return success, detailed_info
    
    def _download_segment_worker(self, url: str, coordinator: SegmentCoordinator, 
                                temp_file: str, download_id: str, progress_callback=None):
        """Worker thread for downloading a segment"""
        thread_id = threading.current_thread().name
        self.logger.info(f"Worker {thread_id} started for download {download_id}")
        
        while True:
            segment = coordinator.get_next_segment(thread_id)
            if not segment:
                self.logger.info(f"Worker {thread_id} finished - no more segments")
                break
            
            try:
                self._download_single_segment(url, segment, temp_file, coordinator, thread_id)
                coordinator.complete_segment(segment.segment_id, thread_id)
                
            except Exception as e:
                self.logger.error(f"Segment {segment.segment_id} download failed: {e}")
                coordinator.fail_segment(segment.segment_id, thread_id, str(e))
                break
    
    def _download_single_segment(self, url: str, segment: SegmentState, 
                                temp_file: str, coordinator: SegmentCoordinator, thread_id: str):
        """Download a single segment with range request"""
        
        # Create range header
        range_header = f"bytes={segment.start_byte}-{segment.end_byte}"
        headers = {'Range': range_header}
        
        self.logger.debug(f"Thread {thread_id} downloading segment {segment.segment_id}: {range_header}")
        
        # Open new connection for this segment
        response = self.session.get(url, headers=headers, stream=True, timeout=(10, 30))
        response.raise_for_status()
        
        # Verify partial content response
        if response.status_code != 206:
            raise Exception(f"Expected 206 Partial Content, got {response.status_code}")
        
        expected_size = segment.end_byte - segment.start_byte + 1
        downloaded = 0
        
        # Write segment to temporary file
        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=self.chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    coordinator.update_segment_progress(segment.segment_id, downloaded)
        
        # Verify segment size
        if downloaded != expected_size:
            raise Exception(f"Segment size mismatch: expected {expected_size}, got {downloaded}")
        
        self.logger.debug(f"Thread {thread_id} completed segment {segment.segment_id}: {downloaded} bytes")
    
    def _merge_segments(self, segment_files: List[str], output_path: str, expected_size: int) -> bool:
        """Merge downloaded segments into final file"""
        self.logger.info(f"Merging {len(segment_files)} segments into {output_path}")
        
        try:
            total_written = 0
            
            with open(output_path, 'wb') as output_file:
                for i, segment_file in enumerate(segment_files):
                    if not os.path.exists(segment_file):
                        self.logger.error(f"Segment file {i} missing: {segment_file}")
                        return False
                    
                    with open(segment_file, 'rb') as f:
                        chunk_count = 0
                        while True:
                            chunk = f.read(self.chunk_size)
                            if not chunk:
                                break
                            output_file.write(chunk)
                            total_written += len(chunk)
                            chunk_count += 1
                    
                    self.logger.debug(f"Merged segment {i}: {chunk_count} chunks")
            
            # Verify final file size
            if total_written != expected_size:
                self.logger.error(f"Final file size mismatch: expected {expected_size}, got {total_written}")
                return False
            
            self.logger.info(f"Successfully merged file: {total_written} bytes")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to merge segments: {e}")
            return False
    
    def _single_connection_download(self, url: str, output_path: str, 
                                   download_id: str, capability_info: Dict) -> Tuple[bool, Dict]:
        """Fallback single-connection download"""
        self.logger.info(f"Single-connection download {download_id}")
        
        download_start = time.time()
        
        try:
            response = self.session.get(url, stream=True, timeout=(10, 300))
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
            
            download_time = time.time() - download_start
            success = True
            
            self.logger.info(f"Single-connection download completed: {download_time:.2f}s, {downloaded} bytes")
            
        except Exception as e:
            self.logger.error(f"Single-connection download failed: {e}")
            download_time = time.time() - download_start
            downloaded = 0
            success = False
        
        detailed_info = {
            'download_id': download_id,
            'success': success,
            'download_time': download_time,
            'file_size': downloaded,
            'connections_used': 1,
            'throughput_bps': downloaded / download_time if download_time > 0 else 0,
            'capability_info': capability_info,
            'mode': 'single-connection'
        }
        
        return success, detailed_info

# Configure logging
def setup_logging(level=logging.INFO):
    """Setup logging for multi-connection downloader"""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('multi_connection_downloader.log')
        ]
    )

if __name__ == "__main__":
    # Example usage
    setup_logging(logging.DEBUG)
    
    downloader = MultiConnectionDownloader(max_connections=4)
    
    # Test URL (should support ranges)
    test_url = "https://httpbin.org/bytes/1048576"  # 1MB
    output_file = "./test_download.bin"
    
    success, info = downloader.download_file(test_url, output_file)
    
    print(f"Download success: {success}")
    print(f"Details: {info}")