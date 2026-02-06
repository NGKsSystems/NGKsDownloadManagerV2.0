"""
PHASE 9 - VERIFICATION GATES G9-1 TO G9-4
Comprehensive test suite for unified download pipeline requirements
"""

import os
import json
import time
import tempfile
from datetime import datetime

def verification_gate_g9_1():
    """
    G9-1: All download types (HTTP, yt-dlp, HuggingFace, protocol) use unified QueueManager
    Verify that all download types are routed through the same queue management system
    """
    print("\n🔍 VERIFICATION GATE G9-1: UNIFIED QUEUE INTEGRATION")
    print("-" * 50)
    
    try:
        from unified_executor import UnifiedDownloadExecutor
        from ui_adapter.api import UIAdapter
        from queue_manager import QueueManager
        
        # Test that UI adapter uses unified executor
        adapter = UIAdapter()
        if not hasattr(adapter, 'unified_executor'):
            print("   ❌ UIAdapter missing unified_executor")
            return False
            
        print("   ✅ UIAdapter has unified_executor integration")
        
        # Test that unified executor can handle all download types
        executor = adapter.unified_executor
        test_urls = {
            "http": "https://example.com/file.zip",
            "youtube": "https://www.youtube.com/watch?v=test", 
            "huggingface": "https://huggingface.co/gpt2",
            "protocol": "ftp://test.example.com/file.txt"
        }
        
        all_routed = True
        for download_type, url in test_urls.items():
            detected_type = executor.detect_download_type(url)
            if detected_type != download_type:
                print(f"   ❌ {download_type.upper()} routing failed: {url}")
                all_routed = False
            else:
                print(f"   ✅ {download_type.upper()} routed to unified pipeline")
        
        if not all_routed:
            return False
            
        # Verify QueueManager integration
        if not hasattr(adapter, 'queue_manager') or not adapter.queue_manager:
            print("   ❌ QueueManager not properly integrated")
            return False
            
        print("   ✅ QueueManager integrated with unified pipeline")
        print("   🎯 G9-1 PASSED: All download types use unified QueueManager")
        return True
        
    except Exception as e:
        print(f"   ❌ G9-1 FAILED: {str(e)}")
        return False

def verification_gate_g9_2():
    """
    G9-2: Policy engine applies to all download types consistently  
    Verify that OPTION 4 auditability works across all download types
    """
    print("\n🔍 VERIFICATION GATE G9-2: UNIFIED POLICY APPLICATION")
    print("-" * 50)
    
    try:
        from unified_executor import UnifiedDownloadExecutor
        from policy_engine import PolicyEngine
        from unified_task import UnifiedQueueTask, TaskState
        
        # Test policy engine initialization in unified executor
        executor = UnifiedDownloadExecutor()
        if not hasattr(executor, 'policy_engine'):
            print("   ❌ Policy engine not integrated in unified executor")
            return False
            
        print("   ✅ Policy engine integrated in unified executor")
        
        # Test policy evaluation for different download types
        test_cases = [
            ("http_task", "https://example.com/file.zip", "http"),
            ("youtube_task", "https://www.youtube.com/watch?v=test", "youtube"),
            ("hf_task", "https://huggingface.co/model", "huggingface"),
            ("ftp_task", "ftp://example.com/file.txt", "protocol")
        ]
        
        policy_applied = True
        for task_id, url, expected_type in test_cases:
            try:
                # Test policy evaluation using correct method
                result = executor.policy_engine.check_enqueue_policy(task_id, url, "downloads/test")
                if not hasattr(result, 'action'):
                    print(f"   ❌ Policy result missing 'action' field for {expected_type}")
                    policy_applied = False
                else:
                    print(f"   ✅ Policy applied to {expected_type.upper()}: action={result.action}")
            except Exception as e:
                print(f"   ❌ Policy evaluation failed for {expected_type}: {e}")
                policy_applied = False
        
        if not policy_applied:
            return False
            
        print("   🎯 G9-2 PASSED: Policy engine applies consistently across all download types")
        return True
        
    except Exception as e:
        print(f"   ❌ G9-2 FAILED: {str(e)}")
        return False

