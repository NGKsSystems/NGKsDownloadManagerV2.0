#!/usr/bin/env python3
"""
Verification script for NGK Download Manager V2.0 UI fixes
Tests core functionality without starting full UI
"""

import sys
import os
import json
import time

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_logging_setup():
    """Test that logging directory and setup works"""
    print("=== Testing Logging Setup ===")
    
    try:
        from ui_qt.app import setup_ui_logging
        logger = setup_ui_logging()
        logger.info("Test log entry from verification")
        
        log_file = os.path.join(project_root, 'logs', 'ui.log')
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                content = f.read()
            if "Test log entry from verification" in content:
                print("✅ Logging setup: PASS")
                return True
        
        print("❌ Logging setup: FAIL - log not written")
        return False
        
    except Exception as e:
        print(f"❌ Logging setup: FAIL - {e}")
        return False

def test_progress_parsing():
    """Test progress string parsing"""
    print("\n=== Testing Progress Parsing ===")
    
    try:
        from ui_adapter.api import UIAdapter
        
        adapter = UIAdapter()
        
        # Test progress parsing directly
        test_cases = [
            {"progress": "85.5%", "speed": "1.2 MB/s", "filename": "test.mp4"},
            {"percent": 67.3, "speed": "800 KB/s", "filename": "test2.mp4"},
            {"progress": "100%", "speed": "0 B/s", "filename": "completed.mp4"}
        ]
        
        # Create a dummy download to test progress update
        adapter.active_downloads['test'] = {
            'progress': 0.0,
            'speed': '0 B/s',
            'filename': 'test',
            'status': 'Starting'
        }
        
        all_passed = True
        for i, test_data in enumerate(test_cases):
            adapter._update_download_progress('test', test_data)
            dl = adapter.active_downloads['test']
            
            expected_progress = 85.5 if i == 0 else (67.3 if i == 1 else 100.0)
            actual_progress = dl['progress']
            
            if abs(actual_progress - expected_progress) < 0.1:
                print(f"✅ Progress parsing case {i+1}: {actual_progress}% - PASS")
            else:
                print(f"❌ Progress parsing case {i+1}: Expected {expected_progress}%, got {actual_progress}% - FAIL")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"❌ Progress parsing: FAIL - {e}")
        return False

def test_history_schema():
    """Test V1 history schema compliance"""
    print("\n=== Testing History Schema ===")
    
    try:
        from utils import HistoryManager
        
        # Create test history manager
        test_file = "test_history.json"
        hm = HistoryManager(test_file)
        
        # Test V1 schema entry
        test_entry = {
            'url': 'https://youtu.be/test123',
            'filename': 'Test Video',
            'type': 'YouTube',  # V1 uses 'type'
            'destination': '/downloads',
            'status': 'Completed',
            'size': 'Unknown'
        }
        
        success = hm.add_download(test_entry)
        
        if success:
            history = hm.load_history()
            if history and len(history) > 0:
                entry = history[-1]
                
                # Check V1 required fields
                required_fields = ['url', 'filename', 'type', 'destination', 'status', 'size', 'timestamp', 'date']
                missing_fields = [f for f in required_fields if f not in entry]
                
                if not missing_fields:
                    print("✅ History V1 schema: PASS")
                    
                    # Test deduplication
                    hm.add_download(test_entry)  # Add same entry again
                    history2 = hm.load_history()
                    
                    if len(history2) == len(history):
                        print("✅ History deduplication: PASS")
                        result = True
                    else:
                        print(f"❌ History deduplication: FAIL - {len(history)} vs {len(history2)}")
                        result = False
                    
                else:
                    print(f"❌ History V1 schema: FAIL - missing fields: {missing_fields}")
                    result = False
            else:
                print("❌ History V1 schema: FAIL - no entries saved")
                result = False
        else:
            print("❌ History V1 schema: FAIL - could not save entry")
            result = False
        
        # Cleanup
        if os.path.exists(test_file):
            os.remove(test_file)
        
        return result
        
    except Exception as e:
        print(f"❌ History schema: FAIL - {e}")
        return False

def test_ui_adapter():
    """Test UI adapter basic functionality"""
    print("\n=== Testing UI Adapter ===")
    
    try:
        from ui_adapter.api import get_adapter
        
        adapter = get_adapter()
        
        # Test URL validation
        result = adapter.validate_url("https://youtu.be/test123")
        if result['valid'] and result['type'] == 'YouTube':
            print("✅ URL validation: PASS")
        else:
            print(f"❌ URL validation: FAIL - {result}")
            return False
        
        # Test settings
        adapter.set_settings({'test_key': 'test_value'})
        settings = adapter.get_settings()
        if settings.get('test_key') == 'test_value':
            print("✅ Settings management: PASS")
        else:
            print("❌ Settings management: FAIL")
            return False
        
        print("✅ UI Adapter: PASS")
        return True
        
    except Exception as e:
        print(f"❌ UI Adapter: FAIL - {e}")
        return False

def main():
    """Run all verification tests"""
    print("NGK DOWNLOAD MANAGER V2.0 - UI FIX VERIFICATION")
    print("=" * 60)
    
    tests = [
        test_logging_setup,
        test_progress_parsing,
        test_history_schema,
        test_ui_adapter
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY:")
    print("=" * 60)
    
    test_names = [
        "Logging Setup",
        "Progress Parsing",
        "History Schema",
        "UI Adapter"
    ]
    
    all_passed = True
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "PASS" if result else "FAIL"
        print(f"{name:<20}: {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED - UI fixes are working correctly!")
        return 0
    else:
        print("❌ SOME TESTS FAILED - fixes need additional work")
        return 1

if __name__ == "__main__":
    sys.exit(main())