"""
Simple test of verified multi-connection downloader
"""

from verified_multi_downloader import MultiConnectionDownloader
import tempfile
import os

def test_real_multi_connection():
    """Test with a server that supports range requests"""
    downloader = MultiConnectionDownloader(max_connections=4)
    url = 'https://github.com/git/git/archive/refs/heads/master.zip'
    
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        print("Testing multi-connection with GitHub URL...")
        success, info = downloader.download_file(url, temp_path)
        
        if success:
            print("SUCCESS!")
            print(f"  File size: {info['file_size']:,} bytes")
            print(f"  Download time: {info['download_time']:.2f}s")
            print(f"  Connections used: {info['connections_used']}")
            print(f"  Mode: {info['mode']}")
            speed_mbps = info['file_size'] / info['download_time'] / 1024 / 1024
            print(f"  Speed: {speed_mbps:.2f} MB/s")
            
            if info['connections_used'] > 1:
                print("  ✅ Multi-connection download successful!")
            else:
                print("  ⚠️ Fell back to single connection")
        else:
            print("FAILED to download")
            
    except Exception as e:
        print(f"ERROR: {e}")
        
    finally:
        try:
            os.unlink(temp_path)
        except:
            pass

if __name__ == "__main__":
    test_real_multi_connection()