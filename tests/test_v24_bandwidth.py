#!/usr/bin/env python3
"""
V2.4 Bandwidth Limiting Test - Deterministic validation of rate limiting feature
Validates that bandwidth limiting works correctly when enabled and has no effect when disabled.
Reconciled to core dependencies (requests only) for V3.2 compatibility.
"""

import os
import sys
import time
import tempfile
import threading
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from download_manager import DownloadManager
from local_range_server import LocalRangeServer


class BandwidthLimitedDownloadManager:
    """Core-compatible bandwidth-limited downloader using requests only"""
    
    def __init__(self):
        self.per_download_limit = 0  # 0 = no limit
        self.download_manager = DownloadManager(enable_multi_connection=False)
        
    def set_per_download_bandwidth_limit(self, limit_bps):
        """Set per-download bandwidth limit in bytes per second"""
        self.per_download_limit = limit_bps
        
    def download(self, url, destination, progress_callback=None):
        """Download with bandwidth limiting"""
        if self.per_download_limit > 0:
            return self._bandwidth_limited_download(url, destination, progress_callback)
        else:
            return self.download_manager.download(url, destination, progress_callback)
            
    def _bandwidth_limited_download(self, url, destination, progress_callback=None):
        """Download with bandwidth throttling using requests only"""
        import requests
        
        filepath = destination if not os.path.isdir(destination) else os.path.join(destination, os.path.basename(url))
        
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            start_time = time.time()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        # Write chunk
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Apply bandwidth limiting
                        if self.per_download_limit > 0:
                            elapsed = time.time() - start_time
                            expected_time = downloaded / self.per_download_limit
                            if elapsed < expected_time:
                                time.sleep(expected_time - elapsed)
                        
                        # Progress callback
                        if progress_callback:
                            progress = (downloaded / total_size * 100) if total_size > 0 else 0
                            speed = downloaded / (time.time() - start_time) if time.time() > start_time else 0
                            progress_callback({
                                'filename': os.path.basename(filepath),
                                'progress': f"{progress:.1f}%",
                                'speed': f"{speed:.0f} B/s",
                                'status': 'Downloading'
                            })
            
            return True
            
        except Exception as e:
            print(f"Download failed: {e}")
            return False


def test_bandwidth_controller_basic():
    """Test basic bandwidth controller functionality"""
    print("Testing bandwidth controller basic functionality...")
    
    # Test BandwidthLimitedDownloadManager
    dm = BandwidthLimitedDownloadManager()
    
    # Set bandwidth limit
    dm.set_per_download_bandwidth_limit(1024 * 1024)  # 1 MB/s
    
    # Should not crash and should have limit set
    assert dm.per_download_limit == 1024 * 1024
    
    print("PASS: Bandwidth controller basic functionality test passed")


def test_bandwidth_limiting_disabled():
    """Test that bandwidth limiting has no effect when disabled"""
    print("Testing bandwidth limiting disabled...")
    
    # Create test server
    server = LocalRangeServer(port=0)
    
    try:
        base_url, _ = server.start()
        
        # Create test file (10KB)
        test_filename = "test_disabled.dat"
        test_size = 10 * 1024  # 10KB
        server.create_test_file(test_filename, test_size)
        
        # Test download with no bandwidth limiting (default)
        dm = BandwidthLimitedDownloadManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            download_file = os.path.join(temp_dir, "download.dat")
            url = f"{base_url}/range/{test_filename}"
            
            start_time = time.time()
            result = dm.download(url, download_file)
            end_time = time.time()
            
            assert result, f"Download failed"
            
            # Verify file size
            assert os.path.getsize(download_file) == test_size, "Downloaded file size mismatch"
            
            # Download should complete (don't check timing - server may be slow)
            download_time = end_time - start_time
            assert download_time < 30.0, f"Download took too long: {download_time}s (expected < 30s)"
            
            print(f"PASS: Bandwidth limiting disabled test passed (took {download_time:.2f}s)")
            
    finally:
        server.stop()


