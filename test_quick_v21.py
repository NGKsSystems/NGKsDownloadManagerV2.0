#!/usr/bin/env python3
"""
DEPRECATED: Use test_v21_acceptance.py instead
V2.1 Quick Verification Test - Shows clear PASS/FAIL for all 3 tests
"""

import os
import sys
import time
import tempfile
import shutil
import hashlib
import threading
import glob
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from integrated_multi_downloader import IntegratedMultiDownloader
from local_range_server import LocalRangeServer

class QuickV21Test:
    def __init__(self):
        self.test_dir = None
        self.server = None
        self.results = []
        
    def calculate_file_hash(self, filepath):
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
        
    def setup(self):
        """Set up test environment"""
        print("V2.1 Quick Verification Test")
        print("=" * 40)
        
        # Create test directory
        self.test_dir = tempfile.mkdtemp(prefix="v21_quick_")
        print(f"Test directory: {self.test_dir}")
        
        # Start server
        self.server = LocalRangeServer(port=0)
        base_url, _ = self.server.start()
        self.base_url = base_url
        print(f"Server: {base_url}")
        
        # Create test files
        self.server.create_test_file("test12mb.dat", 12 * 1024 * 1024)  # 12MB
        self.server.create_test_file("test24mb.dat", 24 * 1024 * 1024)  # 24MB for resume
        
        self.hash_12mb = self.server.get_file_hash("test12mb.dat")
        self.hash_24mb = self.server.get_file_hash("test24mb.dat")
        
    def teardown(self):
        """Clean up"""
        if self.server:
            self.server.stop()
        if self.test_dir and os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
            
    def test1_multi_connection(self):
        """Test 1: Multi-connection mode"""
        print("\\nTest 1: Multi-connection mode")
        try:
            url = f"{self.base_url}/range/test12mb.dat"
            output_path = os.path.join(self.test_dir, "multi.dat")
            
            downloader = IntegratedMultiDownloader(max_connections=4)
            success, info = downloader.download(url, output_path)
            
            if success and info.get('mode') == 'multi' and info.get('connections_used') == 4:
                if self.calculate_file_hash(output_path) == self.hash_12mb:
                    print("PASS: Multi-connection mode verified")
                    return True
                    
            print("FAIL: Multi-connection mode failed")
            return False
        except Exception as e:
            print(f"FAIL: Multi-connection exception: {e}")
            return False
            
    def test2_single_fallback(self):
        """Test 2: Single-connection fallback"""
        print("\\nTest 2: Single-connection fallback")
        try:
            url = f"{self.base_url}/norange/test12mb.dat"
            output_path = os.path.join(self.test_dir, "single.dat")
            
            downloader = IntegratedMultiDownloader(max_connections=4)
            success, info = downloader.download(url, output_path)
            
            if success and info.get('mode') == 'single' and info.get('connections_used') == 1:
                if self.calculate_file_hash(output_path) == self.hash_12mb:
                    print("PASS: Single-connection fallback verified")
                    return True
                    
            print("FAIL: Single-connection fallback failed")
            return False
        except Exception as e:
            print(f"FAIL: Single-connection exception: {e}")
            return False
            
    def test3_interrupt_resume(self):
        """Test 3: Interrupt and resume"""
        print("\\nTest 3: Interrupt and resume")
        try:
            # Enable slow mode
            self.server.set_slow_mode(True)
            
            url = f"{self.base_url}/range/test24mb.dat"
            output_path = os.path.join(self.test_dir, "resume.dat")
            state_file = output_path + ".downloadstate.json"
            
            # Phase 1: Start and interrupt
            downloader = IntegratedMultiDownloader(max_connections=4)
            download_result = [None]
            
            def download_worker():
                download_result[0] = downloader.download(url, output_path)
                
            download_thread = threading.Thread(target=download_worker)
            download_thread.start()
            
            # Wait for substantial progress
            time.sleep(8)  # Wait 8 seconds for progress
            
            # Check if we have partial files
            part_files = glob.glob(output_path + ".part*")
            total_partial = sum(os.path.getsize(f) for f in part_files if os.path.exists(f))
            
            if total_partial < 2 * 1024 * 1024:  # Less than 2MB
                print("FAIL: Insufficient partial data for test")
                return False
                
            # Cancel download
            downloader.cancel_download()
            download_thread.join(timeout=10)
            
            # Check if download properly failed
            if download_result[0] and download_result[0][0]:
                print("FAIL: Download completed before cancellation")
                return False
                
            # Check state file exists
            if not os.path.exists(state_file):
                print("FAIL: No state file after interruption")
                return False
                
            # Phase 2: Resume
            self.server.set_slow_mode(False)
            downloader2 = IntegratedMultiDownloader(max_connections=4)
            success, info = downloader2.download(url, output_path)
            
            if success and self.calculate_file_hash(output_path) == self.hash_24mb:
                print("PASS: Interrupt and resume verified")
                return True
            else:
                print("FAIL: Resume failed or hash mismatch")
                return False
                
        except Exception as e:
            print(f"FAIL: Interrupt/resume exception: {e}")
            return False
        finally:
            if self.server:
                self.server.set_slow_mode(False)
    
    def run_all(self):
        """Run all tests"""
        try:
            self.setup()
            
            test1_pass = self.test1_multi_connection()
            test2_pass = self.test2_single_fallback()
            test3_pass = self.test3_interrupt_resume()
            
            print("\\n" + "=" * 40)
            print("FINAL RESULTS:")
            print("=" * 40)
            print(f"Test 1 (Multi-connection): {'PASS' if test1_pass else 'FAIL'}")
            print(f"Test 2 (Single fallback): {'PASS' if test2_pass else 'FAIL'}")
            print(f"Test 3 (Interrupt+resume): {'PASS' if test3_pass else 'FAIL'}")
            
            if all([test1_pass, test2_pass, test3_pass]):
                print("\\nOVERALL: PASS")
                return True
            else:
                print("\\nOVERALL: FAIL")
                return False
                
        finally:
            self.teardown()

def main():
    test = QuickV21Test()
    success = test.run_all()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()