"""
Local Range Server for V2.1 Testing
Provides a deterministic HTTP server with Range request support
"""

import os
import sys
import socket
import threading
import time
import hashlib
import tempfile
import shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote


class RangeHTTPRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler with /range/ and /norange/ endpoints"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        """Override to suppress request logs"""
        pass
    
    def parse_request_path(self, requested_path):
        """Parse request path to determine mode and filename"""
        # Remove leading slash and decode URL
        path = unquote(requested_path.lstrip('/'))
        
        if path.startswith('range/'):
            return 'range', path[6:]  # Remove 'range/' prefix
        elif path.startswith('norange/'):
            return 'norange', path[8:]  # Remove 'norange/' prefix
        else:
            # Default to range mode for compatibility
            return 'range', path
    
    def get_file_path(self, filename):
        """Get the actual file path for a filename"""
        return os.path.join(self.server.serve_dir, filename)
    
    def do_HEAD(self):
        """Handle HEAD requests"""
        mode, filename = self.parse_request_path(self.path)
        file_path = self.get_file_path(filename)
        
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            self.send_error(404, "File not found")
            return
            
        file_size = os.path.getsize(file_path)
        file_mtime = int(os.path.getmtime(file_path))
        
        self.send_response(200)
        self.send_header('Content-Length', str(file_size))
        
        # Range support depends on endpoint
        if mode == 'range':
            self.send_header('Accept-Ranges', 'bytes')
        # norange mode: don't send Accept-Ranges header
            
        self.send_header('ETag', f'"{file_size}-{file_mtime}"')
        self.send_header('Last-Modified', 'Wed, 21 Oct 2015 07:28:00 GMT')
        self.send_header('Content-Type', 'application/octet-stream')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests with conditional Range support"""
        mode, filename = self.parse_request_path(self.path)
        file_path = self.get_file_path(filename)
        
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            self.send_error(404, "File not found")
            return
            
        file_size = os.path.getsize(file_path)
        file_mtime = int(os.path.getmtime(file_path))
        
        # Check if this is a range request and if endpoint supports ranges
        range_header = self.headers.get('Range')
        
        if range_header and mode == 'range':
            # Parse Range header for /range/ endpoint
            try:
                ranges = self._parse_range_header(range_header, file_size)
                if ranges:
                    start, end = ranges[0]  # Handle single range
                    
                    # Send partial content response
                    self.send_response(206, 'Partial Content')
                    self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                    self.send_header('Content-Length', str(end - start + 1))
                    self.send_header('Accept-Ranges', 'bytes')
                    self.send_header('ETag', f'"{file_size}-{file_mtime}"')
                    self.send_header('Content-Type', 'application/octet-stream')
                    self.end_headers()
                    
                    # Send partial file content
                    self._send_file_range(file_path, start, end)
                    return
                    
            except Exception:
                # Invalid range, fall through to full file
                pass
        
        # Send full file (either /norange/ or fallback)
        self.send_response(200)
        self.send_header('Content-Length', str(file_size))
        
        if mode == 'range':
            self.send_header('Accept-Ranges', 'bytes')
        # norange mode: no Accept-Ranges header
            
        self.send_header('ETag', f'"{file_size}-{file_mtime}"')
        self.send_header('Content-Type', 'application/octet-stream')
        self.end_headers()
        
        # Send full file content
        self._send_file_range(file_path, 0, file_size - 1)
    
    def _parse_range_header(self, range_header, file_size):
        """Parse Range header and return list of (start, end) tuples"""
        ranges = []
        
        if not range_header.startswith('bytes='):
            return ranges
            
        range_specs = range_header[6:].split(',')
        
        for range_spec in range_specs:
            range_spec = range_spec.strip()
            
            if '-' not in range_spec:
                continue
                
            start_str, end_str = range_spec.split('-', 1)
            
            try:
                if start_str:
                    start = int(start_str)
                    if end_str:
                        end = int(end_str)
                    else:
                        end = file_size - 1
                else:
                    # Suffix range
                    if end_str:
                        suffix_length = int(end_str)
                        start = max(0, file_size - suffix_length)
                        end = file_size - 1
                    else:
                        continue
                
                # Validate range
                start = max(0, start)
                end = min(end, file_size - 1)
                
                if start <= end:
                    ranges.append((start, end))
                    
            except ValueError:
                continue
        
        return ranges
    
    def _send_file_range(self, file_path, start, end):
        """Send a range of bytes from a file with optional delay for testing"""
        try:
            with open(file_path, 'rb') as f:
                f.seek(start)
                remaining = end - start + 1
                chunk_size = 8192
                
                while remaining > 0:
                    chunk_size = min(chunk_size, remaining)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    self.wfile.write(data)
                    remaining -= len(data)
                    
                    # Add delay for testing if enabled
                    if hasattr(self.server, 'slow_mode') and self.server.slow_mode:
                        time.sleep(0.01)  # 10ms delay per chunk for slow testing
                    
        except Exception as e:
            # Connection might be broken, ignore
            pass


