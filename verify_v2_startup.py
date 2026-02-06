"""
Quick V2.0 Unified Pipeline Verification Test
Verify that all Phase 9 integrations are working properly in the running V2.0 instance
"""

def test_v2_unified_pipeline_quick():
    """Quick test to verify unified pipeline is working in running V2.0"""
    try:
        print("🔍 V2.0 UNIFIED PIPELINE VERIFICATION")
        print("=" * 40)
        
        # Test unified executor integration
        from unified_executor import UnifiedDownloadExecutor
        executor = UnifiedDownloadExecutor()
        print("✅ UnifiedDownloadExecutor imported and initialized")
        
        # Test URL detection for all types
        test_urls = {
            "HTTP": "https://example.com/file.zip",
            "YouTube": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "HuggingFace": "https://huggingface.co/gpt2", 
            "Protocol": "ftp://test.example.com/file.txt"
        }
        
        print("\n📋 URL TYPE DETECTION:")
        all_working = True
        for expected_type, url in test_urls.items():
            detected = executor.detect_download_type(url)
            status = "✅" if detected.lower() == expected_type.lower() else "❌"
            print(f"  {expected_type:>11}: {detected:>12} {status}")
            if detected.lower() != expected_type.lower():
                all_working = False
        
        # Test unified task creation
        print("\n🔧 TASK CREATION TEST:")
        try:
            task = executor.create_task_for_url(
                task_id="test_v2_verification",
                url="https://httpbin.org/get",
                destination="downloads/test",
                priority=5
            )
            print(f"✅ Task created: {task.download_type} pipeline")
            print(f"✅ Task ID: {task.task_id}")
            print(f"✅ Engine compatibility: {'TaskState' in str(type(task.state))}")
        except Exception as e:
            print(f"❌ Task creation failed: {e}")
            all_working = False
        
        # Test UI adapter integration
        print("\n🔗 UI ADAPTER INTEGRATION:")
        try:
            from ui_adapter.api import UIAdapter
            adapter = UIAdapter()
            has_unified = hasattr(adapter, 'unified_executor')
            print(f"✅ UI Adapter integration: {has_unified}")
            if not has_unified:
                all_working = False
        except Exception as e:
            print(f"❌ UI Adapter test failed: {e}")
            all_working = False
        
        print("\n" + "=" * 40)
        if all_working:
            print("🎉 V2.0 UNIFIED PIPELINE VERIFIED - ALL SYSTEMS OPERATIONAL")
        else:
            print("⚠️  V2.0 UNIFIED PIPELINE - SOME ISSUES DETECTED")
        print("=" * 40)
        
        return all_working
        
    except Exception as e:
        print(f"❌ V2.0 verification failed: {e}")
        return False

if __name__ == "__main__":
    success = test_v2_unified_pipeline_quick()
    print(f"\n🔍 V2.0 Status: {'OPERATIONAL' if success else 'NEEDS ATTENTION'}")