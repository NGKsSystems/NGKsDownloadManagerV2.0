#!/usr/bin/env python3
"""
Quick range detection test
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from local_range_server import LocalRangeServer
from http_range_detector import supports_http_range
import time

def test_range_detection():
    print("Testing Range Detection")
    print("=" * 30)
    
    # Start server
    server = LocalRangeServer(port=0)
    server.start_background()
    
    port = server.actual_port
    base_url = f"http://localhost:{port}"
    
    # Create test file
    test_filename = "test.dat"
    server.create_test_file(test_filename, 1024 * 10)  # 10KB
    
    url = f"{base_url}/{test_filename}"
    print(f"Testing URL: {url}")
    
    # Test range detection
    supports_range, info = supports_http_range(url)
    
    print(f"Supports Range: {supports_range}")
    print(f"Range Info: {info}")
    
    server.shutdown()

if __name__ == "__main__":
    test_range_detection()