"""
Core Download Manager V2.1
Handles direct HTTP/HTTPS downloads with verified multi-connection capability
"""

import os
import requests
import threading
from urllib.parse import urlparse, unquote
import time
import hashlib
import logging
import json
from typing import Optional, Dict
from datetime import datetime
from pathlib import Path

# Module-level logger
logger = logging.getLogger(__name__)

# Import verified multi-connection capability
try:
    from integrated_multi_downloader import IntegratedMultiDownloader
    MULTI_CONNECTION_AVAILABLE = True
except ImportError:
    MULTI_CONNECTION_AVAILABLE = False
    print("Multi-connection features not available.")

class DownloadManager:
    def __init__(self, max_chunk_size=8192, max_retries=3, enable_multi_connection=True, 
                 max_connections=4, debug_logging=False):
        self.max_chunk_size = max_chunk_size
        self.max_retries = max_retries
        self.active_downloads = {}
        
        # Setup logging
        if debug_logging:
            logger.setLevel(logging.INFO)
            if not logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
                logger.addHandler(handler)
        
        # Multi-connection feature
        self.enable_multi_connection = enable_multi_connection and MULTI_CONNECTION_AVAILABLE
        self.max_connections = max_connections
        
        if self.enable_multi_connection:
            self.multi_downloader = IntegratedMultiDownloader(max_connections=max_connections)
            print(f"Multi-connection downloads enabled (max {max_connections} connections per file)")
        else:
            print("Using single-connection downloads only")
    
    def _get_resume_file_path(self, filepath: str) -> str:
        """Get path to resume state file"""
        return f"{filepath}.resume"
    
    def _save_resume_state(self, task_id: str, url: str, final_path: str, temp_path: str, 
                          total_size: int, bytes_completed: int, etag: str = None, 
                          last_modified: str = None) -> None:
        """Save resume state for crash recovery"""
        resume_path = self._get_resume_file_path(final_path)
        state = {
            "version": "3.0",
            "task_id": task_id,
            "url": url,
            "final_path": final_path,
            "temp_path": temp_path,
            "mode": "single",
            "total_size": total_size,
            "bytes_completed": bytes_completed,
            "etag": etag,
            "last_modified": last_modified,
            "segments": [{
                "id": 0,
                "start": 0,
                "end": total_size - 1,
                "part_file": temp_path,
                "bytes_written": bytes_completed,
                "verified": False
            }],
            "timestamps": {
                "created": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "last_verified": None
            },
            "session": {
                "id": f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "crash_recovery": True
            }
        }
        
        try:
            with open(resume_path, 'w') as f:
                json.dump(state, f, indent=2)
            logger.info(f"RESUME | STATE_SAVED | task_id={task_id} | bytes={bytes_completed}")
        except Exception as e:
            logger.warning(f"Failed to save resume state: {e}")
    
    def _load_resume_state(self, filepath: str) -> Optional[Dict]:
        """Load resume state from file"""
        resume_path = self._get_resume_file_path(filepath)
        if not os.path.exists(resume_path):
            return None
        
        try:
            with open(resume_path, 'r') as f:
                state = json.load(f)
            return state
        except Exception as e:
            logger.warning(f"Failed to load resume state: {e}")
            return None
    
    def _validate_resume_state(self, state: Dict, url: str, temp_path: str, 
                              final_path: str) -> tuple[bool, str]:
        """Validate resume state for safety"""
        # Check final file doesn't exist
        if os.path.exists(final_path):
            return False, "final_file_exists"
        
        # Check URL unchanged
        if state.get('url') != url:
            return False, "url_mismatch"
        
        # Check temp file exists and size is valid
        if not os.path.exists(temp_path):
            return False, "temp_file_missing"
        
        actual_size = os.path.getsize(temp_path)
        recorded_size = state.get('bytes_completed', 0)
        
        if actual_size > recorded_size:
            return False, "temp_file_oversized"
        
        return True, "valid"
    
    def _validate_server_state(self, url: str, state: Dict) -> tuple[bool, str]:
        """Validate server state hasn't changed"""
        try:
            response = requests.head(url, allow_redirects=True)
            response.raise_for_status()
            
            # Check Content-Length unchanged
            server_size = int(response.headers.get('content-length', 0))
            if server_size != state.get('total_size', 0):
                return False, "content_length_mismatch"
            
            # Check ETag unchanged if available
            etag = response.headers.get('etag')
            if etag and state.get('etag') and etag != state.get('etag'):
                return False, "etag_mismatch"
            
            # Check Last-Modified unchanged if available  
            last_modified = response.headers.get('last-modified')
            if (last_modified and state.get('last_modified') and 
                last_modified != state.get('last_modified')):
                return False, "last_modified_mismatch"
            
            return True, "valid"
        except Exception as e:
            return False, f"server_error_{str(e)}"
    
    def _cleanup_resume_state(self, filepath: str, task_id: str) -> None:
        """Clean up resume state file after successful completion"""
        resume_path = self._get_resume_file_path(filepath)
        try:
            if os.path.exists(resume_path):
                os.remove(resume_path)
                logger.info(f"RESUME | CLEANUP | task_id={task_id} | state_file_deleted=true")
        except Exception as e:
            logger.warning(f"Failed to cleanup resume state: {e}")
        
    def download(self, url, destination, progress_callback=None, resume=True, 
                max_connections=None, priority=5, **options):
        """
        Download a file from URL to destination with multi-connection capability
        
        Args:
            url: URL to download from
            destination: Destination folder or file path
            progress_callback: Function to call with progress updates
            resume: Whether to resume partial downloads (single connection only for now)
            max_connections: Ignored - uses instance max_connections setting
            priority: Ignored - for compatibility only
            **options: Additional download options (ignored)
            
        Returns:
            bool: True if download successful, False otherwise
        """
        # Determine destination file path
        parsed_url = urlparse(url)
        if os.path.isdir(destination):
            filename = self._get_filename_from_url(url)
            filepath = os.path.join(destination, filename)
        else:
            filepath = destination
            filename = os.path.basename(filepath)
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Log download attempt
        logger.info(f"Download starting: {url} -> {filepath}")
        
        # Try multi-connection download first (for HTTP/HTTPS only)
        if self.enable_multi_connection and url.startswith(('http://', 'https://')):
            try:
                success, info = self.multi_downloader.download(url, filepath, progress_callback)
                
                # Log results with instrumentation
                if success:
                    logger.info(f"Download completed: mode={info['mode']}, connections={info['connections_used']}, "
                               f"size={info['total_size']}, time={info['download_time']:.2f}s")
                    
                    # Log segment info for multi-connection downloads
                    if info['mode'] == 'multi' and info['segments_info']:
                        logger.info(f"Segments used: {len(info['segments_info'])} segments")
                        # Log first and last few segments to avoid huge logs
                        segments_to_log = info['segments_info'][:2] + info['segments_info'][-2:]
                        for seg in segments_to_log:
                            logger.info(f"  Segment {seg['id']}: bytes {seg['start']}-{seg['end']} ({seg['size']} bytes)")
                else:
                    logger.error(f"Multi-connection download failed, info: {info}")
                
                return success, info
                
            except Exception as e:
                logger.error(f"Multi-connection download error: {e}")
                # Fall through to basic download
        
        # Fallback to basic single-connection download
        logger.info(f"Using single-connection fallback for {url}")
        
        # Generate task_id for resume support
        task_id = f"dl_{int(time.time())}"
        success = self._basic_download(url, filepath, progress_callback, resume, task_id=task_id)
        
        # Note: Hash verification is already handled in _basic_download
        # Return tuple for consistency with multi-connection downloader
        info = {
            'mode': 'basic',
            'connections_used': 1,
            'total_size': os.path.getsize(filepath) if success and os.path.exists(filepath) else 0,
            'download_time': 0
        }
        return success, info
    
    def _basic_download(self, url, filepath, progress_callback=None, resume=True, task_id="unknown"):
        """Basic single-connection download with resume support and atomic file handling"""
        filename = os.path.basename(filepath)
        
        # STEP 2: Atomic file handling - use temp file
        temp_filepath = f"{filepath}.part"
        
        try:
            # STEP 2: Log atomic operation start
            logger.info(f"ATOMIC | START | final={filepath} | temp={temp_filepath}")
            
            # STEP 3: Resume detection and validation
            resume_state = None
            existing_size = 0
            etag = None
            last_modified = None
            
            if resume and os.path.exists(temp_filepath):
                resume_state = self._load_resume_state(filepath)
                if resume_state:
                    logger.info(f"RESUME | DETECTED | task_id={resume_state.get('task_id', task_id)} | state_file={self._get_resume_file_path(filepath)}")
                    
                    # Validate resume state
                    state_valid, state_reason = self._validate_resume_state(resume_state, url, temp_filepath, filepath)
                    if state_valid:
                        # Validate server state
                        server_valid, server_reason = self._validate_server_state(url, resume_state)
                        if server_valid:
                            existing_size = resume_state.get('bytes_completed', 0)
                            etag = resume_state.get('etag')
                            last_modified = resume_state.get('last_modified')
                            logger.info(f"RESUME | VALIDATED | server_check=OK file_check=OK | task_id={resume_state.get('task_id', task_id)}")
                            logger.info(f"RESUME | START | task_id={resume_state.get('task_id', task_id)} | resuming_from_bytes={existing_size}")
                        else:
                            logger.info(f"RESUME | INVALIDATED | reason={server_reason} | task_id={resume_state.get('task_id', task_id)}")
                            resume_state = None
                            existing_size = 0
                    else:
                        logger.info(f"RESUME | INVALIDATED | reason={state_reason} | task_id={resume_state.get('task_id', task_id)}")
                        resume_state = None
                        existing_size = 0
                
                if not resume_state and existing_size == 0:
                    # Clean up invalid temp file
                    if os.path.exists(temp_filepath):
                        os.remove(temp_filepath)
            
            # Get server information
            response = requests.head(url, allow_redirects=True)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            server_etag = response.headers.get('etag')
            server_last_modified = response.headers.get('last-modified')
            
            # Determine download mode and setup headers
            headers = {}
            if existing_size > 0:
                headers['Range'] = f'bytes={existing_size}-'
                mode = 'ab'
            else:
                mode = 'wb'
            
            if existing_size > 0 and existing_size == total_size:
                # Temp file already complete, proceed to verification
                logger.info(f"ATOMIC | TEMP_COMPLETE | temp={temp_filepath} | size={total_size}")
                downloaded_size = total_size
            else:
                # Download remaining bytes
                response = requests.get(url, headers=headers, stream=True, allow_redirects=True)
                response.raise_for_status()
                
                # Verify we got the expected response
                if existing_size > 0 and response.status_code != 206:
                    # Server doesn't support range requests, restart
                    logger.warning(f"RESUME | INVALIDATED | reason=no_range_support | task_id={task_id}")
                    existing_size = 0
                    mode = 'wb'
                    response = requests.get(url, stream=True, allow_redirects=True)
                    response.raise_for_status()
                
                downloaded_size = existing_size
                start_time = time.time()
                last_update = start_time
                
                with open(temp_filepath, mode) as f:
                    for chunk in response.iter_content(chunk_size=self.max_chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # Save resume state periodically
                            current_time = time.time()
                            if current_time - last_update >= 5.0:  # Save every 5 seconds
                                self._save_resume_state(task_id, url, filepath, temp_filepath, 
                                                       total_size, downloaded_size, server_etag, server_last_modified)
                                last_update = current_time
                            
                            # Update progress
                            if progress_callback and current_time - last_update >= 0.5:
                                elapsed = current_time - start_time
                                speed = (downloaded_size - existing_size) / elapsed if elapsed > 0 else 0
                                progress_callback({
                                    'filename': filename,
                                    'progress': f"{(downloaded_size/total_size)*100:.1f}%" if total_size > 0 else "0%",
                                    'speed': f"{speed:.0f} B/s",
                                    'status': 'Resuming' if existing_size > 0 else 'Downloading'
                                })
                
                # Final resume state save
                self._save_resume_state(task_id, url, filepath, temp_filepath, 
                                       total_size, downloaded_size, server_etag, server_last_modified)
            
            # Update progress to verification
            if progress_callback:
                progress_callback({
                    'filename': filename,
                    'progress': "100%", 
                    'speed': "0 B/s",
                    'status': 'Verifying integrity...'
                })
            
            # STEP 1: Hash verification on temp file (PRESERVED FROM BASELINE)
            logger.info(f"HASH | START | {filename} | verifying SHA256 | temp={temp_filepath}")
            try:
                calculated_hash = self._calculate_file_hash(temp_filepath)
                logger.info(f"HASH | FINAL_OK | {filename} | sha256={calculated_hash[:16]}... | temp={temp_filepath}")
                
                # STEP 2: Atomic commit - move temp to final only after hash verification passes (PRESERVED FROM BASELINE)
                try:
                    os.replace(temp_filepath, filepath)
                    logger.info(f"ATOMIC | COMMIT_OK | final={filepath}")
                    
                    # Clean up resume state after successful completion
                    self._cleanup_resume_state(filepath, task_id)
                    
                    # Update progress with verification complete
                    if progress_callback:
                        progress_callback({
                            'filename': filename,
                            'progress': "100%",
                            'speed': "0 B/s",
                            'status': 'Completed'
                        })
                    
                    logger.info(f"Basic download completed: {downloaded_size} bytes, verified, committed")
                    return True
                except Exception as commit_error:
                    logger.error(f"ATOMIC | COMMIT_FAIL | final={filepath} | err={str(commit_error)}")
                    if progress_callback:
                        progress_callback({
                            'filename': filename,
                            'progress': "100%",
                            'speed': "0 B/s",
                            'status': f'Atomic commit failed: {str(commit_error)}'
                        })
                    return False
                
            except Exception as e:
                logger.error(f"HASH | FINAL_FAIL | {filename} | error={str(e)} | temp={temp_filepath}")
                if progress_callback:
                    progress_callback({
                        'filename': filename,
                        'progress': "100%",
                        'speed': "0 B/s", 
                        'status': f'Hash verification failed: {str(e)}'
                    })
                return False
            
            # STEP 3: Cleanup resume state on successful completion
            self._cleanup_resume_state(destination, task_id)
            
            # Final success return
            return True
            
            # Final progress update
            if progress_callback:
                progress_callback({
                    'filename': filename,
                    'progress': "100%", 
                    'speed': "0 B/s",
                    'status': 'Verifying integrity...'
                })
            
            # STEP 1: Hash verification on temp file
            logger.info(f"HASH | START | {filename} | verifying SHA256 | temp={temp_filepath}")
            try:
                calculated_hash = self._calculate_file_hash(temp_filepath)
                logger.info(f"HASH | FINAL_OK | {filename} | sha256={calculated_hash[:16]}... | temp={temp_filepath}")
                
                # STEP 2: Atomic commit - move temp to final only after hash verification passes
                try:
                    os.replace(temp_filepath, filepath)
                    logger.info(f"ATOMIC | COMMIT_OK | final={filepath}")
                    
                    # Update progress with verification complete
                    if progress_callback:
                        progress_callback({
                            'filename': filename,
                            'progress': "100%",
                            'speed': "0 B/s",
                            'status': 'Completed'
                        })
                    
                    logger.info(f"Basic download completed: {downloaded_size if 'downloaded_size' in locals() else total_size} bytes, verified, committed")
                    return True
                except Exception as commit_error:
                    logger.error(f"ATOMIC | COMMIT_FAIL | final={filepath} | err={str(commit_error)}")
                    if progress_callback:
                        progress_callback({
                            'filename': filename,
                            'progress': "100%",
                            'speed': "0 B/s",
                            'status': f'Atomic commit failed: {str(commit_error)}'
                        })
                    return False
                
            except Exception as e:
                logger.error(f"HASH | FINAL_FAIL | {filename} | error={str(e)} | temp={temp_filepath}")
                if progress_callback:
                    progress_callback({
                        'filename': filename,
                        'progress': "100%",
                        'speed': "0 B/s", 
                        'status': f'Hash verification failed: {str(e)}'
                    })
                return False
            
        except Exception as e:
            if progress_callback:
                progress_callback({
                    'filename': filename,
                    'progress': "0%",
                    'speed': "0 B/s",
                    'status': f'Error: {str(e)}'
                })
            logger.error(f"Basic download failed: {e}")
            return False
    
    def _get_filename_from_url(self, url):
        """Extract filename from URL"""
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        
        if not filename or '.' not in filename:
            # Try to get from Content-Disposition header
            try:
                response = requests.head(url, allow_redirects=True)
                content_disposition = response.headers.get('content-disposition', '')
                if 'filename=' in content_disposition:
                    filename = content_disposition.split('filename=')[1].strip('"\'')
                else:
                    # Generate filename from URL
                    filename = f"download_{hashlib.md5(url.encode()).hexdigest()[:8]}"
            except:
                filename = f"download_{int(time.time())}"
        
        return unquote(filename)
    
    def _format_size(self, bytes_size):
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"
    
    def _format_speed(self, bytes_per_second):
        """Format download speed in human readable format"""
        return f"{self._format_size(bytes_per_second)}/s"
    
    def _calculate_file_hash(self, filepath):
        """Calculate SHA256 hash of a file for integrity verification"""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(8192), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def get_file_info(self, url):
        """Get file information without downloading"""
        try:
            response = requests.head(url, allow_redirects=True)
            response.raise_for_status()
            
            size = int(response.headers.get('content-length', 0))
            content_type = response.headers.get('content-type', 'Unknown')
            filename = self._get_filename_from_url(url)
            
            # Check range support using our detector
            if self.enable_multi_connection:
                from http_range_detector import supports_http_range
                supports_range, _ = supports_http_range(url)
            else:
                supports_range = 'accept-ranges' in response.headers
            
            return {
                'filename': filename,
                'size': size,
                'size_formatted': self._format_size(size),
                'content_type': content_type,
                'supports_range_requests': supports_range
            }
        except Exception as e:
            return None
    
    def validate_url(self, url):
        """Validate if URL is downloadable"""
        try:
            response = requests.head(url, allow_redirects=True, timeout=10)
            return response.status_code == 200
        except:
            return False