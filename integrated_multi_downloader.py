"""
Integrated Multi-Connection HTTP Downloader V2.1
Safe integration with existing download manager - no claims, only verified behavior
"""

import os
import requests
import threading
import time
import json
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, List, Callable, Tuple
from http_range_detector import supports_http_range

# Module logger
logger = logging.getLogger(__name__)

class SegmentDownloader:
    """Downloads a single segment of a file"""
    
    def __init__(self, url: str, start: int, end: int, part_file: str, 
                 segment_id: int, timeout: int = 30, resume_from: int = 0, cancel_event: threading.Event = None):
        self.url = url
        self.start = start
        self.end = end
        self.part_file = part_file
        self.segment_id = segment_id
        self.timeout = timeout
        self.resume_from = resume_from  # Bytes already downloaded
        self.cancel_event = cancel_event  # Cancellation signal
        
        self.downloaded_bytes = resume_from
        self.status = 'pending'
        self.error = None
        
    def download(self) -> bool:
        """Download the segment to its part file"""
        try:
            self.status = 'downloading'
            
            # Calculate actual start position for resume
            actual_start = self.start + self.resume_from
            if actual_start > self.end:
                # Segment already complete
                self.status = 'completed'
                logger.info(f"Segment {self.segment_id}: already complete")
                return True
                
            headers = {'Range': f'bytes={actual_start}-{self.end}'}
            mode = 'ab' if self.resume_from > 0 else 'wb'
            
            logger.info(f"Segment {self.segment_id}: downloading bytes {actual_start}-{self.end} (resume from {self.resume_from})")
            
            response = requests.get(self.url, headers=headers, stream=True, 
                                  allow_redirects=True, timeout=self.timeout)
            
            if response.status_code != 206:
                if response.status_code == 200:
                    self.status = 'failed'
                    self.error = 'range ignored'
                    logger.error(f"Segment {self.segment_id}: range ignored (got 200 instead of 206)")
                    return False
                raise Exception(f"Unexpected status code: {response.status_code}")
                
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.part_file), exist_ok=True)
            
            # Write segment data
            with open(self.part_file, mode) as f:
                for chunk in response.iter_content(chunk_size=8192):
                    # Check for cancellation
                    if self.cancel_event and self.cancel_event.is_set():
                        self.status = 'cancelled'
                        logger.info(f"Segment {self.segment_id}: cancelled by user")
                        return False
                        
                    if chunk:
                        f.write(chunk)
                        self.downloaded_bytes += len(chunk)
            
            self.status = 'completed'
            logger.info(f"Segment {self.segment_id}: completed {self.downloaded_bytes} bytes")
            return True
            
        except Exception as e:
            self.status = 'failed'
            self.error = str(e)
            logger.error(f"Segment {self.segment_id}: failed - {self.error}")
            return False

