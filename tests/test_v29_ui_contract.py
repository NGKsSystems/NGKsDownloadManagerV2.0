#!/usr/bin/env python3
"""
V2.9 UI Contract Tests - Event bus and snapshot validation
Universal Agent Ruleset: ASCII-only, no placeholders, deterministic only
"""

import os
import tempfile
import time
import json
import threading
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from queue_manager import QueueManager
from event_bus import EventBus
from ui_contract import validate_snapshot, build_task_snapshot


class TestUIContract:
    
    def __init__(self):
        self.events_received = []
        self.event_lock = threading.Lock()
    
    def event_callback(self, event_type: str, payload: dict):
        """Callback to capture events"""
        with self.event_lock:
            self.events_received.append({
                'type': event_type,
                'payload': payload.copy()
            })
    
    def test_snapshot_schema_completeness(self):
        """Test A: Snapshot schema completeness (validate_snapshot does not raise)"""
        print("Running Test A: Snapshot schema completeness")
        
        # Create queue manager
        event_bus = EventBus()
        queue_mgr = QueueManager(max_active_downloads=1, event_bus=event_bus)
        
        # Create a test downloader that doesn't actually download
        def stub_downloader(url, destination, **kwargs):
            return True
        
        queue_mgr.set_downloader(stub_downloader)
        
        # Enqueue a task
        task_id = "test_task"
        queue_mgr.enqueue(task_id, "http://127.0.0.1:19999/test", "/tmp/test")
        
        # Get task snapshot
        try:
            snapshot = queue_mgr.get_task_snapshot(task_id)
            
            # Validate snapshot does not raise
            validate_snapshot(snapshot)
            
            print("PASS: Snapshot schema completeness validation")
            return True
            
        except Exception as e:
            print(f"FAIL: Snapshot validation failed: {e}")
            return False
    
    def test_event_emission_counts(self):
        """Test B: Event emission counts (enqueue emits TASK_ADDED, updates emit TASK_UPDATED)"""
        print("Running Test B: Event emission counts")
        
        # Create event bus and subscribe
        event_bus = EventBus()
        token = event_bus.subscribe(self.event_callback)
        
        # Create queue manager with event bus
        queue_mgr = QueueManager(max_active_downloads=1, event_bus=event_bus)
        
        # Create stub downloader
        def stub_downloader(url, destination, **kwargs):
            # Simulate some progress updates
            task = queue_mgr.tasks.get("test_task")
            if task:
                task.progress = 25.0
                queue_mgr._emit_task_event("TASK_UPDATED", "test_task")
                time.sleep(0.1)
                task.progress = 50.0
                queue_mgr._emit_task_event("TASK_UPDATED", "test_task")
                time.sleep(0.1)
                task.progress = 100.0
            return True
        
        queue_mgr.set_downloader(stub_downloader)
        
        # Clear events and enqueue
        with self.event_lock:
            self.events_received.clear()
        
        # Enqueue task
        task_id = "test_task"
        queue_mgr.enqueue(task_id, "http://127.0.0.1:19999/test", "/tmp/test")
        
        # Start scheduler to process task
        queue_mgr.start_scheduler()
        
        # Wait for completion
        timeout = 5.0
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = queue_mgr.get_status()
            if status['state_counts'].get('COMPLETED', 0) >= 1:
                break
            time.sleep(0.1)
        
        queue_mgr.stop_scheduler()
        event_bus.unsubscribe(token)
        
        # Analyze events
        with self.event_lock:
            events = self.events_received.copy()
        
        # Count event types
        task_added_count = len([e for e in events if e['type'] == 'TASK_ADDED'])
        task_updated_count = len([e for e in events if e['type'] == 'TASK_UPDATED'])
        queue_status_count = len([e for e in events if e['type'] == 'QUEUE_STATUS'])
        
        # Validate counts
        if task_added_count != 1:
            print(f"FAIL: Expected 1 TASK_ADDED event, got {task_added_count}")
            return False
        
        if task_updated_count < 2:  # Should have at least progress updates + completion
            print(f"FAIL: Expected at least 2 TASK_UPDATED events, got {task_updated_count}")
            return False
        
        if queue_status_count < 1:  # Should have at least completion status
            print(f"FAIL: Expected at least 1 QUEUE_STATUS event, got {queue_status_count}")
            return False
        
        print(f"PASS: Event emission counts - ADDED:{task_added_count}, UPDATED:{task_updated_count}, STATUS:{queue_status_count}")
        return True
    
    def test_payloads_ascii_safe(self):
        """Test C: Payloads are ASCII-safe"""
        print("Running Test C: Payloads are ASCII-safe")
        
        # Create event bus and subscribe
        event_bus = EventBus()
        token = event_bus.subscribe(self.event_callback)
        
        # Create queue manager
        queue_mgr = QueueManager(max_active_downloads=1, event_bus=event_bus)
        
        # Clear events
        with self.event_lock:
            self.events_received.clear()
        
        # Enqueue task with various characters (should be ASCII-safe)
        task_id = "ascii_test"
        url = "http://127.0.0.1:19999/test_file.txt"  # ASCII-safe URL
        dest = "/tmp/test_file.txt"  # ASCII-safe destination
        
        queue_mgr.enqueue(task_id, url, dest)
        
        # Get events
        with self.event_lock:
            events = self.events_received.copy()
        
        event_bus.unsubscribe(token)
        
        # Test each event payload for ASCII safety
        for event in events:
            try:
                # Convert to JSON to test serialization
                json_str = json.dumps(event['payload'])
                
                # Ensure all characters are ASCII
                json_str.encode('ascii')
                
                # Validate snapshot
                validate_snapshot(event['payload'])
                
            except UnicodeEncodeError:
                print(f"FAIL: Event payload contains non-ASCII characters: {event}")
                return False
            except Exception as e:
                print(f"FAIL: Event payload validation failed: {e}")
                return False
        
        if not events:
            print("FAIL: No events received")
            return False
        
        print("PASS: All event payloads are ASCII-safe")
        return True
    
    def test_event_bus_thread_safety(self):
        """Test D: Event bus thread safety"""
        print("Running Test D: Event bus thread safety")
        
        event_bus = EventBus()
        received_events = []
        lock = threading.Lock()
        
        def callback(event_type, payload):
            with lock:
                received_events.append((event_type, payload))
        
        # Subscribe from multiple threads
        tokens = []
        def subscribe_worker():
            token = event_bus.subscribe(callback)
            tokens.append(token)
        
        threads = []
        for i in range(5):
            thread = threading.Thread(target=subscribe_worker)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Emit events from multiple threads
        def emit_worker(worker_id):
            for i in range(10):
                event_bus.emit(f"TEST_EVENT_{worker_id}", {"data": i})
        
        emit_threads = []
        for i in range(3):
            thread = threading.Thread(target=emit_worker, args=(i,))
            emit_threads.append(thread)
            thread.start()
        
        for thread in emit_threads:
            thread.join()
        
        # Check results
        expected_events = 3 * 10 * len(tokens)  # 3 workers * 10 events * subscriber count
        actual_events = len(received_events)
        
        if actual_events != expected_events:
            print(f"FAIL: Expected {expected_events} events, got {actual_events}")
            return False
        
        # Cleanup
        for token in tokens:
            event_bus.unsubscribe(token)
        
        print("PASS: Event bus thread safety validated")
        return True
    
    def run_all_tests(self):
        """Run all UI contract tests"""
        print("V2.9 UI Contract Tests - Starting")
        print("=" * 50)
        
        tests = [
            self.test_snapshot_schema_completeness,
            self.test_event_emission_counts,
            self.test_payloads_ascii_safe,
            self.test_event_bus_thread_safety
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
        
        print(f"\nV2.9 UI Contract Tests Complete: {passed}/{len(tests)} passed")
        
        if failed == 0:
            print("OVERALL: PASS")
            return True
        else:
            print("OVERALL: FAIL")
            return False


if __name__ == "__main__":
    test_runner = TestUIContract()
    success = test_runner.run_all_tests()
    sys.exit(0 if success else 1)