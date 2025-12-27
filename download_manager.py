"""
Core Download Manager
Handles direct HTTP/HTTPS downloads with resume capability and progress tracking
"""

import os
import requests
import threading
from urllib.parse import urlparse, unquote
import time
import hashlib
from pathlib import Path

class DownloadManager:
    def __init__(self, max_chunk_size=8192, max_retries=3):
        self.max_chunk_size = max_chunk_size
        self.max_retries = max_retries
        self.active_downloads = {}
        
    def download(self, url, destination, progress_callback=None, resume=True):
        """
        Download a file from URL to destination with resume capability
        
        Args:
            url: URL to download from
            destination: Destination folder or file path
            progress_callback: Function to call with progress updates
            resume: Whether to resume partial downloads
            
        Returns:
            bool: True if download successful, False otherwise
        """
        try:
            # Parse URL and determine filename
            parsed_url = urlparse(url)
            if os.path.isdir(destination):
                filename = self._get_filename_from_url(url)
                filepath = os.path.join(destination, filename)
            else:
                filepath = destination
                filename = os.path.basename(filepath)
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Check if file already exists and get size
            existing_size = 0
            if os.path.exists(filepath) and resume:
                existing_size = os.path.getsize(filepath)
            
            # Get file info from server
            headers = {}
            if existing_size > 0:
                headers['Range'] = f'bytes={existing_size}-'
            
            response = requests.head(url, headers=headers, allow_redirects=True)
            total_size = int(response.headers.get('content-length', 0))
            
            if existing_size > 0 and response.status_code == 206:
                # Resume download
                total_size += existing_size
                mode = 'ab'
                if progress_callback:
                    progress_callback({
                        'filename': filename,
                        'progress': f"{(existing_size/total_size)*100:.1f}%" if total_size > 0 else "0%",
                        'speed': "0 B/s",
                        'status': 'Resuming'
                    })
            elif existing_size > 0 and existing_size == total_size:
                # File already complete
                if progress_callback:
                    progress_callback({
                        'filename': filename,
                        'progress': "100%",
                        'speed': "0 B/s",
                        'status': 'Already Complete'
                    })
                return True
            else:
                # Start fresh download
                existing_size = 0
                mode = 'wb'
                if response.status_code == 200:
                    total_size = int(response.headers.get('content-length', 0))
            
            # Start download
            headers = {}
            if existing_size > 0:
                headers['Range'] = f'bytes={existing_size}-'
            
            response = requests.get(url, headers=headers, stream=True, allow_redirects=True)
            response.raise_for_status()
            
            downloaded_size = existing_size
            start_time = time.time()
            last_update = start_time
            
            with open(filepath, mode) as f:
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
                                    'status': 'Downloading'
                                })
                            
                            last_update = current_time
            
            # Final progress update
            if progress_callback:
                progress_callback({
                    'filename': filename,
                    'progress': "100%",
                    'speed': "0 B/s",
                    'status': 'Completed'
                })
            
            return True
            
        except Exception as e:
            if progress_callback:
                progress_callback({
                    'filename': filename if 'filename' in locals() else 'Unknown',
                    'progress': "0%",
                    'speed': "0 B/s",
                    'status': f'Error: {str(e)}'
                })
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
    
    def get_file_info(self, url):
        """Get file information without downloading"""
        try:
            response = requests.head(url, allow_redirects=True)
            response.raise_for_status()
            
            size = int(response.headers.get('content-length', 0))
            content_type = response.headers.get('content-type', 'Unknown')
            filename = self._get_filename_from_url(url)
            
            return {
                'filename': filename,
                'size': size,
                'size_formatted': self._format_size(size),
                'content_type': content_type,
                'supports_resume': 'accept-ranges' in response.headers
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