"""
Test actual Hugging Face download with enhanced progress display
"""

import sys
import os
import time

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from huggingface_downloader import HuggingFaceDownloader

def progress_callback(progress_info):
    """Enhanced progress callback for testing"""
    print(f"\r{progress_info['filename']} | {progress_info['progress']} | {progress_info['speed']}", end="", flush=True)

def test_hf_download():
    """Test actual HF download with progress display"""
    # Try a larger file to see progress tracking
    url = "https://huggingface.co/microsoft/DialoGPT-medium/resolve/main/pytorch_model.bin"
    output_dir = r"C:\Users\suppo\Desktop\NGKsSystems\NGKs DL Manager\downloads"
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    print("Testing Hugging Face download with enhanced progress...")
    print(f"URL: {url}")
    print(f"Output: {output_dir}")
    print("-" * 80)
    
    hf_downloader = HuggingFaceDownloader()
    
    try:
        result = hf_downloader.download(url, output_dir, progress_callback)
        print(f"\n\nDownload Result: {result}")
        
        # Check if file was downloaded
        if result["status"] == "success":
            filepath = result["filepath"]
            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath)
                print(f"File downloaded successfully!")
                print(f"Location: {filepath}")
                print(f"Size: {hf_downloader._format_size(file_size)}")
            else:
                print("File not found after download")
        else:
            print(f"Download failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"\nError during download: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_hf_download()