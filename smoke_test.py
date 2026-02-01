"""
Quick smoke test for patches
"""

import sys

def test_imports():
    """Test basic imports"""
    try:
        from integrated_multi_downloader import IntegratedMultiDownloader
        print("✓ IntegratedMultiDownloader import")
        
        from http_range_detector import supports_http_range
        print("✓ supports_http_range import")
        
        from download_manager import DownloadManager
        print("✓ DownloadManager import")
        
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_probe():
    """Test probe functionality"""
    try:
        from http_range_detector import supports_http_range
        
        # Quick test with httpbin (expect False)
        print("Testing probe with httpbin...")
        result, info = supports_http_range("https://httpbin.org/bytes/1024", timeout=5)
        print(f"✓ Probe completed: result={result}, reason={info['reason']}")
        
        return True
    except Exception as e:
        print(f"✗ Probe test failed: {e}")
        return False

def main():
    print("Smoke Test for V2.1 Patches")
    print("-" * 30)
    
    if not test_imports():
        return 1
        
    if not test_probe():
        return 1
    
    print("\n✓ All smoke tests passed")
    return 0

if __name__ == "__main__":
    sys.exit(main())