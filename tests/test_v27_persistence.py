#!/usr/bin/env python3
"""
V2.7 Persistence Tests - Queue state persistence and crash recovery validation
Universal Agent Ruleset: ASCII-only, no placeholders, deterministic only
"""

import os
import tempfile
import time
import json
import shutil
from datetime import datetime
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from queue_manager import QueueManager, TaskState
from queue_persistence import save_queue_state, load_queue_state, apply_crash_recovery_rules, PersistenceError
from local_range_server import LocalRangeServer


class TestPersistence:
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.server = LocalRangeServer()
        self.server_port = self.server.start()
        self.server_dir = self.server.serve_dir
    
    def cleanup(self):
        """Clean up test resources"""
        if self.server:
            self.server.stop()
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def add_test_file(self, filename: str, content: bytes) -> str:
        """Add a test file and return its URL"""
        file_path = os.path.join(self.server_dir, filename)
        with open(file_path, 'wb') as f:
            f.write(content)
        return f"http://127.0.0.1:{self.server_port}/{filename}"
    
    def test_save_load_roundtrip(self):
        """Test A: Save/Load round-trip schema validation (no downloads)"""
        print("Running Test A: Save/Load round-trip schema validation")
        
        # Create queue manager
        state_path = os.path.join(self.temp_dir, "roundtrip_state.json")
        try:
            if os.path.exists(state_path):
                os.remove(state_path)
        except Exception:
            pass

        queue_mgr = QueueManager(max_active_downloads=2, persist_queue=True, queue_state_path=state_path)
        
        # Add various tasks with different states
        test_states = [
            ("task1", TaskState.PENDING),
            ("task2", TaskState.PAUSED),
            ("task3", TaskState.COMPLETED),
            ("task4", TaskState.FAILED),
            ("task5", TaskState.CANCELLED)
        ]
        
        for task_id, state in test_states:
            queue_mgr.enqueue(task_id, f"http://127.0.0.1:{self.server_port}/{task_id}", f"/tmp/{task_id}")
            # Manually set state for testing
            queue_mgr.tasks[task_id].state = state
            if state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
                queue_mgr._add_to_history(queue_mgr.tasks[task_id])
        
        # Save state
        state_path = os.path.join(self.temp_dir, "test_state.json")
        try:
            save_queue_state(queue_mgr, state_path)
        except Exception as e:
            print(f"FAIL: Save failed: {e}")
            return False
        
        # Verify file was created
        if not os.path.exists(state_path):
            print("FAIL: State file was not created")
            return False
        
        # Load state
        try:
            loaded_state = load_queue_state(state_path)
        except Exception as e:
            print(f"FAIL: Load failed: {e}")
            return False
        
        # Validate schema
        required_fields = ["schema_version", "saved_at", "config_snapshot", "tasks"]
        for field in required_fields:
            if field not in loaded_state:
                print(f"FAIL: Missing field {field} in loaded state")
                return False
        
        # Validate tasks
        if len(loaded_state["tasks"]) != 5:
            print(f"FAIL: Expected 5 tasks, got {len(loaded_state['tasks'])}")
            return False
        
        # Validate task states preserved
        task_states = {task["task_id"]: task["state"] for task in loaded_state["tasks"]}
        for task_id, expected_state in test_states:
            if task_states.get(task_id) != expected_state.value:
                print(f"FAIL: Task {task_id} state mismatch. Expected {expected_state.value}, got {task_states.get(task_id)}")
                return False
        
        print("PASS: Save/Load round-trip schema validation")
        return True
    
    def test_crash_recovery_transitions(self):
        """Test B: Crash recovery transition test"""
        print("Running Test B: Crash recovery transition test")
        
        # Create test state with all possible states
        test_states = [
            ("pending_task", TaskState.PENDING),
            ("starting_task", TaskState.STARTING),
            ("downloading_task", TaskState.DOWNLOADING),
            ("paused_task", TaskState.PAUSED),
            ("completed_task", TaskState.COMPLETED)
        ]
        
        state_path = os.path.join(self.temp_dir, "crash_recovery_state.json")
        try:
            if os.path.exists(state_path):
                os.remove(state_path)
        except Exception:
            pass

        queue_mgr = QueueManager(max_active_downloads=2, persist_queue=True, queue_state_path=state_path)
        
        for task_id, state in test_states:
            queue_mgr.enqueue(task_id, f"http://127.0.0.1:{self.server_port}/{task_id}", f"/tmp/{task_id}")
            queue_mgr.tasks[task_id].state = state
            if state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
                queue_mgr._add_to_history(queue_mgr.tasks[task_id])
        
        # Save state
        state_path = os.path.join(self.temp_dir, "crash_state.json")
        save_queue_state(queue_mgr, state_path)
        
        # Load and apply crash recovery
        loaded_state = load_queue_state(state_path)
        recovered_state = apply_crash_recovery_rules(loaded_state)
        
        # Check recovery rules were applied
        task_states = {task["task_id"]: task["state"] for task in recovered_state["tasks"]}
        
        expected_recovered = {
            "pending_task": "PENDING",      # Unchanged
            "starting_task": "PAUSED",      # STARTING -> PAUSED
            "downloading_task": "PAUSED",   # DOWNLOADING -> PAUSED
            "paused_task": "PAUSED",        # Unchanged
            "completed_task": "COMPLETED"   # Unchanged
        }
        
        for task_id, expected_state in expected_recovered.items():
            actual_state = task_states.get(task_id)
            if actual_state != expected_state:
                print(f"FAIL: Task {task_id} recovery rule failed. Expected {expected_state}, got {actual_state}")
                return False
        
        print("PASS: Crash recovery transition test")
        return True
    
    def test_no_duplicate_task_restore(self):
        """Test C: No duplicate task restore"""
        print("Running Test C: No duplicate task restore")

        # Save state
        state_path = os.path.join(self.temp_dir, "duplicate_test.json")
        try:
            if os.path.exists(state_path):
                os.remove(state_path)
        except Exception:
            pass

        queue_mgr = QueueManager(
            max_active_downloads=2,
            persist_queue=True,
            queue_state_path=state_path,
        )
        
        # Add tasks
        task_ids = ["unique1", "unique2", "unique3"]
        for task_id in task_ids:
            queue_mgr.enqueue(task_id, f"http://127.0.0.1:{self.server_port}/{task_id}", f"/tmp/{task_id}")
        
        # Save state
        save_queue_state(queue_mgr, state_path)
        
        # Restore first time
        restored_mgr1 = QueueManager.restore_from_disk(state_path)
        
        # Restore second time from same file
        restored_mgr2 = QueueManager.restore_from_disk(state_path)
        
        # Check both have same tasks, no duplicates
        if len(restored_mgr1.tasks) != len(task_ids):
            print(f"FAIL: First restore has wrong task count. Expected {len(task_ids)}, got {len(restored_mgr1.tasks)}")
            return False
        
        if len(restored_mgr2.tasks) != len(task_ids):
            print(f"FAIL: Second restore has wrong task count. Expected {len(task_ids)}, got {len(restored_mgr2.tasks)}")
            return False
        
        # Check task IDs are unique and match expected
        for task_id in task_ids:
            if task_id not in restored_mgr1.tasks:
                print(f"FAIL: Task {task_id} missing from first restore")
                return False
            if task_id not in restored_mgr2.tasks:
                print(f"FAIL: Task {task_id} missing from second restore")
                return False
        
        print("PASS: No duplicate task restore")
        return True
    
    def test_persistence_with_real_download(self):
        """Test D: Persistence with real download simulation"""
        print("Running Test D: Persistence with real download simulation")
        
        # Create test file
        test_content = b"Test content for persistence validation " * 100  # Make it substantial
        url = self.add_test_file('persist_test.txt', test_content)
        
        # Create queue manager with persistence enabled
        state_path = os.path.join(self.temp_dir, "real_download_state.json")
        queue_mgr = QueueManager(max_active_downloads=1, persist_queue=True, queue_state_path=state_path)
        
        def simple_downloader(url, destination, **kwargs):
            time.sleep(0.1)  # Simulate work
            # Simple download - copy the test content directly
            with open(destination, 'wb') as f:
                f.write(test_content)
            return True
        
        queue_mgr.set_downloader(simple_downloader)
        
        # Enqueue download
        task_id = "persist_download"
        dest_path = os.path.join(self.temp_dir, 'downloaded_file.txt')
        queue_mgr.enqueue(task_id, url, dest_path)
        
        # Check state file was created due to persistence
        if not os.path.exists(state_path):
            print("FAIL: State file was not created during enqueue")
            return False
        
        # Start scheduler and let it complete
        queue_mgr.start_scheduler()
        
        # Wait for completion
        timeout = 5.0
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = queue_mgr.get_status()
            if status['state_counts']['COMPLETED'] == 1:
                break
            time.sleep(0.1)
        
        queue_mgr.stop_scheduler()
        
        # Check if we completed in time
        final_status = queue_mgr.get_status()
        if final_status['state_counts']['COMPLETED'] != 1:
            print(f"FAIL: Download did not complete in time. Status: {final_status}")
            return False
        
        # Verify download completed and file matches
        if not os.path.exists(dest_path):
            print("FAIL: Downloaded file does not exist")
            return False
        
        with open(dest_path, 'rb') as f:
            downloaded_content = f.read()
        
        if downloaded_content != test_content:
            print("FAIL: Downloaded content does not match original")
            return False
        
        # Test restore from persisted state
        try:
            restored_mgr = QueueManager.restore_from_disk(state_path)
            restored_task = restored_mgr.tasks[task_id]
            
            if restored_task.state != TaskState.COMPLETED:
                print(f"FAIL: Restored task state is {restored_task.state}, expected COMPLETED")
                return False
        except Exception as e:
            print(f"FAIL: Failed to restore from persisted state: {e}")
            return False
        
        print("PASS: Persistence with real download simulation")
        return True
    
    def run_all_tests(self):
        """Run all persistence tests"""
        print("V2.7 Persistence Tests - Starting")
        print("=" * 50)
        
        tests = [
            self.test_save_load_roundtrip,
            self.test_crash_recovery_transitions,
            self.test_no_duplicate_task_restore,
            self.test_persistence_with_real_download
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                if test():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"FAIL: {test.__name__} threw exception: {e}")
                failed += 1
            print("-" * 30)
        
        print(f"\nV2.7 Persistence Tests Complete: {passed}/{len(tests)} passed")
        
        if failed == 0:
            print("OVERALL: PASS")
            return True
        else:
            print("OVERALL: FAIL")
            return False


if __name__ == "__main__":
    test_runner = TestPersistence()
    try:
        success = test_runner.run_all_tests()
        sys.exit(0 if success else 1)
    finally:
        test_runner.cleanup()