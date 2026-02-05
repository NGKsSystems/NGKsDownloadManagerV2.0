#!/usr/bin/env python3
"""
Automated testing script for engine integrity improvements
Tests STEP 1 (hash verification) and STEP 2 (atomic file handling)
"""

import os
import sys
import time
import tempfile
import logging
from pathlib import Path
import re
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from download_manager import DownloadManager
from integrated_multi_downloader import IntegratedMultiDownloader

class EngineIntegrityTester:
    def __init__(self):
        self.test_dir = tempfile.mkdtemp(prefix="dl_test_")
        self.test_results = []
        
        # Setup logging capture
        self.log_messages = []
        self.setup_log_capture()
        
        print(f"Test directory: {self.test_dir}")
        
    def setup_log_capture(self):
        """Setup logging to capture engine messages"""
        # Create custom handler to capture log messages
        class TestLogHandler(logging.Handler):
            def __init__(self, test_instance):
                super().__init__()
                self.test_instance = test_instance
                
            def emit(self, record):
                self.test_instance.log_messages.append(record.getMessage())
        
        # Add handler to root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        test_handler = TestLogHandler(self)
        test_handler.setLevel(logging.INFO)
        root_logger.addHandler(test_handler)
        
    def test_basic_download_engine(self):
        """Test basic download engine with integrity gates"""
        print("\n=== Testing Basic Download Engine ===")
        
        try:
            downloader = DownloadManager()
            test_url = "https://httpbin.org/bytes/1024"  # 1KB test file
            test_file = os.path.join(self.test_dir, "basic_test.bin")
            
            # Clear log messages
            self.log_messages.clear()
            
            print(f"Downloading {test_url} to {test_file}")
            success, info = downloader.download(test_url, test_file)
            
            # Check results
            result = {
                'engine': 'basic',
                'success': success,
                'file_exists': os.path.exists(test_file),
                'file_size': os.path.getsize(test_file) if os.path.exists(test_file) else 0,
                'hash_logs': self.find_log_patterns(r'HASH \| (START|FINAL_OK|FINAL_FAIL)'),
                'atomic_logs': self.find_log_patterns(r'ATOMIC \| (START|COMMIT_OK|COMMIT_FAIL)')
            }
            
            self.test_results.append(result)
            self.print_test_result('Basic Download Engine', result)
            return result
            
        except Exception as e:
            print(f"Basic download test failed: {e}")
            return {'engine': 'basic', 'success': False, 'error': str(e)}
    
    def test_multi_connection_engine(self):
        """Test multi-connection download engine with integrity gates"""
        print("\n=== Testing Multi-Connection Download Engine ===")
        
        try:
            downloader = IntegratedMultiDownloader()
            test_url = "https://httpbin.org/bytes/2048"  # 2KB test file
            test_file = os.path.join(self.test_dir, "multi_test.bin")
            
            # Clear log messages
            self.log_messages.clear()
            
            print(f"Downloading {test_url} to {test_file}")
            success, info = downloader.download(test_url, test_file)
            
            # Check results
            result = {
                'engine': 'multi-connection',
                'success': success,
                'file_exists': os.path.exists(test_file),
                'file_size': os.path.getsize(test_file) if os.path.exists(test_file) else 0,
                'hash_logs': self.find_log_patterns(r'HASH \| (START|FINAL_OK|FINAL_FAIL)'),
                'atomic_logs': self.find_log_patterns(r'ATOMIC \| (START|COMMIT_OK|COMMIT_FAIL)'),
                'connections_used': info.get('connections_used', 0),
                'mode': info.get('mode', 'unknown')
            }
            
            self.test_results.append(result)
            self.print_test_result('Multi-Connection Download Engine', result)
            return result
            
        except Exception as e:
            print(f"Multi-connection download test failed: {e}")
            return {'engine': 'multi-connection', 'success': False, 'error': str(e)}
    
    def test_large_file_download(self):
        """Test larger file download to trigger multi-connection mode"""
        print("\n=== Testing Large File Download ===")
        
        try:
            downloader = IntegratedMultiDownloader()
            test_url = "https://httpbin.org/bytes/10240"  # 10KB test file
            test_file = os.path.join(self.test_dir, "large_test.bin")
            
            # Clear log messages
            self.log_messages.clear()
            
            print(f"Downloading {test_url} to {test_file}")
            success, info = downloader.download(test_url, test_file)
            
            # Check results
            result = {
                'engine': 'multi-connection-large',
                'success': success,
                'file_exists': os.path.exists(test_file),
                'file_size': os.path.getsize(test_file) if os.path.exists(test_file) else 0,
                'hash_logs': self.find_log_patterns(r'HASH \| (START|FINAL_OK|FINAL_FAIL)'),
                'atomic_logs': self.find_log_patterns(r'ATOMIC \| (START|COMMIT_OK|COMMIT_FAIL)'),
                'connections_used': info.get('connections_used', 0),
                'mode': info.get('mode', 'unknown')
            }
            
            self.test_results.append(result)
            self.print_test_result('Large File Download', result)
            return result
            
        except Exception as e:
            print(f"Large file download test failed: {e}")
            return {'engine': 'multi-connection-large', 'success': False, 'error': str(e)}
    
    def find_log_patterns(self, pattern: str) -> List[str]:
        """Find log messages matching the given regex pattern"""
        matches = []
        for msg in self.log_messages:
            if re.search(pattern, msg):
                matches.append(msg)
        return matches
    
    def print_test_result(self, test_name: str, result: Dict[str, Any]):
        """Print formatted test results"""
        print(f"\n{test_name} Results:")
        print(f"  ✅ Success: {result['success']}")
        if 'file_exists' in result:
            print(f"  📁 File exists: {result['file_exists']}")
            print(f"  📏 File size: {result['file_size']} bytes")
        
        if 'hash_logs' in result:
            print(f"  🔒 Hash verification logs: {len(result['hash_logs'])}")
            for log in result['hash_logs']:
                print(f"     {log}")
        
        if 'atomic_logs' in result:
            print(f"  ⚛️  Atomic operation logs: {len(result['atomic_logs'])}")
            for log in result['atomic_logs']:
                print(f"     {log}")
        
        if 'connections_used' in result:
            print(f"  🔗 Connections used: {result['connections_used']}")
            print(f"  📊 Download mode: {result['mode']}")
        
        if 'error' in result:
            print(f"  ❌ Error: {result['error']}")
            
    def verify_integrity_gates(self):
        """Verify that integrity gates are working correctly"""
        print("\n=== Verifying Integrity Gates ===")
        
        step1_verified = False
        step2_verified = False
        
        for result in self.test_results:
            if result.get('success', False):
                # Check STEP 1 (Hash Verification)
                hash_logs = result.get('hash_logs', [])
                has_hash_start = any('HASH | START' in log for log in hash_logs)
                has_hash_final = any('HASH | FINAL_OK' in log for log in hash_logs)
                
                if has_hash_start and has_hash_final:
                    step1_verified = True
                    
                # Check STEP 2 (Atomic File Handling)
                atomic_logs = result.get('atomic_logs', [])
                has_atomic_start = any('ATOMIC | START' in log for log in atomic_logs)
                has_atomic_commit = any('ATOMIC | COMMIT_OK' in log for log in atomic_logs)
                
                if has_atomic_start and has_atomic_commit:
                    step2_verified = True
        
        print(f"🔒 STEP 1 (Hash Verification): {'✅ VERIFIED' if step1_verified else '❌ FAILED'}")
        print(f"⚛️  STEP 2 (Atomic File Handling): {'✅ VERIFIED' if step2_verified else '❌ FAILED'}")
        
        return step1_verified, step2_verified
    
    def run_all_tests(self):
        """Run all automated tests"""
        print("🚀 Starting Automated Engine Integrity Testing")
        print("=" * 60)
        
        # Run tests
        self.test_basic_download_engine()
        time.sleep(1)
        
        self.test_multi_connection_engine()
        time.sleep(1)
        
        self.test_large_file_download()
        time.sleep(1)
        
        # Verify integrity gates
        step1_ok, step2_ok = self.verify_integrity_gates()
        
        # Final summary
        print("\n" + "=" * 60)
        print("📊 FINAL SUMMARY")
        print("=" * 60)
        
        for result in self.test_results:
            engine = result['engine']
            success = result.get('success', False)
            print(f"{engine:25} {'✅ PASS' if success else '❌ FAIL'}")
        
        print("\n🎯 INTEGRITY GATES:")
        print(f"STEP 1 (Hash Verification): {'✅ WORKING' if step1_ok else '❌ NOT WORKING'}")
        print(f"STEP 2 (Atomic Handling):   {'✅ WORKING' if step2_ok else '❌ NOT WORKING'}")
        
        overall_success = all(r.get('success', False) for r in self.test_results) and step1_ok and step2_ok
        print(f"\n🏆 OVERALL RESULT: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
        
        return overall_success
    
    def cleanup(self):
        """Clean up test files"""
        try:
            import shutil
            shutil.rmtree(self.test_dir, ignore_errors=True)
            print(f"\n🧹 Cleaned up test directory: {self.test_dir}")
        except Exception as e:
            print(f"Cleanup warning: {e}")

if __name__ == "__main__":
    tester = EngineIntegrityTester()
    try:
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    finally:
        tester.cleanup()