class LocalRangeServer:
    """Local HTTP server with stable lifecycle for testing"""
    
    def __init__(self, port=0):
        self.port = port
        self.server = None
        self.thread = None
        self.serve_dir = None
        self.actual_port = None
        self.base_url = None
        
    def start(self):
        """Start server and return (base_url, base_dir)"""
        if self.server is not None:
            raise RuntimeError("Server already started")
            
        # Create serve directory
        self.serve_dir = tempfile.mkdtemp(prefix="range_server_")
        
        # Ensure directory exists and is writable
        if not os.path.exists(self.serve_dir):
            os.makedirs(self.serve_dir, exist_ok=True)
        
        # Create and start server
        self.server = HTTPServer(('localhost', self.port), RangeHTTPRequestHandler)
        self.server.serve_dir = self.serve_dir
        self.server.slow_mode = False  # For testing interruption
        
        self.actual_port = self.server.server_address[1]
        self.base_url = f"http://localhost:{self.actual_port}"
        
        # Start in background thread
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        
        # Give server time to start
        time.sleep(0.1)
        
        return self.base_url, self.serve_dir
    
    def stop(self):
        """Stop server and cleanup"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
            
        # Clean up serve directory
        if self.serve_dir and os.path.exists(self.serve_dir):
            shutil.rmtree(self.serve_dir, ignore_errors=True)
            
        self.server = None
        self.thread = None
        self.serve_dir = None
        self.actual_port = None
        self.base_url = None

    def set_slow_mode(self, enabled):
        """Enable/disable slow mode for testing interruption"""
        if self.server:
            self.server.slow_mode = enabled

    def create_test_file(self, filename, size_bytes):
        """Create a deterministic test file in the serve directory"""
        if not self.serve_dir:
            raise RuntimeError("Server not started - call start() first")
            
        file_path = os.path.join(self.serve_dir, filename)
        
        # Create predictable content for hash verification
        pattern = b'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789' * 29  # ~1KB pattern
        pattern = pattern[:1024]  # Exactly 1KB
        
        written = 0
        with open(file_path, 'wb') as f:
            while written < size_bytes:
                remaining = size_bytes - written
                chunk_size = min(len(pattern), remaining)
                f.write(pattern[:chunk_size])
                written += chunk_size
        
        return file_path
    
    def get_file_hash(self, filename):
        """Calculate SHA256 hash of a served file"""
        if not self.serve_dir:
            return None
            
        file_path = os.path.join(self.serve_dir, filename)
        if not os.path.exists(file_path):
            return None
            
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()


def get_free_port():
    """Find a free port"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def main():
    """Run the local range server"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Local Range Server for Testing')
    parser.add_argument('--size-mb', type=int, default=50, help='Test file size in MB')
    parser.add_argument('--port', type=int, default=0, help='Port (0 for auto)')
    parser.add_argument('--no-range', action='store_true', help='Disable Range support')
    args = parser.parse_args()
    
    # Start server
    server = LocalRangeServer(port=args.port)
    server.setup_serve_directory()
    
    # Create test file
    test_filename = "test.dat"
    size_bytes = args.size_mb * 1024 * 1024
    server.create_test_file(test_filename, size_bytes)
    
    if args.no_range:
        server.set_no_range_mode(True)
        print("Range support: DISABLED")
    else:
        print("Range support: ENABLED")
    
    print(f"Serving directory: {server.serve_dir}")
    print(f"Test file created: {test_filename} ({size_bytes:,} bytes)")
    
    # Start server using proper lifecycle
    server.start()
    port = server.actual_port
    
    print(f"Server started at: http://localhost:{port}")
    print(f"Test URL: http://localhost:{port}/{test_filename}")
    print("Press Ctrl+C to stop...")
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.stop()


if __name__ == "__main__":
    main()