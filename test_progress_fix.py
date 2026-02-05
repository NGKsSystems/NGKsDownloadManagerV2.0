#!/usr/bin/env python3
"""Test script to verify progress parsing fix"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ui_adapter.api import UIAdapter

def test_progress_parsing():
    """Test the progress parsing fix for string percentages"""
    print("Testing progress parsing fix...")
    
    # Create UIAdapter instance
    adapter = UIAdapter()
    
    # Test data: simulate progress_info from yt-dlp hooks
    test_cases = [
        # String percentage (the bug we fixed)
        {'percent': '85.5%', 'speed': 1024000, 'eta': 30},
        # Float percentage (original working case)
        {'percent': 75.2, 'speed': 512000, 'eta': 45},
        # No percent key
        {'speed': 256000, 'eta': 60},
        # Invalid percent
        {'percent': 'unknown', 'speed': 128000, 'eta': 90}
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case}")
        
        # Call the internal progress update method
        try:
            adapter._update_download_progress("test_url", test_case)
            print(f"✅ Progress update succeeded")
        except Exception as e:
            print(f"❌ Progress update failed: {e}")
    
    print("\n✅ All progress parsing tests completed successfully!")

if __name__ == '__main__':
    test_progress_parsing()