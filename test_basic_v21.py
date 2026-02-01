#!/usr/bin/env python3
"""
DEPRECATED: Use test_v21_acceptance.py instead
Quick V2.1 Basic Test
Basic test of multi-connection download functionality.
"""

import os
import sys
import time
import threading
import tempfile
import shutil

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from integrated_multi_downloader import IntegratedMultiDownloader
from local_range_server import LocalRangeServer


def basic_test():
    """Test basic multi-connection download"""
    print("Download Manager V2.1 Basic Test")
    print("=" * 40)
    
    # Create temporary test directory
    test_dir = tempfile.mkdtemp(prefix="v21_basic_test_")
    
    try:
        # Start local HTTP server
        server = LocalRangeServer(port=0)
        server.start()
        
        port = server.actual_port
        base_url = f"http://localhost:{port}"
        print(f"Test server started at {base_url}")
        
        # Create test file (10MB - above the multi-connection threshold)
        test_filename = "test_basic.dat"
        test_size = 10 * 1024 * 1024  # 10MB
        server.create_test_file(test_filename, test_size)
        print(f"Created test file: {test_filename} ({test_size:,} bytes)")
        
        # Download with multi-connection
        downloader = IntegratedMultiDownloader(max_connections=4)
        url = f"{base_url}/{test_filename}"
        output_path = os.path.join(test_dir, "downloaded.dat")
        
        print(f"\nDownloading {url}")
        print("Using 4 connections...")
        
        start_time = time.time()
        success, info = downloader.download(url=url, destination=output_path)
        end_time = time.time()
        
        # Check results
        if success:
            downloaded_size = os.path.getsize(output_path)
            download_time = end_time - start_time
            
            print(f"✓ Download completed in {download_time:.2f}s")
            print(f"✓ Downloaded {downloaded_size:,} bytes")
            print(f"✓ Mode: {info.get('mode', 'unknown')}")
            print(f"✓ Connections used: {info.get('connections_used', 0)}")
            
            # Verify size
            if downloaded_size == test_size:
                print("✓ File size matches original")
                
                # Verify hash
                original_hash = server.get_file_hash(test_filename)
                
                import hashlib
                sha256_hash = hashlib.sha256()
                with open(output_path, "rb") as f:
                    for byte_block in iter(lambda: f.read(4096), b""):
                        sha256_hash.update(byte_block)
                downloaded_hash = sha256_hash.hexdigest()
                
                if original_hash == downloaded_hash:
                    print("✓ File hash matches original")
                    print("\n🎉 BASIC TEST PASSED!")
                    return True
                else:
                    print("❌ Hash mismatch")
            else:
                print(f"❌ Size mismatch: {downloaded_size} != {test_size}")
        else:
            print("❌ Download failed")
            
        print("\n❌ BASIC TEST FAILED")
        return False
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False
        
    finally:
        # Cleanup
        try:
            if 'server' in locals():
                server.stop()
        except:
            pass
            
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    success = basic_test()
    sys.exit(0 if success else 1)