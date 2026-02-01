#!/usr/bin/env python3
"""
Download Manager V2.1 Acceptance Test - Stable Server Lifecycle
=====================================
Deterministic test of multi-connection download with interruption and resume.

Tests:
1. Multi-connection mode verification (4 connections)
2. Single-connection fallback verification 
3. Interruption and resume with hash verification
"""

import os
import sys
import time
import hashlib
import threading
import tempfile
import shutil
import glob
import json

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from integrated_multi_downloader import IntegratedMultiDownloader
from local_range_server import LocalRangeServer


class V21AcceptanceTest:
    """V2.1 acceptance test with stable server lifecycle"""
    
    def __init__(self):
        self.test_dir = None
        self.server = None
        self.base_url = None
        self.test_filename = "testfile.dat"
        self.test_size = 12 * 1024 * 1024  # 12MB - above multi-connection threshold
        self.resume_test_filename = "resume_testfile.dat"
        self.resume_test_size = 48 * 1024 * 1024  # 48MB for interruption test
        self.source_hash = None
        self.resume_source_hash = None
        self.results = []
        
    def setup(self):
        """Set up test environment with stable server"""
        print("Download Manager V2.1 Acceptance Test")
        print("=" * 50)
        
        # Create test directory
        self.test_dir = tempfile.mkdtemp(prefix="v21_acceptance_")
        print(f"Test directory: {self.test_dir}")
        
        # Start stable server
        self.server = LocalRangeServer(port=0)
        self.base_url, _ = self.server.start()
        print(f"Server started at: {self.base_url}")
        print(f"Serve directory: {self.server.serve_dir}")
        print(f"Range endpoint: {self.base_url}/range/")
        print(f"No-range endpoint: {self.base_url}/norange/")
        
        # Create test file
        print(f"Creating {self.test_size // (1024*1024)}MB test file...")
        self.server.create_test_file(self.test_filename, self.test_size)
        self.source_hash = self.server.get_file_hash(self.test_filename)
        print(f"Source file hash: {self.source_hash}")
        
        # Create larger test file for resume testing
        print(f"Creating {self.resume_test_size // (1024*1024)}MB resume test file...")
        self.server.create_test_file(self.resume_test_filename, self.resume_test_size)
        self.resume_source_hash = self.server.get_file_hash(self.resume_test_filename)
        print(f"Resume test file hash: {self.resume_source_hash}")
        
    def teardown(self):
        """Clean up test environment"""
        print("\nTeardown:")
        
        if self.server:
            self.server.stop()
            print("Server stopped")
            
        if self.test_dir and os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
            print("Test directory cleaned")
            
    def calculate_file_hash(self, filepath):
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
        
    def test_multi_connection_mode(self):
        """Test multi-connection download with 4 connections"""
        print("\n=== Test 1: Multi-Connection Mode ===")
        
        try:
            # Download from /range/ endpoint 
            url = f"{self.base_url}/range/{self.test_filename}"
            output_path = os.path.join(self.test_dir, "download_multi.dat")
            
            print(f"Base URL: {self.base_url}")
            print(f"Serve directory: {self.server.serve_dir}")
            print(f"Exact URL: {url}")
            print(f"Downloading {url}")
            print("Expected: multi-connection mode, 4 connections")
            
            downloader = IntegratedMultiDownloader(max_connections=4)
            start_time = time.time()
            success, info = downloader.download(url=url, destination=output_path)
            end_time = time.time()
            
            # Verify results
            if not success:
                self.results.append(("Multi-Connection Mode", False, "Download failed"))
                return False
                
            # Check file exists and size
            if not os.path.exists(output_path):
                self.results.append(("Multi-Connection Mode", False, "Output file missing"))
                return False
                
            actual_size = os.path.getsize(output_path)
            if actual_size != self.test_size:
                self.results.append(("Multi-Connection Mode", False, f"Size mismatch: {actual_size} != {self.test_size}"))
                return False
                
            # Verify mode and connections
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
                
            duration = end_time - start_time
            print(f"PASS: Multi-mode verified (mode={mode}, connections={connections_used}, time={duration:.2f}s)")
            self.results.append(("Multi-Connection Mode", True, f"mode={mode}, connections={connections_used}"))
            return True
            
        except Exception as e:
            self.results.append(("Multi-Connection Mode", False, f"Exception: {str(e)}"))
            return False
            
    def test_single_connection_fallback(self):
        """Test single-connection fallback when no ranges supported"""
        print("\n=== Test 2: Single-Connection Fallback ===")
        
        try:
            # Download from /norange/ endpoint
            url = f"{self.base_url}/norange/{self.test_filename}"
            output_path = os.path.join(self.test_dir, "download_single.dat")
            
            print(f"Base URL: {self.base_url}")
            print(f"Serve directory: {self.server.serve_dir}")
            print(f"Exact URL: {url}")
            print(f"Downloading {url}")
            print("Expected: single-connection fallback")
            
            downloader = IntegratedMultiDownloader(max_connections=4)
            success, info = downloader.download(url=url, destination=output_path)
            
            # Verify results
            if not success:
                self.results.append(("Single-Connection Fallback", False, "Download failed"))
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
                
            print(f"PASS: Single fallback verified (mode={mode}, connections={connections_used})")
            self.results.append(("Single-Connection Fallback", True, f"mode={mode}, connections={connections_used}"))
            return True
            
        except Exception as e:
            self.results.append(("Single-Connection Fallback", False, f"Exception: {str(e)}"))
            return False
            
    def test_interruption_and_resume(self):
        """Test interruption and resume with strict verification"""
        print("\n=== Test 3: Interruption and Resume ===")
        print("Testing with 48MB file for reliable interruption")
        
        try:
            # Enable slow mode for reliable interruption
            self.server.set_slow_mode(True)
            
            url = f"{self.base_url}/range/{self.resume_test_filename}"
            output_path = os.path.join(self.test_dir, "download_resume.dat")
            state_file = output_path + ".downloadstate.json"
            
            print(f"Base URL: {self.base_url}")
            print(f"Serve directory: {self.server.serve_dir}")
            print(f"Exact URL: {url}")
            print(f"Testing interruption and resume for {url}")
            print("(Using 48MB file with slow mode for reliable interruption)")
            
            # Phase 1: Start download and interrupt
            print("Phase 1: Starting download and interrupting...")
            downloader = IntegratedMultiDownloader(max_connections=4)
            
            download_result = [None]  # Mutable container for thread result
            
            def download_worker():
                download_result[0] = downloader.download(url=url, destination=output_path)
                
            download_thread = threading.Thread(target=download_worker)
            download_thread.start()
            
            # Wait for download to start and create significant part files
            print("Waiting for substantial part files to appear...")
            substantial_progress_found = False
            wait_start = time.time()
            
            while time.time() - wait_start < 30:  # Max 30 second wait
                part_files = glob.glob(output_path + ".part*")
                if part_files:
                    # Check if any part file has substantial data (at least 1MB)
                    total_partial_size = 0
                    for part_file in part_files:
                        if os.path.exists(part_file):
                            total_partial_size += os.path.getsize(part_file)
                    
                    # We need at least 4MB downloaded before interrupting
                    if total_partial_size > 4 * 1024 * 1024:  # 4MB
                        substantial_progress_found = True
                        print(f"Found {total_partial_size / (1024*1024):.1f}MB partial data")
                        break
                time.sleep(1.5)
            
            if not substantial_progress_found:
                self.results.append(("Interruption & Resume", False, "Insufficient partial data for interruption test"))
                return False
                
            print("Substantial progress found, triggering cancellation...")
            downloader.cancel_download()
            
            # Wait for download to complete (should fail due to cancellation)
            download_thread.join(timeout=15)
            
            # Verify interruption results - MUST fail for valid test
            if download_result[0] is not None:
                success, _ = download_result[0]
                if success:
                    # If download completed despite cancellation, this is NOT a valid resume test
                    print("FAIL: Download completed before cancellation - not a valid resume test")
                    self.results.append(("Interruption & Resume", False, "Download completed before cancellation"))
                    return False
                print("Download was properly interrupted")
            else:
                print("Download thread timed out (interrupted as expected)")
                
            # Check that state file exists after interruption
            if not os.path.exists(state_file):
                self.results.append(("Interruption & Resume", False, "Download failed but no state file created"))
                return False
                
            print("State file created successfully")
            
            # Verify state file structure
            with open(state_file, 'r') as f:
                state = json.load(f)
                
            required_fields = ['url', 'total_size', 'max_connections', 'segments']
            for field in required_fields:
                if field not in state:
                    self.results.append(("Interruption & Resume", False, f"Missing state field: {field}"))
                    return False
                    
            print("State file structure verified")
            
            # Disable slow mode for resume
            self.server.set_slow_mode(False)
            
            # Phase 2: Resume download
            print("Phase 2: Resuming download...")
            downloader2 = IntegratedMultiDownloader(max_connections=4)
            success, info = downloader2.download(url=url, destination=output_path)
            
            if not success:
                self.results.append(("Interruption & Resume", False, "Resume download failed"))
                return False
                
            # Verify final results
            if not os.path.exists(output_path):
                self.results.append(("Interruption & Resume", False, "Final output file missing"))
                return False
                
            final_size = os.path.getsize(output_path)
            if final_size != self.resume_test_size:
                self.results.append(("Interruption & Resume", False, f"Final size mismatch: {final_size} != {self.resume_test_size}"))
                return False
                
            # Verify hash matches original
            final_hash = self.calculate_file_hash(output_path)
            if final_hash != self.resume_source_hash:
                self.results.append(("Interruption & Resume", False, "Final hash mismatch after resume"))
                return False
                
            print("PASS: Interrupt+resume verified (48MB file, hash match)")
            self.results.append(("Interruption & Resume", True, "interrupt+resume verified with 48MB file"))
            return True
            
        except Exception as e:
            self.results.append(("Interruption & Resume", False, f"Exception: {str(e)}"))
            return False
        finally:
            # Always disable slow mode
            if self.server:
                self.server.set_slow_mode(False)
            
    def run_all_tests(self):
        """Run all acceptance tests"""
        try:
            self.setup()
            
            # Run tests
            test_methods = [
                self.test_multi_connection_mode,
                self.test_single_connection_fallback, 
                self.test_interruption_and_resume
            ]
            
            passed = 0
            total = len(test_methods)
            
            for test_method in test_methods:
                if test_method():
                    passed += 1
                    
            # Print results
            print("\n" + "=" * 50)
            print("FINAL RESULTS")
            print("=" * 50)
            
            for test_name, success, details in self.results:
                status = "PASS" if success else "FAIL"
                print(f"{status}: {test_name} - {details}")
                
            print(f"\nTests passed: {passed}/{total}")
            
            if passed == total:
                print("OVERALL: PASS")
                return True
            else:
                print("OVERALL: FAIL")
                return False
                
        except Exception as e:
            print(f"\nTest framework error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.teardown()


def main():
    """Run the V2.1 acceptance test"""
    test = V21AcceptanceTest()
    success = test.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()