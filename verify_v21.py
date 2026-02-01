"""
V2.1 Verification Suite
Tests the integrated multi-connection download capability
"""

import sys
import tempfile
import os
import time
from download_manager import DownloadManager

def test_non_range_server():
    """Test a server that doesn't support range requests"""
    print("TEST 1: Non-Range Server")
    print("-" * 40)
    
    url = "https://github.com/git/git/archive/refs/heads/master.zip"
    print(f"URL: {url}")
    
    # Enable debug logging for this test
    dm = DownloadManager(enable_multi_connection=True, debug_logging=True)
    
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        print("Starting download...")
        start_time = time.time()
        success = dm.download(url, temp_path)
        end_time = time.time()
        
        if success:
            file_size = os.path.getsize(temp_path)
            download_time = end_time - start_time
            
            print(f"RESULT: SUCCESS")
            print(f"  File size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
            print(f"  Download time: {download_time:.2f}s")
            print(f"  Expected mode: single-connection")
            print(f"  Expected connections: 1")
            
            return True
        else:
            print(f"RESULT: FAILED")
            return False
            
    except Exception as e:
        print(f"RESULT: ERROR - {e}")
        return False
    finally:
        try:
            os.unlink(temp_path)
        except:
            pass

def test_range_server():
    """Test a server that supports range requests"""
    print("\\nTEST 2: Range-Capable Server")
    print("-" * 40)
    
    url = "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.1.tar.xz"
    print(f"URL: {url}")
    
    # Enable debug logging for this test
    dm = DownloadManager(enable_multi_connection=True, max_connections=4, debug_logging=True)
    
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        print("Starting download...")
        start_time = time.time()
        success = dm.download(url, temp_path)
        end_time = time.time()
        
        if success:
            file_size = os.path.getsize(temp_path)
            download_time = end_time - start_time
            
            print(f"RESULT: SUCCESS")
            print(f"  File size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
            print(f"  Download time: {download_time:.2f}s")
            print(f"  Expected mode: multi-connection")
            print(f"  Expected connections: 4")
            
            return True
        else:
            print(f"RESULT: FAILED")
            return False
            
    except Exception as e:
        print(f"RESULT: ERROR - {e}")
        return False
    finally:
        try:
            os.unlink(temp_path)
        except:
            pass

def test_capability_detection():
    """Test the range capability detection"""
    print("\\nTEST 3: Capability Detection")
    print("-" * 40)
    
    dm = DownloadManager(enable_multi_connection=True)
    
    test_urls = [
        ("GitHub (no range)", "https://github.com/git/git/archive/refs/heads/master.zip", False),
        ("Linux Kernel (range)", "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.1.tar.xz", True)
    ]
    
    all_correct = True
    
    for name, url, expected_range in test_urls:
        print(f"Testing {name}...")
        try:
            file_info = dm.get_file_info(url)
            if file_info:
                actual_range = file_info['supports_resume']
                print(f"  Range support: {actual_range} (expected: {expected_range})")
                
                if actual_range == expected_range:
                    print(f"  CORRECT")
                else:
                    print(f"  INCORRECT")
                    all_correct = False
            else:
                print(f"  ERROR: Could not get file info")
                all_correct = False
        except Exception as e:
            print(f"  ERROR: {e}")
            all_correct = False
    
    return all_correct

def main():
    """Run the verification suite"""
    print("NGK's Download Manager V2.1 - Verification Suite")
    print("=" * 60)
    print("This suite verifies the integrated multi-connection capability")
    print()
    
    results = []
    
    # Test 1: Non-range server (should use single connection)
    results.append(("Non-Range Server", test_non_range_server()))
    
    # Test 2: Range server (should use multi-connection)
    results.append(("Range-Capable Server", test_range_server()))
    
    # Test 3: Capability detection
    results.append(("Capability Detection", test_capability_detection()))
    
    # Summary
    print("\\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("SUCCESS: All verification tests passed")
        print("Multi-connection integration verified and working correctly")
        return 0
    else:
        print("FAILURE: Some tests failed")
        print("Integration may have issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())