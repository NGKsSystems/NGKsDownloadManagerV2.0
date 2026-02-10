#!/usr/bin/env python3
"""
V2.8 Execution Policy Tests - Retry/backoff, fairness, per-host caps validation
Universal Agent Ruleset: ASCII-only, no placeholders, deterministic only
"""

import os
import tempfile
import time
import shutil
from datetime import datetime, timedelta
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from queue_manager import QueueManager, TaskState
from local_range_server import LocalRangeServer

# F6: whitelist loopback for test-local servers (policy now uses hostname, not netloc)
_LOOPBACK = {'localhost', '127.0.0.1', '::1'}
try:
    from policy_engine import get_policy_engine as _get_pe
    _pe = _get_pe()
    _orig_denylist_v28 = list(_pe.policies.get('per_host', {}).get('denylist', []))
    _pe.policies.setdefault('per_host', {})['denylist'] = [
        h for h in _orig_denylist_v28 if h not in _LOOPBACK
    ]
except Exception:
    _pe = None
    _orig_denylist_v28 = None


class TestExecutionPolicy:
    
    def setup_method(self):
        """Set up test environment for each test method"""
        self.temp_dir = tempfile.mkdtemp()
        self.server = LocalRangeServer()
        self.server_port = self.server.start()
        self.server_dir = self.server.serve_dir
        self.failure_count = {}  # Track failure counts per task
    
    def teardown_method(self):
        """Clean up test resources after each test method"""
        if hasattr(self, 'server') and self.server:
            self.server.stop()
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def add_test_file(self, filename: str, content: bytes) -> str:
        """Add a test file and return its URL"""
        file_path = os.path.join(self.server_dir, filename)
        with open(file_path, 'wb') as f:
            f.write(content)
        return f"http://127.0.0.1:{self.server_port}/{filename}"
    
    def failing_downloader(self, url, destination, **kwargs):
        """Downloader that fails deterministically"""
        task_id = kwargs.get('task_id', 'unknown')
        self.failure_count[task_id] = self.failure_count.get(task_id, 0) + 1
        
        # Fail first 2 attempts, succeed on 3rd
        if self.failure_count[task_id] <= 2:
            raise ConnectionError("Temporary network error")
        
        # Success - create the file
        with open(destination, 'wb') as f:
            f.write(b"Downloaded successfully")
        return True
    
    def timeout_downloader(self, url, destination, **kwargs):
        """Downloader that always times out"""
        raise TimeoutError("Connection timeout")
    
    def success_downloader(self, url, destination, **kwargs):
        """Downloader that always succeeds"""
        time.sleep(0.01)  # Simulate work
        with open(destination, 'wb') as f:
            f.write(b"Success")
        return True
    
    def test_retry_backoff(self):
        """Test A: Retry/backoff functionality"""
        print("Running Test A: Retry/backoff functionality")
        
        # Create queue manager with retry enabled
        queue_mgr = QueueManager(
            max_active_downloads=1,
            retry_enabled=True,
            retry_max_attempts=3,
            retry_backoff_base_s=0.1,  # Short delays for testing
            retry_backoff_max_s=1.0,
            retry_jitter_mode="none"
        )
        
        queue_mgr.set_downloader(self.failing_downloader)
        
        # Enqueue task that will fail twice then succeed
        task_id = "retry_test"
        url = self.add_test_file('retry_file.txt', b"test content")
        dest = os.path.join(self.temp_dir, 'retry_output.txt')
        
        queue_mgr.enqueue(task_id, url, dest)
        
        # Start scheduler
        queue_mgr.start_scheduler()
        
        # Wait for completion (should retry and eventually succeed)
        timeout = 10.0
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            task = queue_mgr.tasks[task_id]
            if task.state in [TaskState.COMPLETED, TaskState.FAILED]:
                break
            time.sleep(0.1)
        
        queue_mgr.stop_scheduler()
        
        # Verify task completed successfully after retries
        task = queue_mgr.tasks[task_id]
        if task.state != TaskState.COMPLETED:
            print(f"FAIL: Task state is {task.state}, expected COMPLETED")
            return False
        
        if task.attempt != 3:
            print(f"FAIL: Task attempt count is {task.attempt}, expected 3")
            return False
        
        if not os.path.exists(dest):
            print("FAIL: Output file was not created")
            return False
        
        print("PASS: Retry/backoff functionality")
        return True
    
    def test_max_attempts(self):
        """Test B: Max attempts enforcement"""
        print("Running Test B: Max attempts enforcement")
        
        # Create queue manager with retry but limited attempts
        queue_mgr = QueueManager(
            max_active_downloads=1,
            retry_enabled=True,
            retry_max_attempts=2,  # Only 2 attempts
            retry_backoff_base_s=0.05,
            retry_backoff_max_s=0.5
        )
        
        queue_mgr.set_downloader(self.timeout_downloader)  # Always fails
        
        # Enqueue task that will always fail
        task_id = "max_attempts_test"
        url = self.add_test_file('timeout_file.txt', b"test content")
        dest = os.path.join(self.temp_dir, 'timeout_output.txt')
        
        queue_mgr.enqueue(task_id, url, dest)
        
        # Start scheduler
        queue_mgr.start_scheduler()
        
        # Wait for final failure
        timeout = 5.0
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            task = queue_mgr.tasks[task_id]
            if task.state in [TaskState.COMPLETED, TaskState.FAILED]:
                break
            time.sleep(0.1)
        
        queue_mgr.stop_scheduler()
        
        # Verify task failed after max attempts
        task = queue_mgr.tasks[task_id]
        if task.state != TaskState.FAILED:
            print(f"FAIL: Task state is {task.state}, expected FAILED")
            return False
        
        if task.attempt != 2:
            print(f"FAIL: Task attempt count is {task.attempt}, expected 2")
            return False
        
        print("PASS: Max attempts enforcement")
        return True
    
    def test_priority_aging(self):
        """Test C: Priority aging functionality"""
        print("Running Test C: Priority aging functionality")
        
        # Create queue manager with priority aging enabled
        queue_mgr = QueueManager(
            max_active_downloads=1,
            priority_aging_enabled=True,
            priority_aging_step=2,
            priority_aging_interval_s=0.1  # Short interval for testing
        )
        
        queue_mgr.set_downloader(self.success_downloader)
        
        # Create test files
        url1 = self.add_test_file('aging1.txt', b"content1")
        url2 = self.add_test_file('aging2.txt', b"content2")
        
        # Enqueue low priority task first
        queue_mgr.enqueue("low_priority", url1, os.path.join(self.temp_dir, 'low.txt'), priority=1)
        
        # Wait a bit for aging
        time.sleep(0.15)
        
        # Enqueue high priority task
        queue_mgr.enqueue("high_priority", url2, os.path.join(self.temp_dir, 'high.txt'), priority=5)
        
        # Check effective priorities after aging
        queue_mgr._update_priority_aging()
        
        low_task = queue_mgr.tasks["low_priority"]
        high_task = queue_mgr.tasks["high_priority"]
        
        # Low priority task should have aged up
        if low_task.effective_priority <= low_task.priority:
            print(f"FAIL: Low priority task did not age. Original: {low_task.priority}, Effective: {low_task.effective_priority}")
            return False
        
        # High priority task should be unchanged (no aging time)
        if high_task.effective_priority != high_task.priority:
            print(f"FAIL: High priority task aged when it shouldn't. Original: {high_task.priority}, Effective: {high_task.effective_priority}")
            return False
        
        print("PASS: Priority aging functionality")
        return True
    
    def test_per_host_cap(self):
        """Test D: Per-host caps enforcement"""
        print("Running Test D: Per-host caps enforcement")
        
        # Create queue manager with per-host limits
        queue_mgr = QueueManager(
            max_active_downloads=4,  # High global limit
            per_host_enabled=True,
            per_host_max_active=1    # Only 1 per host
        )
        
        # Use a slow downloader to keep tasks active
        def slow_downloader(url, destination, **kwargs):
            time.sleep(0.2)
            with open(destination, 'wb') as f:
                f.write(b"Slow download")
            return True
        
        queue_mgr.set_downloader(slow_downloader)
        
        # Enqueue multiple tasks for same host
        same_host_urls = [
            f"http://same-host.com/file{i}.txt" 
            for i in range(3)
        ]
        
        for i, url in enumerate(same_host_urls):
            queue_mgr.enqueue(f"task_same_{i}", url, os.path.join(self.temp_dir, f'same_{i}.txt'))
        
        # Enqueue tasks for different host
        diff_host_url = "http://different-host.com/file.txt"
        queue_mgr.enqueue("task_diff", diff_host_url, os.path.join(self.temp_dir, 'diff.txt'))
        
        # Start scheduler
        queue_mgr.start_scheduler()
        
        # Let tasks start
        time.sleep(0.1)
        
        # Check per-host counts
        host_counts = queue_mgr._get_active_count_by_host()
        
        # Should have max 1 active per host
        same_host_active = host_counts.get("same-host.com", 0)
        diff_host_active = host_counts.get("different-host.com", 0)
        
        queue_mgr.stop_scheduler()
        
        if same_host_active > 1:
            print(f"FAIL: Same host has {same_host_active} active downloads, expected max 1")
            return False
        
        if diff_host_active > 1:
            print(f"FAIL: Different host has {diff_host_active} active downloads, expected max 1")
            return False
        
        print("PASS: Per-host caps enforcement")
        return True
    
    def test_mixed_host_scheduling(self):
        """Test E: Mixed-host scheduling fairness"""
        print("Running Test E: Mixed-host scheduling fairness")
        
        # Create queue manager with per-host limits but higher global limit
        queue_mgr = QueueManager(
            max_active_downloads=3,
            per_host_enabled=True,
            per_host_max_active=1
        )
        
        execution_order = []
        
        def tracking_downloader(url, destination, **kwargs):
            from urllib.parse import urlparse
            host = urlparse(url).netloc
            execution_order.append(host)
            time.sleep(0.05)  # Short delay
            with open(destination, 'wb') as f:
                f.write(b"Mixed host test")
            return True
        
        queue_mgr.set_downloader(tracking_downloader)
        
        # Enqueue tasks for different hosts with same priority
        hosts = ["host1.com", "host2.com", "host3.com"]
        for i, host in enumerate(hosts):
            url = f"http://{host}/file.txt"
            queue_mgr.enqueue(f"task_{i}", url, os.path.join(self.temp_dir, f'mixed_{i}.txt'), priority=5)
        
        # Start scheduler
        queue_mgr.start_scheduler()
        
        # Wait for completion
        timeout = 3.0
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            completed = sum(1 for t in queue_mgr.tasks.values() if t.state == TaskState.COMPLETED)
            if completed == 3:
                break
            time.sleep(0.1)
        
        queue_mgr.stop_scheduler()
        
        # Verify all tasks completed
        completed_count = sum(1 for t in queue_mgr.tasks.values() if t.state == TaskState.COMPLETED)
        if completed_count != 3:
            print(f"FAIL: Only {completed_count} of 3 tasks completed")
            return False
        
        # Verify fair scheduling (all hosts should have executed)
        if len(set(execution_order)) != 3:
            print(f"FAIL: Not all hosts executed. Order: {execution_order}")
            return False
        
        print("PASS: Mixed-host scheduling fairness")
        return True


def test_execution_policy_suite():
    """Main test function for running all execution policy tests"""
    print("V2.8 Execution Policy Tests - Starting")
    print("=" * 50)
    
    # Create test instance manually for main runner
    test_instance = TestExecutionPolicy()
    test_instance.setup_method()
    
    tests = [
        test_instance.test_retry_backoff,
        test_instance.test_max_attempts,
        test_instance.test_priority_aging,
        test_instance.test_per_host_cap,
        test_instance.test_mixed_host_scheduling
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
    
    test_instance.teardown_method()
    
    print(f"\nV2.8 Execution Policy Tests Complete: {passed}/{len(tests)} passed")
    
    if failed == 0:
        print("OVERALL: PASS")
        return True
    else:
        print("OVERALL: FAIL")
        return False


def _restore_denylist():
    if _pe is not None and _orig_denylist_v28 is not None:
        _pe.policies['per_host']['denylist'] = _orig_denylist_v28


if __name__ == "__main__":
    try:
        success = test_execution_policy_suite()
        sys.exit(0 if success else 1)
    finally:
        _restore_denylist()