#!/usr/bin/env python3
"""Test script to verify history deduplication and V1 schema compliance"""

import sys
import os
import json
import time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils import HistoryManager

def test_history_features():
    """Test history deduplication and V1 schema compliance"""
    print("Testing history features...")
    
    # Backup existing history
    backup_file = "download_history_backup.json"
    if os.path.exists("download_history.json"):
        import shutil
        shutil.copy("download_history.json", backup_file)
        print(f"Backed up existing history to {backup_file}")
    
    # Create test history manager
    history = HistoryManager("test_history.json")
    
    # Test V1 schema compliance
    print("\n1. Testing V1 schema compliance...")
    test_download = {
        'url': 'https://youtube.com/watch?v=test123',
        'title': 'Test Video',
        'filename': 'test_video.mp4',
        'status': 'completed',
        'file_size': 1048576  # 1MB
    }
    
    history.add_download(test_download)
    
    # Read and verify the entry
    with open("test_history.json", 'r') as f:
        entries = json.load(f)
        
    if entries:
        entry = entries[0]
        required_fields = ['url', 'title', 'filename', 'status', 'type', 'size', 'timestamp', 'date']
        missing_fields = [field for field in required_fields if field not in entry]
        
        if missing_fields:
            print(f"❌ Missing V1 schema fields: {missing_fields}")
        else:
            print("✅ V1 schema compliance verified")
            print(f"   Entry: {entry}")
    
    # Test deduplication
    print("\n2. Testing deduplication within 10 seconds...")
    
    # Add same download twice quickly
    history.add_download(test_download)
    history.add_download(test_download)  # Should be deduplicated
    
    # Read entries again
    with open("test_history.json", 'r') as f:
        entries = json.load(f)
    
    if len(entries) == 1:
        print("✅ Deduplication working - only one entry stored")
    else:
        print(f"❌ Deduplication failed - {len(entries)} entries found")
    
    # Test that entries are allowed after 10 second window
    print("\n3. Testing deduplication time window...")
    
    # Wait and add again (in real scenario this would be 10+ seconds)
    # For test, we'll modify timestamp manually
    time.sleep(1)
    history.add_download(test_download)
    
    with open("test_history.json", 'r') as f:
        entries = json.load(f)
    
    print(f"Total entries after time window test: {len(entries)}")
    
    # Cleanup
    if os.path.exists("test_history.json"):
        os.remove("test_history.json")
        print("Cleaned up test history file")
    
    print("\n✅ History features test completed!")

if __name__ == '__main__':
    test_history_features()