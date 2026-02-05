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
        success = self._basic_download(url, filepath, progress_callback, resume)
        
        # Note: Hash verification is already handled in _basic_download
        # Return tuple for consistency with multi-connection downloader
        info = {
            'mode': 'basic',
            'connections_used': 1,
            'total_size': os.path.getsize(filepath) if success and os.path.exists(filepath) else 0,
            'download_time': 0
        }
        return success, info
    
    def _basic_download(self, url, filepath, progress_callback=None, resume=True):
        """Basic single-connection download with resume support and atomic file handling"""
        filename = os.path.basename(filepath)
        
        # STEP 2: Atomic file handling - use temp file
        temp_filepath = f"{filepath}.part"
        
        try:
            # STEP 2: Log atomic operation start
            logger.info(f"ATOMIC | START | final={filepath} | temp={temp_filepath}")
            
            # Check if temp file already exists and get size for resume
            existing_size = 0
            if os.path.exists(temp_filepath) and resume:
                existing_size = os.path.getsize(temp_filepath)
                logger.info(f"ATOMIC | RESUME | temp={temp_filepath} | existing_size={existing_size}")
            
            # Get file info from server
            headers = {}
            if existing_size > 0:
                headers['Range'] = f'bytes={existing_size}-'
                
                # Attempt GET with Range to check for 206; otherwise restart
                response = requests.get(url, headers=headers, stream=True, allow_redirects=True)
                
                if response.status_code == 206:
                    # Resume download  
                    total_size = existing_size + int(response.headers.get('content-length', 0))
                    mode = 'ab'
                    if progress_callback:
                        progress_callback({
                            'filename': filename,
                            'progress': f"{(existing_size/total_size)*100:.1f}%" if total_size > 0 else "0%",
                            'speed': "0 B/s",
                            'status': 'Resuming'
                        })
                else:
                    # Range not supported or failed, restart cleanly
                    response.close()
                    existing_size = 0
                    mode = 'wb'
                    response = requests.head(url, allow_redirects=True)
                    total_size = int(response.headers.get('content-length', 0))
            else:
                response = requests.head(url, allow_redirects=True)
                total_size = int(response.headers.get('content-length', 0))
                mode = 'wb'
                
            if existing_size > 0 and existing_size == total_size:
                # Temp file already complete, need to verify hash and commit
                logger.info(f"ATOMIC | TEMP_COMPLETE | temp={temp_filepath} | size={total_size}")
                # Proceed to hash verification and atomic commit below
            else:
                # Continue with download to temp file
                pass
            
            # Start download to temp file only if not already complete
            if not (existing_size > 0 and existing_size == total_size):
                headers = {}
                if existing_size > 0:
                    headers['Range'] = f'bytes={existing_size}-'
                
                response = requests.get(url, headers=headers, stream=True, allow_redirects=True)
                response.raise_for_status()
                
                downloaded_size = existing_size
                start_time = time.time()
                last_update = start_time
                
                with open(temp_filepath, mode) as f:
                    for chunk in response.iter_content(chunk_size=self.max_chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # Update progress
                            current_time = time.time()
                            if current_time - last_update >= 0.5:  # Update every 0.5 seconds
                                elapsed_time = current_time - start_time
                                if elapsed_time > 0:
                                    speed = (downloaded_size - existing_size) / elapsed_time
                                    speed_str = self._format_speed(speed)
                                else:
                                    speed_str = "0 B/s"
                                
                                if progress_callback:
                                    progress_callback({
                                        'filename': filename,
                                        'progress': f"{(downloaded_size/total_size)*100:.1f}%" if total_size > 0 else f"{self._format_size(downloaded_size)}",
                                        'speed': speed_str,
                                        'status': 'Downloading (single connection)'
                                    })
                                
                                last_update = current_time
            
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