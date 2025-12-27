"""
Debug the progress callback to see what's being sent
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from youtube_downloader import YouTubeDownloader

def debug_progress_callback(progress_info):
    """Debug progress callback to see exactly what's being sent"""
    print(f"DEBUG PROGRESS: {progress_info}")
    print(f"  - Type: {type(progress_info)}")
    print(f"  - Keys: {list(progress_info.keys()) if isinstance(progress_info, dict) else 'Not a dict'}")
    print(f"  - Filename: '{progress_info.get('filename', 'MISSING')}' (length: {len(progress_info.get('filename', ''))})")
    print(f"  - Progress: '{progress_info.get('progress', 'MISSING')}'")
    print(f"  - Speed: '{progress_info.get('speed', 'MISSING')}'")
    print(f"  - Status: '{progress_info.get('status', 'MISSING')}'")
    print("-" * 80)

def test_youtube_progress():
    """Test what progress info is sent by YouTube downloader"""
    print("Testing YouTube downloader progress callbacks...")
    print("=" * 80)
    
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    output_dir = r"C:\Users\suppo\Desktop\NGKsSystems\NGKs DL Manager\downloads"
    
    yt_downloader = YouTubeDownloader()
    
    print(f"URL: {url}")
    print(f"Destination: {output_dir}")
    print("=" * 80)
    
    try:
        # Check if file already exists to avoid re-download
        existing = yt_downloader.check_existing_download(url, output_dir)
        if existing and existing['status'] == 'complete':
            print(f"File already exists: {existing['filename']}")
            print("Testing with a different approach...")
            
            # Get video info to see what filename should be
            info = yt_downloader.get_video_info(url)
            if info:
                print(f"Expected filename from video info: '{info['title']}'")
                
                # Simulate what the progress callback should send
                print("\nSimulating expected progress callback:")
                debug_progress_callback({
                    'filename': info['title'],
                    'progress': '50%',
                    'speed': '1.5 MB/s - ETA: 30s',
                    'status': 'Downloading'
                })
            return
        
        result = yt_downloader.download(url, output_dir, debug_progress_callback)
        print(f"\nFinal result: {result}")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_youtube_progress()