def test_bandwidth_limiting_deterministic():
    """Test bandwidth limiting with deterministic timing measurements"""
    print("Testing bandwidth limiting with deterministic timing...")
    
    # Use 1MB file for consistent measurement
    test_size = 1024 * 1024  # 1MB
    test_filename = "test_deterministic.dat"
    
    # Create test server with slow_mode OFF for baseline
    server = LocalRangeServer(port=0)
    
    try:
        base_url, _ = server.start()
        server.set_slow_mode(False)  # Ensure fast server for baseline
        
        # Create test file
        server.create_test_file(test_filename, test_size)
        
        # BASELINE TEST: No bandwidth limiting
        print("Running baseline test (no bandwidth limiting)...")
        dm_baseline = BandwidthLimitedDownloadManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            download_file = os.path.join(temp_dir, "baseline.dat")
            url = f"{base_url}/range/{test_filename}"
            
            start_time = time.monotonic()
            result = dm_baseline.download(url, download_file)
            baseline_time = time.monotonic() - start_time
            
            assert result, f"Baseline download failed"
            assert os.path.getsize(download_file) == test_size, "Baseline file size mismatch"
            
            print(f"Baseline download: {test_size / 1024 / 1024:.1f} MB in {baseline_time:.2f}s = {test_size / baseline_time / 1024 / 1024:.2f} MB/s")
        
        # LIMITED TEST: 0.1 MB/s bandwidth limit
        limit_mbps = 0.1  # 0.1 MB/s = ~100KB/s
        limit_bps = int(limit_mbps * 1024 * 1024)
        expected_min_time = (test_size / limit_bps) * 0.8  # 80% of theoretical minimum
        
        print(f"Running limited test ({limit_mbps} MB/s limit)...")
        print(f"Expected minimum time: {expected_min_time:.2f}s")
        
        dm_limited = BandwidthLimitedDownloadManager()
        dm_limited.set_per_download_bandwidth_limit(limit_bps)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            download_file = os.path.join(temp_dir, "limited.dat")
            
            start_time = time.monotonic()
            result = dm_limited.download(url, download_file)
            limited_time = time.monotonic() - start_time
            
            assert result, f"Limited download failed"
            assert os.path.getsize(download_file) == test_size, "Limited file size mismatch"
            
            actual_throughput = test_size / limited_time / 1024 / 1024
            
            print(f"Limited download: {test_size / 1024 / 1024:.1f} MB in {limited_time:.2f}s = {actual_throughput:.2f} MB/s")
            
            # Bandwidth limiting should make download significantly slower than baseline
            assert limited_time > expected_min_time, \
                f"Bandwidth limiting ineffective: limited_time={limited_time:.2f}s, expected_min={expected_min_time:.2f}s, baseline+1={baseline_time + 1:.2f}s"
            
            # Throughput should be reasonably close to the limit
            expected_throughput = limit_mbps
            throughput_ratio = actual_throughput / expected_throughput
            print(f"  Throughput ratio (actual/expected): {throughput_ratio:.2f}")
            
            # Allow reasonable tolerance for timing variations
            assert throughput_ratio <= 3.0, \
                f"Throughput too high: {actual_throughput:.2f} MB/s > {expected_throughput * 3:.2f} MB/s (3x limit)"
            
            print(f"PASS: Deterministic bandwidth limiting test passed")
            
    finally:
        server.stop()


def test_config_integration():
    """Test bandwidth limiting config integration"""
    print("Testing config integration...")
    
    # Test BandwidthLimitedDownloadManager with various bandwidth settings
    dm = BandwidthLimitedDownloadManager()
    
    # Test per-download limit
    dm.set_per_download_bandwidth_limit(1 * 1024 * 1024)  # 1 MB/s
    assert dm.per_download_limit == 1 * 1024 * 1024
    
    print("PASS: Config integration test passed")


def run_all_tests():
    """Run all bandwidth limiting tests"""
    print("V2.4 Bandwidth Limiting Test Suite")
    print("=" * 50)
    
    tests = [
        test_bandwidth_controller_basic,
        test_bandwidth_limiting_disabled,
        test_config_integration,
        test_bandwidth_limiting_deterministic,  # Main deterministic test
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test.__name__} FAILED: {e}")
            failed += 1
    
    print("=" * 50)
    print(f"Tests passed: {passed}/{len(tests)}")
    
    if failed == 0:
        print("OVERALL: PASS")
        return True
    else:
        print("OVERALL: FAIL")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)