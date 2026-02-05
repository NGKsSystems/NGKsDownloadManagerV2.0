"""
Simple test to verify UI download progress functionality
"""

import sys
import os
import time

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ui_adapter.api import get_adapter

def test_download_progress():
    """Test downloading a YouTube video to verify progress"""
    
    adapter = get_adapter()
    
    test_url = "https://youtu.be/dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up (short video)
    destination = os.path.expanduser("~/Downloads")
    
    print("Starting test download...")
    print(f"URL: {test_url}")
    print(f"Destination: {destination}")
    
    download_id = adapter.start_download(test_url, destination)
    print(f"Download ID: {download_id}")
    
    # Monitor progress for 60 seconds
    for i in range(60):
        active = adapter.list_active()
        if active:
            download = active[0]
            print(f"Progress: {download['progress']} | Speed: {download['speed']} | Status: {download['status']}")
            
            if download['status'] in ['Completed', 'Failed']:
                break
        else:
            print("No active downloads")
            break
        
        time.sleep(1)
    
    # Check final status
    print("\nFinal active downloads:")
    active = adapter.list_active()
    for dl in active:
        print(f"  {dl['download_id']}: {dl['filename']} - {dl['status']} - {dl['progress']}")
    
    print("\nRecent history entries:")
    history = adapter.get_history()
    for entry in history[-3:]:
        print(f"  {entry.get('filename', 'Unknown')} - {entry.get('status', 'Unknown')} - {entry.get('type', 'Unknown')}")

if __name__ == "__main__":
    test_download_progress()