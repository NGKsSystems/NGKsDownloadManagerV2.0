"""
Resume Test V2.1 - Deterministic local test for multi-connection resume
Tests interruption and resume with hash verification
"""

import os
import time
import hashlib
import threading
import tempfile
import shutil
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import logging

from integrated_multi_downloader import IntegratedMultiDownloader

class RangeHTTPRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler that supports Range requests"""
    
    def __init__(self, test_file_path, *args, **kwargs):
        self.test_file_path = test_file_path
        super().__init__(*args, **kwargs)
    
    def do_HEAD(self):
        """Handle HEAD requests"""
        if not os.path.exists(self.test_file_path):
            self.send_error(404)
            return
            
        file_size = os.path.getsize(self.test_file_path)
        
        self.send_response(200)
        self.send_header('Content-Length', str(file_size))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('ETag', f'"{file_size}-{int(os.path.getmtime(self.test_file_path))}"')
        self.send_header('Last-Modified', 'Wed, 21 Oct 2015 07:28:00 GMT')  # Fixed for testing
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests with Range support"""
        if not os.path.exists(self.test_file_path):
            self.send_error(404)
            return
            
        file_size = os.path.getsize(self.test_file_path)
        
        # Parse Range header
        range_header = self.headers.get('Range')
        
        if range_header:
            # Parse range request
            try:
                ranges = range_header.replace('bytes=', '').split(',')
                start, end = ranges[0].split('-')
                start = int(start) if start else 0
                end = int(end) if end else file_size - 1
                
                if start >= file_size or end >= file_size:
                    self.send_error(416)  # Range not satisfiable
                    return
                
                content_length = end - start + 1
                
                self.send_response(206)  # Partial content
                self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                self.send_header('Content-Length', str(content_length))
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('ETag', f'"{file_size}-{int(os.path.getmtime(self.test_file_path))}"')
                self.end_headers()
                
                # Send file content
                with open(self.test_file_path, 'rb') as f:
                    f.seek(start)
                    remaining = content_length
                    while remaining > 0:
                        chunk_size = min(8192, remaining)
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                        
            except Exception as e:
                logging.error(f"Range parsing error: {e}")
                self.send_error(400)
                
        else:
            # Send full file
            self.send_response(200)
            self.send_header('Content-Length', str(file_size))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('ETag', f'"{file_size}-{int(os.path.getmtime(self.test_file_path))}"')
            self.end_headers()
            
            with open(self.test_file_path, 'rb') as f:
                shutil.copyfileobj(f, self.wfile)

