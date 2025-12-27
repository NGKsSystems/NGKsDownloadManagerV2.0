"""
Test YouTube downloader with comprehensive logging
"""

import os
import sys
from youtube_downloader import YouTubeDownloader

def detailed_progress_callback(progress_info):
    print(f"PROGRESS CALLBACK: {progress_info}")
    
    # Check what fields are available
    print(f"  Keys: {list(progress_info.keys())}")
    for key, value in progress_info.items():
        print(f"    {key}: {repr(value)}")

def test_youtube_download():
    print("Testing YouTube downloader with detailed logging...")
    
    downloader = YouTubeDownloader()
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll
    output_dir = r"C:\Users\suppo\Desktop\NGKsSystems\NGKs DL Manager\downloads"
    
    print(f"URL: {url}")
    print(f"Output dir: {output_dir}")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        result = downloader.download(url, output_dir, detailed_progress_callback)
        print(f"\nFINAL RESULT: {result}")
        print(f"Result type: {type(result)}")
        
        if isinstance(result, dict):
            print("Result is a dictionary:")
            for key, value in result.items():
                print(f"  {key}: {repr(value)}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_youtube_download()