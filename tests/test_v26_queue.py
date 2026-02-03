#!/usr/bin/env python3
"""
V2.6 Queue Tests - Deterministic queue behavior validation
Reconciled to current architecture for V3.2 compatibility.
Universal Agent Ruleset: ASCII-only, no placeholders, deterministic only
"""

import sys
import os
import time
import threading
import tempfile
import shutil
import hashlib
sys.path.insert(0, os.path.dirname(__file__) + '/..')

from queue_manager import QueueManager, TaskState
from local_range_server import LocalRangeServer
from download_manager import DownloadManager


class TestV26Queue:
    """Test suite for V2.6 queue functionality"""
    
    def __init__(self):
        self.temp_dir = None
        self.server = None
        self.download_manager = None
        self.queue_manager = None
        
    def setup(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.server = LocalRangeServer()
        base_url, serve_dir = self.server.start()
        self.base_url = base_url
        self.serve_dir = serve_dir
        
        # Set up queue manager with download manager
        self.download_manager = DownloadManager()
        self.queue_manager = QueueManager()
        self.queue_manager.set_downloader(self.download_manager.download)
        self.queue_manager.start_scheduler()
        
        time.sleep(0.1)  # Server startup
    
    def add_test_file(self, filename, content):
        """Add a test file to the server"""
        file_path = os.path.join(self.serve_dir, filename)
        if isinstance(content, str):
            content = content.encode()
        with open(file_path, 'wb') as f:
            f.write(content)
        return f"{self.base_url}/{filename}"
        
    def teardown(self):
        """Cleanup test environment"""
        if self.queue_manager:
            self.queue_manager.stop_scheduler()
        if self.server:
            self.server.stop()
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_fifo_ordering(self):
        """Test A: FIFO ordering with same priority"""
        print("Running Test A: FIFO ordering (same priority)")
        
        # Create test files
        test_files = ['file1.txt', 'file2.txt', 'file3.txt']
        file_urls = []
        
        for filename in test_files:
            content = f"Test content for {filename}"
            url = self.add_test_file(filename, content)
            file_urls.append(url)
        
        # Mock downloader that tracks execution order
        execution_order = []
        
        def mock_downloader(url, destination, **kwargs):
            # Extract filename from URL for tracking
            filename = url.split('/')[-1]
            execution_order.append(filename)
            time.sleep(0.1)  # Simulate work
            return True
        
        # Configure queue manager for sequential processing
        self.queue_manager.stop_scheduler()  # Stop default scheduler
        test_queue = QueueManager(max_active_downloads=1)
        test_queue.set_downloader(mock_downloader)
        test_queue.start_scheduler()
        
        # Enqueue all files with same priority (should maintain FIFO order)
        for i, url in enumerate(file_urls):
            test_queue.enqueue(f"task{i}", url, os.path.join(self.temp_dir, test_files[i]), priority=5)
        
        # Wait for completion
        timeout = 5.0
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = test_queue.get_status()
            if status['state_counts']['COMPLETED'] == 3:
                break
            time.sleep(0.1)
        
        test_queue.stop_scheduler()
        
        # Verify FIFO order
        expected_order = ['file1.txt', 'file2.txt', 'file3.txt']
        if execution_order == expected_order:
            print("PASS: FIFO ordering maintained")
            return True
        else:
            print(f"FAIL: Expected {expected_order}, got {execution_order}")
            return False
    
    def test_priority_ordering(self):
        """Test B: Priority ordering with different priorities"""
        print("Running Test B: Priority ordering (different priority)")
        
        # Create test files
        test_files = ['low.txt', 'high.txt', 'medium.txt']
        file_urls = []
        
        for filename in test_files:
            content = f"Test content for {filename}"
            url = self.add_test_file(filename, content)
            file_urls.append(url)
        
        execution_order = []
        
        def mock_downloader(url, destination, **kwargs):
            filename = url.split('/')[-1]
            execution_order.append(filename)
            time.sleep(0.1)
            return True
        
        # Create test queue manager for priority testing
        test_queue = QueueManager(max_active_downloads=1)
        test_queue.set_downloader(mock_downloader)
        test_queue.start_scheduler()
        
        # Enqueue with different priorities (higher number = higher priority)
        test_queue.enqueue("task_low", file_urls[0], os.path.join(self.temp_dir, test_files[0]), priority=1)
        test_queue.enqueue("task_high", file_urls[1], os.path.join(self.temp_dir, test_files[1]), priority=10)
        test_queue.enqueue("task_med", file_urls[2], os.path.join(self.temp_dir, test_files[2]), priority=5)
        
        # Wait for completion
        timeout = 5.0
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = test_queue.get_status()
            if status['state_counts']['COMPLETED'] == 3:
                break
            time.sleep(0.1)
        
        test_queue.stop_scheduler()
        
        # Verify priority order: high (10), medium (5), low (1)
        expected_order = ['high.txt', 'medium.txt', 'low.txt']
        if execution_order == expected_order:
            print("PASS: Priority ordering maintained")
            return True
        else:
            print(f"FAIL: Expected {expected_order}, got {execution_order}")
            return False
    
    def test_concurrency_cap(self):
        """Test C: Concurrency cap with max_active_downloads=2"""
        print("Running Test C: Concurrency cap (max_active_downloads=2)")
        
        # Create 5 test files
        test_files = [f'file{i}.txt' for i in range(1, 6)]
        file_urls = []
        
        for filename in test_files:
            content = f"Test content for {filename}"
            url = self.add_test_file(filename, content)
            file_urls.append(url)
        
        active_count_history = []
        max_concurrent = 0
        
        def mock_downloader(url, destination, **kwargs):
            # Track active count during execution
            current_active = len(test_queue.active_workers)
            active_count_history.append(current_active)
            nonlocal max_concurrent
            max_concurrent = max(max_concurrent, current_active)
            
            time.sleep(0.2)  # Simulate work to ensure overlap
            return True
        
        # Create test queue manager with max_active_downloads=2
        test_queue = QueueManager(max_active_downloads=2)
        test_queue.set_downloader(mock_downloader)
        test_queue.start_scheduler()
        
        # Enqueue all 5 files
        for i, url in enumerate(file_urls):
            test_queue.enqueue(f"task{i}", url, os.path.join(self.temp_dir, test_files[i]))
        
        # Wait for completion
        timeout = 10.0
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = test_queue.get_status()
            current_active = status['active_downloads']
            if current_active > 2:
                print(f"FAIL: Concurrency cap violated - {current_active} active downloads")
                test_queue.stop_scheduler()
                return False
                
            if status['state_counts']['COMPLETED'] == 5:
                break
            time.sleep(0.05)
        
        test_queue.stop_scheduler()
        
        # Verify we never exceeded the limit
        if max_concurrent <= 2:
            print(f"PASS: Concurrency cap maintained (max observed: {max_concurrent})")
            return True
        else:
            print(f"FAIL: Concurrency cap exceeded (max: {max_concurrent})")
            return False
    
    def test_pause_resume_states(self):
        """Test D: Pause/resume state transitions"""
        print("Running Test D: Pause/resume state transitions")
        
        # Create a test task manually
        task_id = "pause_test"
        content = b"Test content for pause/resume test"
        url = self.add_test_file('pausetest.txt', content)
        dest_path = os.path.join(self.temp_dir, 'pausetest.txt')
        
        self.queue_manager.enqueue(task_id, url, dest_path)
        
        # Test 1: Cannot pause PENDING task
        task = self.queue_manager.tasks[task_id]
        task.state = TaskState.PENDING
        paused = self.queue_manager.pause_task(task_id)
        if paused:
            print("FAIL: Should not be able to pause PENDING task")
            return False
        
        # Test 2: Can pause DOWNLOADING task
        task.state = TaskState.DOWNLOADING
        paused = self.queue_manager.pause_task(task_id)
        if not paused:
            print("FAIL: Could not pause DOWNLOADING task")
            return False
            
        # Verify PAUSED state
        if task.state != TaskState.PAUSED:
            print(f"FAIL: Expected PAUSED state, got {task.state}")
            return False
        
        # Test 3: Can resume PAUSED task
        resumed = self.queue_manager.resume_task(task_id)
        if not resumed:
            print("FAIL: Could not resume PAUSED task")
            return False
            
        # Verify PENDING state (resume transitions PAUSED -> PENDING)
        if task.state != TaskState.PENDING:
            print(f"FAIL: Expected PENDING state after resume, got {task.state}")
            return False
        
        print("PASS: Pause/resume state transitions")
        return True
    
    def test_cancel_semantics(self):
        """Test E: Cancel semantics - no completion fallback"""
        print("Running Test E: Cancel semantics")
        
        # Create test file
        content = b"Test content for cancel test"
        url = self.add_test_file('canceltest.txt', content)
        
        download_started = threading.Event()
        cancel_detected = threading.Event()
        
        def cancellable_downloader(url, destination, cancel_event=None, **kwargs):
            download_started.set()
            # Simulate work while checking for cancellation
            for i in range(50):
                if cancel_event and cancel_event.is_set():
                    cancel_detected.set()
                    return False  # Cancelled
                time.sleep(0.01)
            
            # If we get here, download would succeed
            with open(destination, 'wb') as f:
                f.write(content)
            return True
        
        # Create test queue manager for cancel testing
        test_queue = QueueManager(max_active_downloads=1)
        test_queue.set_downloader(cancellable_downloader)
        test_queue.start_scheduler()
        
        # Enqueue download
        task_id = "cancel_test"
        dest_path = os.path.join(self.temp_dir, 'canceltest.txt')
        test_queue.enqueue(task_id, url, dest_path)
        
        # Wait for download to start
        download_started.wait(timeout=2.0)
        time.sleep(0.1)  # Let it get to DOWNLOADING state
        
        # Cancel the task
        cancelled = test_queue.cancel_task(task_id)
        if not cancelled:
            print("FAIL: Could not cancel task")
            test_queue.stop_scheduler()
            return False
        
        # Wait for cancellation to be processed
        cancel_detected.wait(timeout=2.0)
        
        # Give some time for state updates
        time.sleep(0.2)
        
        # Verify final state is CANCELLED (not COMPLETED)
        task = test_queue.tasks[task_id]
        if task.state == TaskState.CANCELLED:
            # Verify no file was created (no fallback completion)
            if not os.path.exists(dest_path):
                print("PASS: Cancel semantics - task cancelled, no fallback completion")
                test_queue.stop_scheduler()
                return True
            else:
                print("FAIL: File exists after cancel - fallback completion occurred")
        else:
            print(f"FAIL: Expected CANCELLED state, got {task.state}")
        
        test_queue.stop_scheduler()
        return False
    
    def run_all_tests(self):
        """Run all tests and return overall result"""
        print("V2.6 Queue Tests - Starting")
        print("=" * 50)
        
        try:
            self.setup()
            
            tests = [
                self.test_fifo_ordering,
                self.test_priority_ordering,
                self.test_concurrency_cap,
                self.test_pause_resume_states,
                self.test_cancel_semantics
            ]
            
            results = []
            for test in tests:
                try:
                    result = test()
                    results.append(result)
                except Exception as e:
                    print(f"ERROR in {test.__name__}: {e}")
                    results.append(False)
                
                print("-" * 30)
        
        finally:
            self.teardown()
        
        passed = sum(results)
        total = len(results)
        
        print(f"\nV2.6 Queue Tests Complete: {passed}/{total} passed")
        
        if passed == total:
            print("OVERALL: PASS")
            return True
        else:
            print("OVERALL: FAIL")
            return False


if __name__ == "__main__":
    tester = TestV26Queue()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)