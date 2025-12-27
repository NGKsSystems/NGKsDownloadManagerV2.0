"""
Test YouTube downloader with enhanced features
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from youtube_downloader import YouTubeDownloader

def progress_callback(progress_info):
    """Enhanced progress callback for testing"""
    print(f"\r{progress_info['filename']} | {progress_info['progress']} | {progress_info['speed']} | {progress_info['status']}", end="", flush=True)

def test_youtube_download():
    """Test YouTube download with progress display"""
    # Test with a short video
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll - short and reliable
    output_dir = r"C:\Users\suppo\Desktop\NGKsSystems\NGKs DL Manager\downloads"
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    print("Testing YouTube download with enhanced progress...")
    print(f"URL: {url}")
    print(f"Output: {output_dir}")
    print("-" * 80)
    
    yt_downloader = YouTubeDownloader()
    
    try:
        # Check for existing download first
        existing = yt_downloader.check_existing_download(url, output_dir)
        if existing:
            print(f"\nExisting download found: {existing}")
        
        result = yt_downloader.download(url, output_dir, progress_callback)
        print(f"\n\nDownload Result: {result}")
        
        # Check if file was downloaded
        if result["status"] == "success":
            print(f"Download completed successfully!")
            if result.get("resumed"):
                print("Download was resumed from previous attempt")
            else:
                print("Fresh download completed")
        else:
            print(f"Download failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"\nError during download: {e}")
        import traceback
        traceback.print_exc()

def test_video_info():
    """Test video info extraction"""
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    print("\nTesting video info extraction...")
    print("-" * 40)
    
    yt_downloader = YouTubeDownloader()
    
    try:
        info = yt_downloader.get_video_info(url)
        if info:
            print(f"Title: {info['title']}")
            print(f"Uploader: {info['uploader']}")
            print(f"Duration: {info['duration']} seconds")
            print(f"View count: {info['view_count']:,}")
            print(f"Available formats: {len(info['formats'])}")
        else:
            print("Failed to get video info")
    except Exception as e:
        print(f"Error getting video info: {e}")

if __name__ == "__main__":
    test_video_info()
    print("\n" + "="*80 + "\n")
    test_youtube_download()