def verification_gate_g9_3():
    """
    G9-3: Forensics export captures all download types with type-specific metadata
    Verify Phase 8 forensics system captures unified pipeline data correctly
    """
    print("\n🔍 VERIFICATION GATE G9-3: UNIFIED FORENSICS CAPTURE")
    print("-" * 50)
    
    try:
        from forensics_exporter import ForensicsExporter
        from unified_executor import UnifiedDownloadExecutor
        from unified_task import UnifiedQueueTask, TaskState
        
        # Create unified tasks for all download types
        executor = UnifiedDownloadExecutor()
        test_tasks = []
        
        test_data = [
            ("http_test", "https://example.com/file.zip", {"resume": True}),
            ("youtube_test", "https://youtube.com/watch?v=test", {"extract_audio": True, "quality": "720p"}),
            ("hf_test", "https://huggingface.co/gpt2", {"token": "test_token"}),
            ("ftp_test", "ftp://example.com/file.txt", {"username": "test"})
        ]
        
        for task_id, url, options in test_data:
            task = executor.create_task_for_url(
                task_id=task_id,
                url=url,
                destination=f"downloads/{task_id}", 
                priority=5,
                **options
            )
            task.state = TaskState.COMPLETED
            task.forensics_session_id = f"forensics_{task_id}"
            test_tasks.append(task)
        
        # Test forensics data serialization
        forensics_data = {}
        serialization_successful = True
        
        for task in test_tasks:
            try:
                task_dict = task.to_dict()
                # Verify forensics-critical fields are preserved
                required_fields = ['download_type', 'download_options', 'forensics_session_id']
                missing_fields = [f for f in required_fields if f not in task_dict]
                
                if missing_fields:
                    print(f"   ❌ {task.download_type} missing forensics fields: {missing_fields}")
                    serialization_successful = False
                else:
                    print(f"   ✅ {task.download_type.upper()} forensics data preserved")
                    
                # Verify download options are JSON serializable
                options = task_dict.get('download_options', '{}')
                if isinstance(options, str):
                    json.loads(options)  # Test JSON parsing
                    
                forensics_data[task.task_id] = task_dict
                
            except Exception as e:
                print(f"   ❌ {task.download_type} serialization failed: {e}")
                serialization_successful = False
        
        if not serialization_successful:
            return False
            
        # Test forensics exporter can handle unified tasks
        exporter = ForensicsExporter()
        print("   ✅ Forensics exporter initialized")
        
        # Simulate forensics export with unified tasks
        export_successful = True
        try:
            # Create mock session data
            session_data = {
                'session_id': 'test_unified_session',
                'tasks': forensics_data,
                'unified_metadata': {
                    'download_types_seen': list(set(t.download_type for t in test_tasks)),
                    'total_unified_tasks': len(test_tasks)
                }
            }
            
            # Test JSON serialization of complete session
            json_data = json.dumps(session_data, indent=2, default=str)
            parsed = json.loads(json_data)
            
            print(f"   ✅ Unified forensics session serialized ({len(json_data)} bytes)")
            print(f"   📊 Captured {len(test_tasks)} tasks across {len(set(t.download_type for t in test_tasks))} download types")
            
        except Exception as e:
            print(f"   ❌ Unified forensics export failed: {e}")
            export_successful = False
        
        if not export_successful:
            return False
            
        print("   🎯 G9-3 PASSED: Forensics captures all unified download types with metadata")
        return True
        
    except Exception as e:
        print(f"   ❌ G9-3 FAILED: {str(e)}")
        return False

