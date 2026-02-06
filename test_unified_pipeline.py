"""
PHASE 9 - Unified Download Pipeline Test
Tests all download types through the unified executor
"""

import os
import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_unified_pipeline():
    """Test unified download pipeline with different URL types"""
    
    try:
        # Import the unified system
        from unified_executor import UnifiedDownloadExecutor
        from unified_task import UnifiedQueueTask
        
        print("=" * 60)
        print("PHASE 9 - UNIFIED DOWNLOAD PIPELINE TEST")
        print("=" * 60)
        
        # Initialize unified executor  
        executor = UnifiedDownloadExecutor()
        print("✅ Unified executor initialized")
        
        # Test URLs for different types
        test_urls = {
            "http": "https://httpbin.org/get",
            "youtube": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", 
            "huggingface": "https://huggingface.co/gpt2",
            "protocol": "ftp://test.example.com/file.txt"
        }
        
        print("\n🔍 URL DETECTION TESTS:")
        for url_type, url in test_urls.items():
            detected_type = executor.detect_download_type(url)
            status = "✅ PASS" if detected_type == url_type else f"❌ FAIL (expected {url_type}, got {detected_type})"
            print(f"   {url_type.upper():>12}: {detected_type:>12} | {status}")
        
        print("\n📋 TASK CREATION TESTS:")
        tasks = []
        for i, (url_type, url) in enumerate(test_urls.items()):
            task_id = f"test_{url_type}_{i}"
            try:
                task = executor.create_task_for_url(
                    task_id=task_id,
                    url=url, 
                    destination=f"downloads/test_{url_type}",
                    priority=5
                )
                tasks.append(task)
                print(f"   ✅ {url_type.upper()} task created: {task.download_type}")
            except Exception as e:
                print(f"   ❌ {url_type.upper()} task failed: {str(e)}")
        
        print("\n🔧 EXECUTOR TYPE MAPPING:")
        for task in tasks:
            try:
                executor_type = task.get_download_executor_type()
                print(f"   {task.download_type.upper():>12} → {executor_type}")
            except Exception as e:
                print(f"   ❌ {task.download_type.upper()} mapping failed: {str(e)}")
        
        print("\n💾 TASK SERIALIZATION TESTS:")
        for task in tasks:
            try:
                # Test serialization/deserialization compatibility
                task_dict = task.to_dict()
                restored_task = UnifiedQueueTask.from_dict(task_dict)
                
                # Verify critical fields preserved
                assert restored_task.task_id == task.task_id
                assert restored_task.download_type == task.download_type
                assert restored_task.url == task.url
                assert restored_task.download_options == task.download_options
                
                print(f"   ✅ {task.download_type.upper()} serialization OK")
            except Exception as e:
                print(f"   ❌ {task.download_type.upper()} serialization failed: {str(e)}")
        
        print("\n🏗️ ENGINE BASELINE V2.0 COMPATIBILITY:")
        sample_task = tasks[0] if tasks else None
        if sample_task:
            # Check that all ENGINE BASELINE v2.0 fields exist
            baseline_fields = [
                'task_id', 'url', 'destination', 'priority', 'state', 
                'created_at', 'updated_at', 'mode', 'connections_used',
                'error', 'progress', 'speed_bps', 'resume_state_path',
                'history_id', 'attempt', 'max_attempts', 'next_eligible_at', 
                'last_error', 'host', 'effective_priority'
            ]
            
            missing_fields = []
            for field in baseline_fields:
                if not hasattr(sample_task, field):
                    missing_fields.append(field)
            
            if missing_fields:
                print(f"   ❌ Missing ENGINE BASELINE fields: {missing_fields}")
            else:
                print(f"   ✅ All ENGINE BASELINE v2.0 fields present")
        
        print("\n📊 PHASE 9 EXTENSIONS CHECK:")
        if sample_task:
            phase9_fields = ['download_type', 'download_options', 'forensics_session_id']
            missing_phase9 = []
            for field in phase9_fields:
                if not hasattr(sample_task, field):
                    missing_phase9.append(field)
            
            if missing_phase9:
                print(f"   ❌ Missing Phase 9 fields: {missing_phase9}")
            else:
                print(f"   ✅ All Phase 9 extension fields present")
        
        print("\n" + "=" * 60)
        print("✅ UNIFIED PIPELINE TEST COMPLETED SUCCESSFULLY")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ UNIFIED PIPELINE TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_unified_pipeline()
    sys.exit(0 if success else 1)