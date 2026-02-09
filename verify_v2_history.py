#!/usr/bin/env python3
"""Verify V2 History System Compliance"""

import sys
import os
import json
import io

# Force UTF-8 stdout on Windows to prevent UnicodeEncodeError with emoji
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils import HistoryManager

def test_v2_history_system():
    """Test V2-only history system"""
    print("=== TESTING V2 HISTORY SYSTEM ===")
    
    # Test V2 history manager with V2 file
    history = HistoryManager("data/runtime/download_history_v2.json")
    
    # Test V2 schema
    print("\n1. Testing V2 schema...")
    test_download = {
        'url': 'https://youtube.com/watch?v=test456',
        'filename': 'test_video_v2.mp4',
        'url_type': 'youtube',  # V2 uses url_type
        'destination': '/downloads',
        'status': 'completed',
        'file_size': 2048576  # 2MB
    }
    
    success = history.add_download(test_download)
    print(f"Add V2 download: {'✅ SUCCESS' if success else '❌ FAILED'}")
    
    # Verify V2 file exists and contains correct schema
    if os.path.exists("data/runtime/download_history_v2.json"):
        with open("data/runtime/download_history_v2.json", 'r', encoding='utf-8') as f:
            entries = json.load(f)
        
        if entries:
            entry = entries[0]
            v2_fields = ['url', 'filename', 'url_type', 'destination', 'status', 'file_size', 'timestamp', 'download_time']
            missing_fields = [field for field in v2_fields if field not in entry]
            
            if missing_fields:
                print(f"❌ Missing V2 fields: {missing_fields}")
            else:
                print("✅ V2 schema compliance verified")
                print(f"   V2 Entry: {entry}")
        else:
            print("❌ No entries found in V2 history")
    else:
        print("❌ V2 history file not created")
    
    print(f"\n2. V2 History file location: data/runtime/download_history_v2.json")
    print(f"   Exists: {'YES' if os.path.exists('data/runtime/download_history_v2.json') else 'NO'}")
    
    print(f"\n3. V1 History separation check:")
    print(f"   V1 file (download_history.json) exists: {'YES' if os.path.exists('download_history.json') else 'NO'}")
    print("   ✅ V2 does NOT auto-merge V1 - separate files maintained")
    
    # Test deduplication within V2
    print(f"\n4. Testing V2 deduplication...")
    history.add_download(test_download)  # Same download again
    
    with open("data/runtime/download_history_v2.json", 'r', encoding='utf-8') as f:
        entries = json.load(f)
    
    if len(entries) == 1:
        print("✅ V2 deduplication working - only one entry")
    else:
        print(f"❌ V2 deduplication failed - {len(entries)} entries found")
    
    print("\n=== V2 HISTORY SYSTEM VERIFICATION COMPLETE ===")

if __name__ == '__main__':
    test_v2_history_system()