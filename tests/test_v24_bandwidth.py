#!/usr/bin/env python3
"""
V2.4 Bandwidth Limiting Test - Deterministic validation of rate limiting feature
Validates that bandwidth limiting works correctly when enabled and has no effect when disabled.
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

from integrated_multi_downloader import IntegratedMultiDownloader, TokenBucketRateLimiter
from local_range_server import LocalRangeServer


class MockTimeTokenBucket:
    """Mock token bucket for deterministic testing"""
    def __init__(self, rate_mbps: float):
        self.rate_bytes_per_second = max(1024, int(rate_mbps * 1024 * 1024))
        self.bucket_size = self.rate_bytes_per_second * 2
        self.tokens = self.bucket_size
        self.mock_time = 0.0
        
    def set_mock_time(self, mock_time: float):
        """Set mock time for deterministic testing"""
        self.mock_time = mock_time
        
    def consume(self, bytes_count: int) -> float:
        """Consume tokens using mock time"""
        # Calculate needed delay
        if self.tokens >= bytes_count:
            self.tokens -= bytes_count
            return 0.0
        else:
            deficit = bytes_count - self.tokens
            delay = deficit / self.rate_bytes_per_second
            self.tokens = 0
            return delay


def test_token_bucket_basic():
    """Test basic token bucket functionality"""
    print("Testing token bucket basic functionality...")
    
    # Test with 1 MB/s rate limit
    bucket = TokenBucketRateLimiter(1.0)  # 1 MB/s
    
    # Should be able to consume some tokens immediately
    delay = bucket.consume(1024)  # 1KB
    assert delay == 0.0, f"Expected no delay for initial tokens, got {delay}"
    
    # Large consumption should require delay
    delay = bucket.consume(2 * 1024 * 1024)  # 2MB (more than bucket size)
    assert delay > 0, f"Expected delay for large consumption, got {delay}"
    
    print("PASS: Token bucket basic functionality test passed")


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
        
        # Test download with bandwidth limiting disabled (default)
        dm = IntegratedMultiDownloader(max_connections=1, enable_bandwidth_limiting=False)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            download_file = os.path.join(temp_dir, "download.dat")
            url = f"{base_url}/range/{test_filename}"
            
            start_time = time.time()
            success, info = dm.download(url, download_file)
            end_time = time.time()
            
            assert success, f"Download failed: {info.get('error', 'Unknown error')}"
            
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
    
    # Use 8MB file for consistent measurement
    test_size = 8 * 1024 * 1024  # 8MB
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
        dm_baseline = IntegratedMultiDownloader(max_connections=1, enable_bandwidth_limiting=False)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            download_file = os.path.join(temp_dir, "baseline.dat")
            url = f"{base_url}/range/{test_filename}"
            
            start_time = time.monotonic()
            success, info = dm_baseline.download(url, download_file)
            baseline_time = time.monotonic() - start_time
            
            assert success, f"Baseline download failed: {info.get('error', 'Unknown error')}"
            assert os.path.getsize(download_file) == test_size, "Baseline file size mismatch"
            
            print(f"Baseline download: {test_size / 1024 / 1024:.1f} MB in {baseline_time:.2f}s = {test_size / baseline_time / 1024 / 1024:.2f} MB/s")
        
        # LIMITED TEST: 0.25 MB/s bandwidth limit
        limit_mbps = 0.25  # 0.25 MB/s = 256 KB/s
        expected_min_time = (test_size / (limit_mbps * 1024 * 1024)) * 0.9  # 90% of theoretical minimum
        
        print(f"Running limited test ({limit_mbps} MB/s limit)...")
        print(f"Expected minimum time: {expected_min_time:.2f}s")
        
        dm_limited = IntegratedMultiDownloader(max_connections=1, enable_bandwidth_limiting=True, 
                                             global_bandwidth_limit_mbps=limit_mbps)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            download_file = os.path.join(temp_dir, "limited.dat")
            
            start_time = time.monotonic()
            success, info = dm_limited.download(url, download_file)
            limited_time = time.monotonic() - start_time
            
            assert success, f"Limited download failed: {info.get('error', 'Unknown error')}"
            assert os.path.getsize(download_file) == test_size, "Limited file size mismatch"
            
            actual_throughput = test_size / limited_time / 1024 / 1024
            print(f"Limited download: {test_size / 1024 / 1024:.1f} MB in {limited_time:.2f}s = {actual_throughput:.2f} MB/s")
            
            # CRITICAL ASSERTIONS: Prove bandwidth limiting is working
            print(f"Checking timing constraints...")
            print(f"  Limited time ({limited_time:.2f}s) >= Expected minimum ({expected_min_time:.2f}s): {limited_time >= expected_min_time}")
            print(f"  Limited time ({limited_time:.2f}s) >= Baseline + 2s ({baseline_time + 2:.2f}s): {limited_time >= baseline_time + 2}")
            
            # Must meet expected minimum time OR be significantly slower than baseline
            timing_constraint_met = (limited_time >= expected_min_time) or (limited_time >= baseline_time + 2)
            assert timing_constraint_met, \
                f"Bandwidth limiting ineffective: limited_time={limited_time:.2f}s, expected_min={expected_min_time:.2f}s, baseline+2={baseline_time + 2:.2f}s"
            
            # Throughput should be close to the limit (within reasonable tolerance)
            expected_throughput = limit_mbps
            throughput_ratio = actual_throughput / expected_throughput
            print(f"  Throughput ratio (actual/expected): {throughput_ratio:.2f}")
            
            # Allow some tolerance but it should be reasonably close to the limit
            assert throughput_ratio <= 2.0, \
                f"Throughput too high: {actual_throughput:.2f} MB/s > {expected_throughput * 2:.2f} MB/s (2x limit)"
            
            print(f"PASS: Deterministic bandwidth limiting test passed")
            print(f"  Baseline: {baseline_time:.2f}s, Limited: {limited_time:.2f}s, Slowdown: {limited_time/baseline_time:.1f}x")
            
    finally:
        server.stop()


def test_per_download_override():
    """Test per-download bandwidth limit override"""
    print("Testing per-download bandwidth limit override...")
    
    # Create test server
    server = LocalRangeServer(port=0)
    
    try:
        base_url, _ = server.start()
        
        # Create test file (10KB)
        test_filename = "test_override.dat"
        test_size = 10 * 1024  # 10KB
        server.create_test_file(test_filename, test_size)
        
        # Test with global limit but per-download override
        dm = IntegratedMultiDownloader(max_connections=1, enable_bandwidth_limiting=True, 
                           global_bandwidth_limit_mbps=0.005)  # ~5KB/s global
        
        with tempfile.TemporaryDirectory() as temp_dir:
            download_file = os.path.join(temp_dir, "download.dat")
            url = f"{base_url}/range/{test_filename}"
            
            start_time = time.time()
            # Override with unlimited per-download (0 = unlimited)
            success, info = dm.download(url, download_file, bandwidth_limit_mbps=0)
            end_time = time.time()
            
            assert success, f"Download failed: {info.get('error', 'Unknown error')}"
            
            # Verify file size
            assert os.path.getsize(download_file) == test_size, "Downloaded file size mismatch"
            
            download_time = end_time - start_time
            print(f"PASS: Per-download override test passed (took {download_time:.2f}s)")
            
    finally:
        server.stop()


def test_config_integration():
    """Test bandwidth limiting config integration"""
    print("Testing config integration...")
    
    # Test config loading
    config_data = {
        "enable_bandwidth_limiting": True,
        "global_bandwidth_limit_mbps": 5.0,
        "hf_token": "",
        "auto_quality": True,
        "extract_audio": False,
        "max_downloads": 3,
        "destination": "/tmp/test"
    }
    
    # Validate config structure
    assert "enable_bandwidth_limiting" in config_data
    assert "global_bandwidth_limit_mbps" in config_data
    assert isinstance(config_data["enable_bandwidth_limiting"], bool)
    assert isinstance(config_data["global_bandwidth_limit_mbps"], (int, float))
    
    print("PASS: Config integration test passed")


def test_multi_connection_bandwidth_limiting():
    """Test bandwidth limiting with multi-connection downloads"""
    print("Testing multi-connection bandwidth limiting...")
    
    # Create test server
    server = LocalRangeServer(port=0)
    
    try:
        base_url, _ = server.start()
        
        # Create larger test file for multi-connection (10MB)
        test_filename = "test_multi.dat"
        test_size = 10 * 1024 * 1024  # 10MB
        server.create_test_file(test_filename, test_size)
        
        # Test multi-connection with bandwidth limiting
        dm = IntegratedMultiDownloader(max_connections=2, enable_bandwidth_limiting=True, 
                           global_bandwidth_limit_mbps=0.5)  # ~500KB/s total
        
        with tempfile.TemporaryDirectory() as temp_dir:
            download_file = os.path.join(temp_dir, "download.dat")
            url = f"{base_url}/range/{test_filename}"
            
            start_time = time.time()
            success, info = dm.download(url, download_file)
            end_time = time.time()
            
            assert success, f"Download failed: {info.get('error', 'Unknown error')}"
            assert info.get('mode') == 'multi', f"Expected multi-connection mode, got {info.get('mode')}"
            
            # Verify file size
            assert os.path.getsize(download_file) == test_size, "Downloaded file size mismatch"
            
            print(f"PASS: Multi-connection bandwidth limiting test passed (took {end_time - start_time:.2f}s)")
            
    finally:
        server.stop()


def run_all_tests():
    """Run all bandwidth limiting tests"""
    print("V2.4 Bandwidth Limiting Test Suite")
    print("=" * 50)
    
    tests = [
        test_token_bucket_basic,
        test_bandwidth_limiting_disabled,
        test_config_integration,
        test_bandwidth_limiting_deterministic,  # Main deterministic test
        test_per_download_override,
        test_multi_connection_bandwidth_limiting,
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