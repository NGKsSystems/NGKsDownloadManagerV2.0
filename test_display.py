"""
Test enhanced progress display for Hugging Face downloads
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from huggingface_downloader import HuggingFaceDownloader

def test_progress_display(progress_info):
    """Test enhanced progress display"""
    print(f"Filename: {progress_info['filename']}")
    print(f"Progress: {progress_info['progress']}")
    print(f"Speed: {progress_info['speed']}")
    print(f"Status: {progress_info['status']}")
    print("-" * 60)

def test_display_formats():
    """Test the display formatting functions"""
    hf_downloader = HuggingFaceDownloader()
    
    print("Testing Format Functions:")
    print("=" * 50)
    
    # Test size formatting
    sizes = [1024, 1048576, 1073741824, 3740000000]  # 1KB, 1MB, 1GB, ~3.7GB
    for size in sizes:
        formatted = hf_downloader._format_size(size)
        print(f"Size {size:,} bytes = {formatted}")
    
    print()
    
    # Test time formatting
    times = [30, 90, 3600, 7200, 10800]  # 30s, 1.5m, 1h, 2h, 3h
    for time_sec in times:
        formatted = hf_downloader._format_time(time_sec)
        print(f"Time {time_sec} seconds = {formatted}")
    
    print()
    
    # Test speed formatting
    speeds = [512000, 1048576, 5242880]  # 500KB/s, 1MB/s, 5MB/s
    for speed in speeds:
        formatted = hf_downloader._format_speed(speed)
        print(f"Speed {speed} bytes/s = {formatted}")
    
    print("\n" + "=" * 50)
    
    # Simulate progress display
    print("Simulating Enhanced Progress Display:")
    print("-" * 50)
    
    # Simulate different progress states
    filename = "fine_2.pt"
    total_size = 3740000000  # ~3.7GB
    
    # Progress stages
    stages = [
        (100000000, 500000),    # 100MB at 500KB/s
        (500000000, 750000),    # 500MB at 750KB/s  
        (1500000000, 1000000),  # 1.5GB at 1MB/s
        (total_size, 0)         # Complete
    ]
    
    for downloaded, speed in stages:
        if downloaded < total_size:
            progress_pct = (downloaded / total_size) * 100
            if speed > 0:
                remaining = total_size - downloaded
                eta = remaining / speed
                eta_str = hf_downloader._format_time(eta)
            else:
                eta_str = "Unknown"
            
            filename_display = f"{filename} ({hf_downloader._format_size(downloaded)}/{hf_downloader._format_size(total_size)})"
            speed_display = f"{hf_downloader._format_speed(speed)} - ETA: {eta_str}"
            
            test_progress_display({
                'filename': filename_display,
                'progress': f"{progress_pct:.1f}%", 
                'speed': speed_display,
                'status': 'Downloading'
            })
        else:
            # Final state
            filename_display = f"{filename} ({hf_downloader._format_size(total_size)})"
            test_progress_display({
                'filename': filename_display,
                'progress': "100%",
                'speed': "0 B/s", 
                'status': 'Downloaded'
            })

if __name__ == "__main__":
    test_display_formats()