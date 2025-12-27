"""
Test YouTube downloader result format
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from youtube_downloader import YouTubeDownloader

def test_result_format():
    """Test that YouTube downloader returns proper result format"""
    print("Testing YouTube downloader result format...")
    
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    output_dir = r"C:\Users\suppo\Desktop\NGKsSystems\NGKs DL Manager\downloads"
    
    yt_downloader = YouTubeDownloader()
    
    # Test get_video_info first
    print(f"Getting video info for: {url}")
    info = yt_downloader.get_video_info(url)
    
    if info:
        print(f"✅ Video info retrieved successfully")
        print(f"   Title: {info['title']}")
        print(f"   Uploader: {info['uploader']}")
        print(f"   Duration: {info['duration']} seconds")
        print(f"   Available formats: {len(info['formats'])}")
    else:
        print("❌ Failed to get video info")
        return
    
    # Test download return format without actually downloading
    def mock_progress(progress_info):
        print(f"Progress: {progress_info}")
    
    print(f"\nTesting download method return format...")
    print(f"URL: {url}")
    print(f"Destination: {output_dir}")
    
    # Check if file already exists to skip actual download
    existing = yt_downloader.check_existing_download(url, output_dir)
    if existing:
        print(f"✅ Found existing download: {existing}")
        print(f"   Status: {existing['status']}")
        print(f"   Filename: {existing['filename']}")
        if existing['status'] == 'complete':
            print("   Skipping download test (file already exists)")
            return
    
    try:
        result = yt_downloader.download(url, output_dir, mock_progress)
        print(f"\n✅ Download method returned: {type(result)}")
        print(f"   Result: {result}")
        
        if isinstance(result, dict):
            print(f"   ✅ Correct dictionary format")
            print(f"   Status: {result.get('status')}")
            print(f"   Filename: {result.get('filename')}")
            print(f"   Filepath: {result.get('filepath')}")
            print(f"   Resumed: {result.get('resumed')}")
        else:
            print(f"   ❌ Unexpected format: {type(result)}")
            
    except Exception as e:
        print(f"❌ Error during download test: {e}")

if __name__ == "__main__":
    test_result_format()