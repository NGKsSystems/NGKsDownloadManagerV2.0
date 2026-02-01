"""
Protocol Handlers for Advanced Download Manager
Supports HTTP/HTTPS, FTP, SFTP and other protocols
"""

import os
import ftplib
import time
import hashlib
from urllib.parse import urlparse, unquote
from typing import Dict, Optional, Callable, Any, List
import logging

try:
    import paramiko
    SFTP_AVAILABLE = True
except ImportError:
    SFTP_AVAILABLE = False

class BaseProtocolHandler:
    """Base class for protocol handlers"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def can_handle(self, url: str) -> bool:
        """Check if this handler can handle the URL"""
        raise NotImplementedError
    
    def get_file_info(self, url: str) -> Optional[Dict]:
        """Get file information from URL"""
        raise NotImplementedError
    
    def download(self, url: str, destination: str, progress_callback: Optional[Callable] = None,
                **options) -> bool:
        """Download file from URL"""
        raise NotImplementedError

class HTTPProtocolHandler(BaseProtocolHandler):
    """Handler for HTTP/HTTPS downloads"""
    
    def __init__(self, session=None):
        super().__init__()
        self.session = session
    
    def can_handle(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme.lower() in ['http', 'https']
    
    def get_file_info(self, url: str) -> Optional[Dict]:
        """Get file information via HTTP HEAD request"""
        try:
            if not self.session:
                import requests
                response = requests.head(url, allow_redirects=True, timeout=10)
            else:
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
                'supports_resume': 'accept-ranges' in response.headers.get('accept-ranges', '').lower(),
                'protocol': 'HTTP/HTTPS'
            }
        except Exception as e:
            self.logger.error(f"Failed to get HTTP file info: {e}")
            return None
    
    def download(self, url: str, destination: str, progress_callback: Optional[Callable] = None,
                **options) -> bool:
        """Download via HTTP (delegated to AdvancedDownloadManager)"""
        # This is handled by the main download manager
        # This method is for consistency with the interface
        return True
    
    def _get_filename_from_url(self, url: str, response=None) -> str:
        """Extract filename from URL or response headers"""
        if response and 'content-disposition' in response.headers:
            content_disposition = response.headers['content-disposition']
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[1].strip('"\'')
                return unquote(filename)
        
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        
        if not filename or '.' not in filename:
            filename = f"download_{hashlib.md5(url.encode()).hexdigest()[:8]}"
        
        return unquote(filename)
    
    def _format_size(self, bytes_size: int) -> str:
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"

class FTPProtocolHandler(BaseProtocolHandler):
    """Handler for FTP downloads"""
    
    def can_handle(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme.lower() == 'ftp'
    
    def get_file_info(self, url: str) -> Optional[Dict]:
        """Get file information via FTP"""
        try:
            parsed = urlparse(url)
            
            # Connect to FTP server
            ftp = ftplib.FTP()
            ftp.connect(parsed.hostname, parsed.port or 21)
            
            # Login
            username = parsed.username or 'anonymous'
            password = parsed.password or 'anonymous@'
            ftp.login(username, password)
            
            # Get file info
            filepath = parsed.path
            filename = os.path.basename(filepath)
            
            try:
                # Try to get file size
                size = ftp.size(filepath)
                if size is None:
                    size = 0
            except:
                size = 0
            
            ftp.quit()
            
            return {
                'filename': filename,
                'size': size,
                'size_formatted': self._format_size(size),
                'content_type': 'application/octet-stream',
                'supports_resume': True,  # FTP generally supports resume
                'protocol': 'FTP'
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get FTP file info: {e}")
            return None
    
    def download(self, url: str, destination: str, progress_callback: Optional[Callable] = None,
                **options) -> bool:
        """Download file via FTP"""
        try:
            parsed = urlparse(url)
            
            # Determine file path
            if os.path.isdir(destination):
                filename = os.path.basename(parsed.path)
                filepath = os.path.join(destination, filename)
            else:
                filepath = destination
                filename = os.path.basename(filepath)
            
            # Create directory if needed
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Check for resume
            existing_size = 0
            if os.path.exists(filepath) and options.get('resume', True):
                existing_size = os.path.getsize(filepath)
            
            # Connect to FTP server
            ftp = ftplib.FTP()
            ftp.connect(parsed.hostname, parsed.port or 21)
            
            # Login
            username = parsed.username or 'anonymous'
            password = parsed.password or 'anonymous@'
            ftp.login(username, password)
            
            # Set binary mode
            ftp.voidcmd('TYPE I')
            
            # Get file size
            try:
                total_size = ftp.size(parsed.path)
                if total_size is None:
                    total_size = 0
            except:
                total_size = 0
            
            # Setup resume if needed
            if existing_size > 0:
                ftp.voidcmd(f'REST {existing_size}')
                mode = 'ab'
            else:
                mode = 'wb'
            
            downloaded = existing_size
            start_time = time.time()
            last_update = start_time
            
            def write_callback(data):
                nonlocal downloaded, last_update
                f.write(data)
                downloaded += len(data)
                
                # Update progress
                current_time = time.time()
                if current_time - last_update >= 0.5:  # Update every 0.5 seconds
                    elapsed_time = current_time - start_time
                    if elapsed_time > 0:
                        speed = (downloaded - existing_size) / elapsed_time
                        speed_str = self._format_speed(speed)
                    else:
                        speed_str = "0 B/s"
                    
                    if progress_callback:
                        progress_callback({
                            'filename': filename,
                            'progress': f"{(downloaded/total_size)*100:.1f}%" if total_size > 0 else f"{self._format_size(downloaded)}",
                            'speed': speed_str,
                            'status': 'Downloading',
                            'downloaded': downloaded
                        })
                    
                    last_update = current_time
            
            # Download file
            with open(filepath, mode) as f:
                ftp.retrbinary(f'RETR {parsed.path}', write_callback)
            
            ftp.quit()
            
            # Final progress update
            if progress_callback:
                progress_callback({
                    'filename': filename,
                    'progress': "100%",
                    'speed': "0 B/s",
                    'status': 'Completed',
                    'downloaded': downloaded
                })
            
            return True
            
        except Exception as e:
            self.logger.error(f"FTP download failed: {e}")
            if progress_callback:
                progress_callback({
                    'filename': filename if 'filename' in locals() else 'Unknown',
                    'progress': "0%",
                    'speed': "0 B/s",
                    'status': f'Error: {str(e)}'
                })
            return False
    
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

class SFTPProtocolHandler(BaseProtocolHandler):
    """Handler for SFTP downloads (requires paramiko)"""
    
    def __init__(self):
        super().__init__()
        if not SFTP_AVAILABLE:
            self.logger.warning("paramiko not available, SFTP support disabled")
    
    def can_handle(self, url: str) -> bool:
        if not SFTP_AVAILABLE:
            return False
        parsed = urlparse(url)
        return parsed.scheme.lower() == 'sftp'
    
    def get_file_info(self, url: str) -> Optional[Dict]:
        """Get file information via SFTP"""
        if not SFTP_AVAILABLE:
            return None
        
        try:
            parsed = urlparse(url)
            
            # Create SSH client
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect
            ssh.connect(
                parsed.hostname,
                port=parsed.port or 22,
                username=parsed.username,
                password=parsed.password
            )
            
            # Create SFTP client
            sftp = ssh.open_sftp()
            
            # Get file stats
            filepath = parsed.path
            filename = os.path.basename(filepath)
            
            try:
                stats = sftp.stat(filepath)
                size = stats.st_size
            except:
                size = 0
            
            sftp.close()
            ssh.close()
            
            return {
                'filename': filename,
                'size': size,
                'size_formatted': self._format_size(size),
                'content_type': 'application/octet-stream',
                'supports_resume': False,  # SFTP resume is more complex
                'protocol': 'SFTP'
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get SFTP file info: {e}")
            return None
    
    def download(self, url: str, destination: str, progress_callback: Optional[Callable] = None,
                **options) -> bool:
        """Download file via SFTP"""
        if not SFTP_AVAILABLE:
            if progress_callback:
                progress_callback({
                    'filename': 'Unknown',
                    'progress': "0%",
                    'speed': "0 B/s",
                    'status': 'Error: paramiko not installed'
                })
            return False
        
        try:
            parsed = urlparse(url)
            
            # Determine file path
            if os.path.isdir(destination):
                filename = os.path.basename(parsed.path)
                filepath = os.path.join(destination, filename)
            else:
                filepath = destination
                filename = os.path.basename(filepath)
            
            # Create directory if needed
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Create SSH client
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect
            ssh.connect(
                parsed.hostname,
                port=parsed.port or 22,
                username=parsed.username,
                password=parsed.password
            )
            
            # Create SFTP client
            sftp = ssh.open_sftp()
            
            # Get file size
            try:
                stats = sftp.stat(parsed.path)
                total_size = stats.st_size
            except:
                total_size = 0
            
            # Download with progress
            downloaded = 0
            start_time = time.time()
            last_update = start_time
            
            def progress_tracker(transferred, total):
                nonlocal downloaded, last_update
                downloaded = transferred
                
                current_time = time.time()
                if current_time - last_update >= 0.5:
                    elapsed_time = current_time - start_time
                    if elapsed_time > 0:
                        speed = downloaded / elapsed_time
                        speed_str = self._format_speed(speed)
                    else:
                        speed_str = "0 B/s"
                    
                    if progress_callback:
                        progress_callback({
                            'filename': filename,
                            'progress': f"{(downloaded/total)*100:.1f}%" if total > 0 else f"{self._format_size(downloaded)}",
                            'speed': speed_str,
                            'status': 'Downloading',
                            'downloaded': downloaded
                        })
                    
                    last_update = current_time
            
            # Download file
            sftp.get(parsed.path, filepath, callback=progress_tracker)
            
            sftp.close()
            ssh.close()
            
            # Final progress update
            if progress_callback:
                progress_callback({
                    'filename': filename,
                    'progress': "100%",
                    'speed': "0 B/s",
                    'status': 'Completed',
                    'downloaded': downloaded
                })
            
            return True
            
        except Exception as e:
            self.logger.error(f"SFTP download failed: {e}")
            if progress_callback:
                progress_callback({
                    'filename': filename if 'filename' in locals() else 'Unknown',
                    'progress': "0%",
                    'speed': "0 B/s",
                    'status': f'Error: {str(e)}'
                })
            return False
    
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

class ProtocolManager:
    """Manages different protocol handlers"""
    
    def __init__(self):
        self.handlers = []
        self.logger = logging.getLogger(__name__)
        
        # Register default handlers
        self.register_handler(HTTPProtocolHandler())
        self.register_handler(FTPProtocolHandler())
        self.register_handler(SFTPProtocolHandler())
    
    def register_handler(self, handler: BaseProtocolHandler):
        """Register a new protocol handler"""
        self.handlers.append(handler)
        self.logger.info(f"Registered protocol handler: {handler.__class__.__name__}")
    
    def get_handler(self, url: str) -> Optional[BaseProtocolHandler]:
        """Get appropriate handler for URL"""
        for handler in self.handlers:
            if handler.can_handle(url):
                return handler
        return None
    
    def get_supported_protocols(self) -> List[str]:
        """Get list of supported protocols"""
        protocols = []
        test_urls = {
            'http': 'http://example.com/file.txt',
            'https': 'https://example.com/file.txt',
            'ftp': 'ftp://example.com/file.txt',
            'sftp': 'sftp://example.com/file.txt'
        }
        
        for protocol, test_url in test_urls.items():
            if self.get_handler(test_url):
                protocols.append(protocol.upper())
        
        return protocols
    
    def get_file_info(self, url: str) -> Optional[Dict]:
        """Get file information using appropriate handler"""
        handler = self.get_handler(url)
        if handler:
            return handler.get_file_info(url)
        return None
    
    def download(self, url: str, destination: str, progress_callback: Optional[Callable] = None,
                **options) -> bool:
        """Download using appropriate handler"""
        handler = self.get_handler(url)
        if handler:
            return handler.download(url, destination, progress_callback, **options)
        return False

# Example usage
if __name__ == "__main__":
    # Test protocol manager
    pm = ProtocolManager()
    
    print("Supported protocols:", pm.get_supported_protocols())
    
    # Test HTTP
    http_info = pm.get_file_info("https://httpbin.org/bytes/1024")
    print("HTTP file info:", http_info)
    
    # Test FTP (if available)
    try:
        ftp_info = pm.get_file_info("ftp://test.rebex.net/readme.txt")
        print("FTP file info:", ftp_info)
    except Exception as e:
        print(f"FTP test failed: {e}")