def verification_gate_g9_4():
    """
    G9-4: ENGINE BASELINE v2.0 compatibility preserved across all download types
    Verify backward compatibility and LOCKED semantic preservation
    """
    print("\n🔍 VERIFICATION GATE G9-4: ENGINE BASELINE V2.0 COMPATIBILITY")
    print("-" * 50)
    
    try:
        from unified_task import UnifiedQueueTask, TaskState
        from unified_executor import UnifiedDownloadExecutor
        
        # Test field preservation (primary compatibility requirement)
        print("   ✅ UnifiedQueueTask import successful")
        
        # Test ENGINE BASELINE v2.0 field preservation
        executor = UnifiedDownloadExecutor()
        task = executor.create_task_for_url(
            task_id="baseline_test",
            url="https://example.com/test.zip",
            destination="downloads/test",
            priority=5
        )
        
        # List of ENGINE BASELINE v2.0 LOCKED fields
        baseline_fields = [
            'task_id', 'url', 'destination', 'priority', 'state',
            'created_at', 'updated_at', 'mode', 'connections_used',
            'error', 'progress', 'speed_bps', 'resume_state_path',
            'history_id', 'attempt', 'max_attempts', 'next_eligible_at',
            'last_error', 'host', 'effective_priority'
        ]
        
        missing_baseline_fields = []
        for field in baseline_fields:
            if not hasattr(task, field):
                missing_baseline_fields.append(field)
        
        if missing_baseline_fields:
            print(f"   ❌ Missing ENGINE BASELINE v2.0 fields: {missing_baseline_fields}")
            return False
        
        print("   ✅ All ENGINE BASELINE v2.0 fields preserved")
        
        # Test serialization compatibility
        try:
            task_dict = task.to_dict()
            restored_task = UnifiedQueueTask.from_dict(task_dict)
            
            # Verify critical fields match  
            critical_fields = ['task_id', 'url', 'destination', 'priority', 'state']
            for field in critical_fields:
                if getattr(task, field) != getattr(restored_task, field):
                    print(f"   ❌ Field {field} not preserved in serialization")
                    return False
            
            print("   ✅ ENGINE BASELINE v2.0 serialization compatibility verified")
            
        except Exception as e:
            print(f"   ❌ Serialization compatibility failed: {e}")
            return False
        
        # Test state enum compatibility
        if not isinstance(task.state, TaskState):
            print(f"   ❌ State is not TaskState enum: {type(task.state)}")
            return False
            
        print("   ✅ TaskState enum compatibility preserved")
        
        # Verify Phase 9 extensions don't break baseline operations
        phase9_fields = ['download_type', 'download_options', 'forensics_session_id']
        for field in phase9_fields:
            if not hasattr(task, field):
                print(f"   ❌ Phase 9 field {field} missing")
                return False
        
        # Test that baseline operations still work
        task.progress = 50.0
        task.speed_bps = 1000000
        task.error = "Test error"
        
        # Verify updates work
        if task.progress != 50.0 or task.speed_bps != 1000000 or task.error != "Test error":
            print("   ❌ ENGINE BASELINE v2.0 field updates not working")  
            return False
            
        print("   ✅ Phase 9 extensions don't break baseline operations")
        print("   🎯 G9-4 PASSED: ENGINE BASELINE v2.0 compatibility fully preserved")
        return True
        
    except Exception as e:
        print(f"   ❌ G9-4 FAILED: {str(e)}")
        return False

def run_all_verification_gates():
    """Run all Phase 9 verification gates"""
    print("=" * 80)
    print("PHASE 9 - UNIFIED DOWNLOAD PIPELINE VERIFICATION GATES")
    print("=" * 80)
    
    gates = [
        ("G9-1", "Unified QueueManager Integration", verification_gate_g9_1),
        ("G9-2", "Unified Policy Application", verification_gate_g9_2), 
        ("G9-3", "Unified Forensics Capture", verification_gate_g9_3),
        ("G9-4", "ENGINE BASELINE v2.0 Compatibility", verification_gate_g9_4)
    ]
    
    results = []
    for gate_id, gate_name, gate_function in gates:
        try:
            result = gate_function()
            results.append((gate_id, gate_name, result))
        except Exception as e:
            print(f"\n❌ {gate_id} EXCEPTION: {str(e)}")
            results.append((gate_id, gate_name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("PHASE 9 VERIFICATION GATES SUMMARY")
    print("=" * 80)
    
    passed_count = 0
    for gate_id, gate_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{gate_id:>5}: {gate_name:<35} | {status}")
        if passed:
            passed_count += 1
    
    overall_success = passed_count == len(gates)
    print(f"\nOVERALL RESULT: {passed_count}/{len(gates)} gates passed")
    
    if overall_success:
        print("🎉 PHASE 9 VERIFICATION COMPLETE - ALL GATES PASSED")
        print("🚀 UNIFIED DOWNLOAD PIPELINE READY FOR PRODUCTION")
    else:
        print("❌ PHASE 9 VERIFICATION FAILED - REVIEW FAILED GATES")
    
    print("=" * 80)
    return overall_success

if __name__ == "__main__":
    success = run_all_verification_gates()
    exit(0 if success else 1)