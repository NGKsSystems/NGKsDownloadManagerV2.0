#!/usr/bin/env python3
"""
Simple Interruption Test
"""

import os
import sys
import threading
import time
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from integrated_multi_downloader import IntegratedMultiDownloader
from local_range_server import LocalRangeServer


def simple_interruption_test():
    print("Simple Interruption Test")
    print("=" * 30)
    
    # Setup
    test_dir = tempfile.mkdtemp(prefix="simple_test_")
    server = LocalRangeServer(port=0)
    base_url, _ = server.start()
    
    try:
        # Create test file
        test_filename = "test.dat"
        test_size = 12 * 1024 * 1024  # 12MB
        server.create_test_file(test_filename, test_size)
        
        # Enable slow mode
        server.set_slow_mode(True)
        
        url = f"{base_url}/range/{test_filename}"
        output_path = os.path.join(test_dir, "test_download.dat")
        
        print(f"Starting download: {url}")
        
        # Start download
        downloader = IntegratedMultiDownloader(max_connections=4)
        
        result = [None]
        
        def download_worker():
            result[0] = downloader.download(url=url, destination=output_path)
            
        thread = threading.Thread(target=download_worker)
        thread.start()
        
        # Wait 3 seconds then cancel
        print("Waiting 3 seconds...")
        time.sleep(3)
        
        print("Triggering cancel...")
        downloader.cancel_download()
        
        # Wait for thread to complete
        print("Waiting for download thread...")
        thread.join(timeout=15)
        
        if thread.is_alive():
            print("WARNING: Thread did not complete!")
            return False
            
        # Check result
        if result[0] is not None:
            success, info = result[0]
            print(f"Download result: success={success}")
            print(f"Mode: {info.get('mode', 'unknown')}")
        else:
            print("No result returned")
            
        # Check files
        if os.path.exists(output_path):
            size = os.path.getsize(output_path)
            print(f"Output file size: {size}")
        else:
            print("No output file")
            
        state_file = output_path + ".downloadstate.json"
        if os.path.exists(state_file):
            print("State file exists")
        else:
            print("No state file")
            
        return True
        
    finally:
        server.stop()
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    simple_interruption_test()