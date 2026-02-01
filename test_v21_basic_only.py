#!/usr/bin/env python3
"""
V2.1 Acceptance Test - Modified (no interruption test)
Tests basic multi-connection and single-connection modes only
"""

import os
import sys
import time
import tempfile
import shutil
import hashlib
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from integrated_multi_downloader import IntegratedMultiDownloader
from local_range_server import LocalRangeServer

class V21AcceptanceTestModified:
    def __init__(self):
        self.test_dir = None
        self.server = None
        self.results = []
        self.test_size = 12 * 1024 * 1024  # 12MB
        self.source_hash = None
        
        # Configure logging to reduce noise
        logging.basicConfig(level=logging.ERROR)
        
    def calculate_file_hash(self, file_path):
        """Calculate SHA256 hash of a file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
        
    def setup(self):
        """Set up test environment"""
        print("Download Manager V2.1 Acceptance Test (Modified)")
        print("=" * 50)
        
        # Create test directory
        self.test_dir = tempfile.mkdtemp(prefix="v21_acceptance_")
        print(f"Test directory: {self.test_dir}")
        
        # Start server
        self.server = LocalRangeServer()
        self.server.start()
        print(f"Server started at: {self.server.base_url}")
        
        # Create test file
        print("Creating 12MB test file...")
        test_content = b"X" * self.test_size
        test_file = os.path.join(self.server.serve_dir, "testfile.dat")
        with open(test_file, 'wb') as f:
            f.write(test_content)
            
        # Calculate source hash
        self.source_hash = self.calculate_file_hash(test_file)
        print(f"Source file hash: {self.source_hash}")
        
    def teardown(self):
        """Clean up test environment"""
        print("\nTeardown:")
        if self.server:
            self.server.stop()
            print("Server stopped")
        if self.test_dir and os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
            print("Test directory cleaned")
            
    def test_multi_connection_mode(self):
        """Test multi-connection mode"""
        print("\n=== Test 1: Multi-Connection Mode ===")
        url = f"{self.server.base_url}/range/testfile.dat"
        output_path = os.path.join(self.test_dir, "multi_download.dat")
        
        print(f"Downloading {url}")
        print("Expected: multi-connection mode, 4 connections")
        
        try:
            downloader = IntegratedMultiDownloader(max_connections=4)
            start_time = time.time()
            
            success, info = downloader.download(url, output_path)
            elapsed = time.time() - start_time
            
            if not success:
                self.results.append(("Multi-Connection Mode", False, f"Download failed: {info}"))
                return False
                
            # Check file size
            actual_size = os.path.getsize(output_path)
            if actual_size != self.test_size:
                self.results.append(("Multi-Connection Mode", False, f"Size mismatch: {actual_size} != {self.test_size}"))
                return False
                
            # Verify mode (should be multi)
            mode = info.get('mode', 'unknown')
            connections_used = info.get('connections_used', 0)
            
            if mode != 'multi':
                self.results.append(("Multi-Connection Mode", False, f"Wrong mode: {mode}, expected 'multi'"))
                return False
                
            if connections_used != 4:
                self.results.append(("Multi-Connection Mode", False, f"Wrong connection count: {connections_used}, expected 4"))
                return False
                
            # Verify hash
            downloaded_hash = self.calculate_file_hash(output_path)
            if downloaded_hash != self.source_hash:
                self.results.append(("Multi-Connection Mode", False, "Hash mismatch"))
                return False
                
            print(f"PASS: Multi-mode verified (mode={mode}, connections={connections_used}, time={elapsed:.2f}s)")
            self.results.append(("Multi-Connection Mode", True, f"mode={mode}, connections={connections_used}"))
            return True
            
        except Exception as e:
            self.results.append(("Multi-Connection Mode", False, f"Exception: {str(e)}"))
            print(f"FAIL: Exception during multi-connection test: {e}")
            return False
            
    def test_single_connection_fallback(self):
        """Test single-connection fallback with no-range server"""
        print("\n=== Test 2: Single-Connection Fallback ===")
        url = f"{self.server.base_url}/norange/testfile.dat"
        output_path = os.path.join(self.test_dir, "single_download.dat")
        
        print(f"Downloading {url}")
        print("Expected: single-connection fallback")
        
        try:
            downloader = IntegratedMultiDownloader(max_connections=4)
            start_time = time.time()
            
            success, info = downloader.download(url, output_path)
            elapsed = time.time() - start_time
            
            if not success:
                self.results.append(("Single-Connection Fallback", False, f"Download failed: {info}"))
                return False
                
            # Check file size
            actual_size = os.path.getsize(output_path)
            if actual_size != self.test_size:
                self.results.append(("Single-Connection Fallback", False, f"Size mismatch: {actual_size} != {self.test_size}"))
                return False
                
            # Verify mode (should be single)
            mode = info.get('mode', 'unknown')
            connections_used = info.get('connections_used', 0)
            
            if mode != 'single':
                self.results.append(("Single-Connection Fallback", False, f"Wrong mode: {mode}, expected 'single'"))
                return False
                
            if connections_used != 1:
                self.results.append(("Single-Connection Fallback", False, f"Wrong connection count: {connections_used}, expected 1"))
                return False
                
            # Verify hash
            downloaded_hash = self.calculate_file_hash(output_path)
            if downloaded_hash != self.source_hash:
                self.results.append(("Single-Connection Fallback", False, "Hash mismatch"))
                return False
                
            print(f"PASS: Single fallback verified (mode={mode}, connections={connections_used}, time={elapsed:.2f}s)")
            self.results.append(("Single-Connection Fallback", True, f"mode={mode}, connections={connections_used}"))
            return True
            
        except Exception as e:
            self.results.append(("Single-Connection Fallback", False, f"Exception: {str(e)}"))
            print(f"FAIL: Exception during single-connection test: {e}")
            return False
            
    def run_tests(self):
        """Run the basic acceptance tests"""
        try:
            self.setup()
            
            # Run tests
            test1_pass = self.test_multi_connection_mode()
            test2_pass = self.test_single_connection_fallback()
            
            # Print results
            print("\n" + "=" * 50)
            print("FINAL RESULTS")
            print("=" * 50)
            
            for test_name, success, details in self.results:
                status = "PASS" if success else "FAIL"
                print(f"{status}: {test_name} - {details}")
            
            passed = sum(1 for _, success, _ in self.results if success)
            total = len(self.results)
            
            print(f"\nPassed: {passed}/{total}")
            
            if passed == total:
                print("Overall: PASS")
                return True
            else:
                print("Overall: FAIL") 
                return False
                
        finally:
            self.teardown()

def main():
    test = V21AcceptanceTestModified()
    success = test.run_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()