class IntegratedMultiDownloader:
    """
    Integrated multi-connection downloader with safe fallback
    Only uses multi-connection for verified Range-capable servers
    """
    
    def __init__(self, max_connections: int = 4, segment_size: int = 8 * 1024 * 1024):
        self.max_connections = max_connections
        self.segment_size = segment_size  # 8MB default
        self.timeout = 30
        self.cancel_event = threading.Event()  # For cancellation support
        
    def cancel_download(self):
        """Cancel the current download"""
        self.cancel_event.set()
        logger.info("Download cancellation requested")
        
    def _get_state_file_path(self, destination: str) -> str:
        """Get path to state file for resume functionality"""
        return f"{destination}.downloadstate.json"
    
    def _save_state(self, url: str, destination: str, total_size: int, segments: list, 
                   etag: str = None, last_modified: str = None):
        """Save download state for resume"""
        state = {
            'url': url,
            'destination': destination,
            'total_size': total_size,
            'segment_size': self.segment_size,
            'max_connections': self.max_connections,
            'etag': etag,
            'last_modified': last_modified,
            'segments': [
                {
                    'id': seg_id,
                    'start': start,
                    'end': end,
                    'part_file': part_file,
                    'completed': False,
                    'bytes_written': 0
                }
                for start, end, part_file, seg_id in segments
            ]
        }
        
        state_file = self._get_state_file_path(destination)
        try:
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
            logger.info(f"Saved download state to {state_file}")
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")
    
    def _load_state(self, destination: str) -> Optional[Dict]:
        """Load download state for resume"""
        state_file = self._get_state_file_path(destination)
        if not os.path.exists(state_file):
            return None
            
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
            logger.info(f"Loaded download state from {state_file}")
            return state
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
            return None
    
    def _archive_old_state(self, destination: str):
        """Archive old state and part files"""
        import time
        timestamp = int(time.time())
        
        state_file = self._get_state_file_path(destination)
        if os.path.exists(state_file):
            archived_state = f"{state_file}.{timestamp}.archived"
            os.rename(state_file, archived_state)
            logger.info(f"Archived old state to {archived_state}")
        
        # Archive part files
        for i in range(self.max_connections * 2):  # Check more than max to be safe
            part_file = f"{destination}.part{i:03d}"
            if os.path.exists(part_file):
                archived_part = f"{part_file}.{timestamp}.archived"
                os.rename(part_file, archived_part)
                logger.info(f"Archived old part file to {archived_part}")
    
    def _validate_state_compatibility(self, state: Dict, url: str, total_size: int, 
                                    etag: str = None, last_modified: str = None) -> bool:
        """Validate if existing state is compatible for resume"""
        if state['url'] != url:
            logger.info(f"State mismatch: URL changed ({state['url']} vs {url})")
            return False
            
        if state['total_size'] != total_size:
            logger.info(f"State mismatch: size changed ({state['total_size']} vs {total_size})")
            return False
            
        # Check etag/last-modified if available
        if etag and state.get('etag') and state['etag'] != etag:
            logger.info(f"State mismatch: etag changed ({state['etag']} vs {etag})")
            return False
            
        if last_modified and state.get('last_modified') and state['last_modified'] != last_modified:
            logger.info(f"State mismatch: last-modified changed ({state['last_modified']} vs {last_modified})")
            return False
            
        return True
    
    def _check_segment_completion(self, segments_state: list) -> list:
        """Check which segments are complete and update state"""
        for seg_state in segments_state:
            part_file = seg_state['part_file']
            expected_size = seg_state['end'] - seg_state['start'] + 1
            
            if os.path.exists(part_file):
                actual_size = os.path.getsize(part_file)
                if actual_size == expected_size:
                    seg_state['completed'] = True
                    seg_state['bytes_written'] = actual_size
                    logger.info(f"Segment {seg_state['id']}: already complete ({actual_size} bytes)")
                elif actual_size > 0:
                    seg_state['bytes_written'] = actual_size
                    logger.info(f"Segment {seg_state['id']}: partially complete ({actual_size}/{expected_size} bytes)")
                else:
                    seg_state['bytes_written'] = 0
            else:
                seg_state['bytes_written'] = 0
                
        return segments_state
        
    def download(self, url: str, destination: str, progress_callback: Optional[Callable] = None) -> Tuple[bool, Dict]:
        """
        Download a file using multi-connection if server supports it
        
        Args:
            url: URL to download
            destination: Full path to destination file
            progress_callback: Optional progress callback function
            
        Returns:
            tuple: (success: bool, info: dict)
        """
        
        info = {
            'url': url,
            'destination': destination,
            'mode': 'unknown',
            'connections_used': 0,
            'total_size': 0,
            'download_time': 0,
            'segments_info': [],
            'range_support_info': {}
        }
        
        start_time = time.time()
        
        try:
            # Step 1: Check if server supports range requests
            supports_range, range_info = supports_http_range(url)
            info['range_support_info'] = range_info
            
            # Step 2: Get content length and etag/last-modified for resume validation
            head_resp = requests.head(url, allow_redirects=True, timeout=self.timeout)
            content_length = head_resp.headers.get('content-length')
            etag = head_resp.headers.get('etag')
            last_modified = head_resp.headers.get('last-modified')
            
            if not content_length:
                logger.info(f"Multi-connection: no content-length, using single connection")
                return self._single_connection_download(url, destination, progress_callback, info)
                
            total_size = int(content_length)
            info['total_size'] = total_size
            
            # Step 3: Decide on download mode
            min_size_threshold = 8 * 1024 * 1024  # 8MB minimum for multi-connection
            
            if not supports_range:
                logger.info(f"Multi-connection: server does not support ranges, using single connection")
                return self._single_connection_download(url, destination, progress_callback, info)
            elif total_size < min_size_threshold:
                logger.info(f"Multi-connection: file too small ({total_size} bytes), using single connection")
                return self._single_connection_download(url, destination, progress_callback, info)
            else:
                logger.info(f"Multi-connection: using {self.max_connections} connections for {total_size} bytes")
                return self._multi_connection_download(url, destination, total_size, progress_callback, info, etag, last_modified)
                
        except Exception as e:
            logger.error(f"Multi-connection: error during setup, falling back to single: {e}")
            return self._single_connection_download(url, destination, progress_callback, info)
        finally:
            info['download_time'] = time.time() - start_time
    
    def _single_connection_download(self, url: str, destination: str, 
                                   progress_callback: Optional[Callable], info: Dict) -> Tuple[bool, Dict]:
        """Single connection download (fallback)"""
        info['mode'] = 'single'
        info['connections_used'] = 1
        
        try:
            logger.info(f"Single-connection: downloading {url}")
            
            response = requests.get(url, stream=True, allow_redirects=True, timeout=self.timeout)
            response.raise_for_status()
            
            if not info['total_size']:
                info['total_size'] = int(response.headers.get('content-length', 0))
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            
            # Download to temp file first
            temp_file = f"{destination}.tmp"
            downloaded_bytes = 0
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        # Check for cancellation
                        if self.cancel_event.is_set():
                            logger.info("Single-connection: download cancelled")
                            # Delete temp file and return (no resume for single connection)
                            if os.path.exists(temp_file):
                                os.remove(temp_file)
                            info['mode'] = 'cancelled'
                            info['connections_used'] = 0
                            info['error'] = 'User cancelled'
                            return False, info
                            
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        
                        # Progress callback
                        if progress_callback and info['total_size'] > 0:
                            progress = (downloaded_bytes / info['total_size']) * 100
                            progress_callback({
                                'filename': os.path.basename(destination),
                                'progress': f"{progress:.1f}%",
                                'status': 'Downloading (single connection)'
                            })
            
            # Atomic move
            os.replace(temp_file, destination)
            
            logger.info(f"Single-connection: completed {downloaded_bytes} bytes")
            
            if progress_callback:
                progress_callback({
                    'filename': os.path.basename(destination),
                    'progress': "100%",
                    'status': 'Completed'
                })
            
            return True, info
            
        except Exception as e:
            # Cleanup temp file
            temp_file = f"{destination}.tmp"
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
            logger.error(f"Single-connection: failed - {e}")
            return False, info
    
    def _multi_connection_download(self, url: str, destination: str, total_size: int,
                                  progress_callback: Optional[Callable], info: Dict,
                                  etag: str = None, last_modified: str = None) -> Tuple[bool, Dict]:
        """Multi-connection download for Range-capable servers with resume support"""
        info['mode'] = 'multi'
        info['connections_used'] = self.max_connections
        
        try:
            # Check for existing state
            state = self._load_state(destination)
            resume_segments = None
            
            if state and self._validate_state_compatibility(state, url, total_size, etag, last_modified):
                logger.info("Compatible state found - attempting resume")
                resume_segments = self._check_segment_completion(state['segments'])
                segments = [(s['start'], s['end'], s['part_file'], s['id']) for s in resume_segments]
            else:
                if state:
                    logger.info("Incompatible state found - archiving and starting fresh")
                    self._archive_old_state(destination)
                
                # Calculate new segments
                segment_size = max(self.segment_size, total_size // self.max_connections)
                segments = []
                
                for i in range(self.max_connections):
                    start = i * segment_size
                    end = min((i + 1) * segment_size - 1, total_size - 1)
                    if start > total_size - 1:
                        break
                        
                    part_file = f"{destination}.part{i:03d}"
                    segments.append((start, end, part_file, i))
                
                # Save initial state
                self._save_state(url, destination, total_size, segments, etag, last_modified)
            
            part_files = [part_file for _, _, part_file, _ in segments]
            
            for i, (start, end, part_file, segment_id) in enumerate(segments):
                info['segments_info'].append({
                    'id': segment_id,
                    'start': start,
                    'end': end,
                    'size': end - start + 1,
                    'part_file': os.path.basename(part_file)
                })
            
            logger.info(f"Multi-connection: using {len(segments)} segments")
            
            # Download segments in parallel
            threads = []
            downloaders = []
            
            for start, end, part_file, segment_id in segments:
                # Determine resume offset
                resume_from = 0
                if resume_segments:
                    for seg_state in resume_segments:
                        if seg_state['id'] == segment_id:
                            if seg_state['completed']:
                                resume_from = seg_state['end'] - seg_state['start'] + 1  # Fully complete
                            else:
                                resume_from = seg_state['bytes_written']  # Partial
                            break
                
                downloader = SegmentDownloader(url, start, end, part_file, segment_id, self.timeout, resume_from, self.cancel_event)
                downloaders.append(downloader)
                
                thread = threading.Thread(target=downloader.download)
                threads.append(thread)
                thread.start()
            
            # Monitor progress
            while any(t.is_alive() for t in threads):
                if progress_callback:
                    total_downloaded = sum(d.downloaded_bytes for d in downloaders)
                    progress = (total_downloaded / total_size) * 100
                    active_segments = sum(1 for d in downloaders if d.status == 'downloading')
                    
                    progress_callback({
                        'filename': os.path.basename(destination),
                        'progress': f"{progress:.1f}%",
                        'status': f'Downloading ({active_segments} connections active)'
                    })
                
                time.sleep(0.5)
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Check if all segments succeeded
            failed_segments = [d for d in downloaders if d.status != 'completed']
            if failed_segments:
                raise Exception(f"{len(failed_segments)} segments failed")
            
            # Validate each part size equals expected size
            for i, (start, end, part_file, segment_id) in enumerate(segments):
                expected_size = end - start + 1
                actual_size = os.path.getsize(part_file)
                if actual_size != expected_size:
                    raise Exception(f"Segment {segment_id}: size mismatch (expected {expected_size}, got {actual_size})")

            # Merge segments into final file using streaming chunks
            logger.info("Multi-connection: merging segments")
            temp_file = f"{destination}.tmp"
            
            merged_size = 0
            with open(temp_file, 'wb') as outfile:
                for _, _, part_file, _ in segments:
                    with open(part_file, 'rb') as infile:
                        while True:
                            chunk = infile.read(8192)
                            if not chunk:
                                break
                            outfile.write(chunk)
                            merged_size += len(chunk)
            
            # Validate merged temp file size == total_size before finalize
            if merged_size != total_size:
                raise Exception(f"Merged file size mismatch (expected {total_size}, got {merged_size})")
            
            # Atomic move
            os.replace(temp_file, destination)
            
            # Cleanup part files
            for part_file in part_files:
                if os.path.exists(part_file):
                    os.remove(part_file)
            
            # Cleanup state file after successful completion
            state_file = self._get_state_file_path(destination)
            if os.path.exists(state_file):
                os.remove(state_file)
                logger.info("Removed download state file after successful completion")
            
            logger.info(f"Multi-connection: completed {total_size} bytes using {len(segments)} connections")
            
            if progress_callback:
                progress_callback({
                    'filename': os.path.basename(destination),
                    'progress': "100%",
                    'status': 'Completed'
                })
            
            return True, info
            
        except Exception as e:
            # Check if this was a cancellation
            if self.cancel_event.is_set():
                logger.info("Multi-connection: Download cancelled by user")
                # Preserve part files and state file for resume
                info['mode'] = 'cancelled'
                info['connections_used'] = 0
                info['error'] = 'User cancelled'
                return False, info
            
            # Cleanup temp file on non-cancel failure, but keep part files for potential resume
            temp_file = f"{destination}.tmp"
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
            # Only remove part files if they are corrupted, not on normal failure
            # (This allows resume to work with partial downloads)
            
            logger.error(f"Multi-connection: failed - {e}")
            
            # Fallback to single connection only on non-cancel failures
            logger.info("Multi-connection: falling back to single connection")
            return self._single_connection_download(url, destination, progress_callback, info)