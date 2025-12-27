"""
Simple test of the YouTube downloader to check for errors
"""

import os
from youtube_downloader import YouTubeDownloader

def simple_test():
    print("Testing simplified YouTube download...")
    
    downloader = YouTubeDownloader()
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    output_dir = r"C:\Users\suppo\Desktop\NGKsSystems\NGKs DL Manager\downloads"
    
    # Ensure directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    def progress_callback(info):
        print(f"Progress: {info}")
    
    try:
        # Test simple download
        print("Testing simple download...")
        result = downloader.download(url, output_dir, progress_callback, auto_quality=True)
        print(f"Result: {result}")
        
        # Test format download
        print("\nTesting format download...")
        result2 = downloader.download_with_format(url, output_dir, "best[height<=720]", progress_callback)
        print(f"Result2: {result2}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    simple_test()