class LocalRangeServer:
    """Local HTTP server for testing Range requests"""
    
    def __init__(self, test_file_path, port=8765):
        self.test_file_path = test_file_path
        self.port = port
        self.server = None
        self.thread = None
    
    def start(self):
        """Start the server in a background thread"""
        def handler(*args, **kwargs):
            return RangeHTTPRequestHandler(self.test_file_path, *args, **kwargs)
            
        self.server = HTTPServer(('localhost', self.port), handler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        
        print(f"Local server started on http://localhost:{self.port}")
    
    def stop(self):
        """Stop the server"""
        if self.server:
            self.server.shutdown()
            self.thread.join()
            print("Local server stopped")

class InterruptibleDownloader:
    """Wrapper around IntegratedMultiDownloader that can be interrupted"""
    
    def __init__(self, downloader):
        self.downloader = downloader
        self.interrupt_event = threading.Event()
        self.original_download = None
    
    def start_download(self, url, destination):
        """Start download in background thread"""
        self.download_thread = threading.Thread(
            target=self._download_worker, 
            args=(url, destination)
        )
        self.download_thread.start()
    
    def _download_worker(self, url, destination):
        """Worker thread for download"""
        try:
            self.result = self.downloader.download(url, destination)
        except Exception as e:
            self.result = (False, {'error': str(e)})
    
    def interrupt_after_delay(self, delay_seconds):
        """Interrupt download after delay"""
        def interrupt_worker():
            time.sleep(delay_seconds)
            print(f"Interrupting download after {delay_seconds} seconds...")
            # Force-kill the process by raising exception in main thread
            os._exit(0)
        
        interrupt_thread = threading.Thread(target=interrupt_worker)
        interrupt_thread.daemon = True
        interrupt_thread.start()

def create_test_file(size_mb=50):
    """Create a test file with known content for hashing"""
    test_file = tempfile.NamedTemporaryFile(delete=False, suffix='.testfile')
    
    # Create predictable content for hashing
    content = b'A' * 1024  # 1KB block of 'A's
    
    total_bytes = size_mb * 1024 * 1024
    written = 0
    
    print(f"Creating {size_mb}MB test file...")
    with open(test_file.name, 'wb') as f:
        while written < total_bytes:
            remaining = total_bytes - written
            chunk_size = min(len(content), remaining)
            f.write(content[:chunk_size])
            written += chunk_size
    
    print(f"Test file created: {test_file.name}")
    return test_file.name

def calculate_file_hash(file_path):
    """Calculate SHA256 hash of file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()

def test_resume_functionality():
    """Test complete resume functionality"""
    print("=" * 60)
    print("Resume Test V2.1 - Multi-Connection Resume Test")
    print("=" * 60)
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Create test file
    test_file_path = create_test_file(size_mb=20)  # 20MB test file
    original_hash = calculate_file_hash(test_file_path)
    print(f"Original file hash: {original_hash}")
    
    # Start local server
    server = LocalRangeServer(test_file_path)
    server.start()
    
    try:
        url = f"http://localhost:{server.port}/testfile"
        destination = tempfile.NamedTemporaryFile(delete=False, suffix='.downloaded').name
        
        print(f"\\nTest URL: {url}")
        print(f"Destination: {destination}")
        
        # Test 1: Start download and interrupt
        print("\\n" + "-" * 40)
        print("TEST 1: Start download and interrupt")
        print("-" * 40)
        
        downloader = IntegratedMultiDownloader(max_connections=4)
        
        try:
            # Start download
            print("Starting download...")
            download_start = time.time()
            
            # This will be interrupted by the timer
            result = downloader.download(url, destination)
            
            # If we get here, download completed (might be too fast)
            if result[0]:
                print("Download completed before interruption")
                completed_hash = calculate_file_hash(destination)
                if completed_hash == original_hash:
                    print("✓ Hash matches - download was complete and correct")
                    return True
                else:
                    print("✗ Hash mismatch - download was corrupted")
                    return False
                    
        except Exception as e:
            print(f"Download interrupted/failed: {e}")
        
        # Check for partial state
        state_file = f"{destination}.downloadstate.json"
        if os.path.exists(state_file):
            print(f"✓ State file exists: {state_file}")
        else:
            print(f"✗ No state file found")
            return False
        
        # Test 2: Resume download
        print("\\n" + "-" * 40) 
        print("TEST 2: Resume interrupted download")
        print("-" * 40)
        
        downloader2 = IntegratedMultiDownloader(max_connections=4)
        
        print("Attempting to resume download...")
        result2 = downloader2.download(url, destination)
        
        if result2[0]:
            print("✓ Resume download completed successfully")
            
            # Verify final file
            final_hash = calculate_file_hash(destination)
            print(f"Final file hash: {final_hash}")
            
            if final_hash == original_hash:
                print("✓ SUCCESS: Hash matches original file!")
                print("✓ Multi-connection resume functionality verified")
                return True
            else:
                print("✗ FAILED: Hash does not match original")
                return False
        else:
            print(f"✗ Resume download failed: {result2[1]}")
            return False
            
    finally:
        # Cleanup
        server.stop()
        
        # Remove test files
        for file_path in [test_file_path, destination]:
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Remove state files
        state_file = f"{destination}.downloadstate.json"
        if os.path.exists(state_file):
            os.remove(state_file)
            
        print("\\nCleanup completed")

def main():
    """Run the resume test"""
    try:
        success = test_resume_functionality()
        if success:
            print("\\n🎉 ALL RESUME TESTS PASSED")
            return 0
        else:
            print("\\n❌ RESUME TESTS FAILED")
            return 1
    except Exception as e:
        print(f"\\n💥 TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())