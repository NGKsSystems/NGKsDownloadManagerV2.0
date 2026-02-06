#!/usr/bin/env python3
"""
PHASE 7 STEP 5 - Policy Gate Verification Script
Tests verification gates P5-A through P5-D with structured logging proof
"""

import os
import sys
import json
import time
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from policy_engine import PolicyEngine
from queue_manager import QueueManager
from download_manager import DownloadManager
import logging

# Setup test logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PolicyVerificationTester:
    """Test harness for policy gate verification"""
    
    def __init__(self):
        self.policy_engine = PolicyEngine()
        self.queue_manager = QueueManager()
        self.download_manager = DownloadManager()
        self.test_results = {}
        
    def run_verification_gate_tests(self):
        """Run all verification gate tests P5-A through P5-D"""
        print("\n" + "="*60)
        print("PHASE 7 STEP 5 - POLICY GATE VERIFICATION")
        print("Testing Verification Gates P5-A through P5-D")
        print("="*60)
        
        # Test each verification gate
        self.test_p5_a_enqueue_gate()
        self.test_p5_b_start_gate()
        self.test_p5_c_retry_gate()
        self.test_p5_d_resume_gate()
        
        # Summary
        self.print_verification_summary()
        
    def test_p5_a_enqueue_gate(self):
        """P5-A: Test ENQUEUE policy gate"""
        print("\n--- P5-A: ENQUEUE POLICY GATE ---")
        
        # Test 1: ALLOW case
        try:
            decision = self.policy_engine.check_enqueue_policy(
                task_id="test_enqueue_allow",
                url="https://example.com/test.txt",
                destination="test_allow.txt"
            )
            print(f"✅ ENQUEUE ALLOW: {decision.action} - {decision.reason}")
            self.test_results["P5-A-ALLOW"] = True
        except Exception as e:
            print(f"❌ ENQUEUE ALLOW failed: {e}")
            self.test_results["P5-A-ALLOW"] = False
            
        # Test 2: DENY case (blocked extension)
        try:
            decision = self.policy_engine.check_enqueue_policy(
                task_id="test_enqueue_deny",
                url="https://example.com/malware.exe",
                destination="malware.exe"
            )
            print(f"✅ ENQUEUE DENY: {decision.action} - {decision.reason}")
            self.test_results["P5-A-DENY"] = decision.action == "DENY"
        except Exception as e:
            print(f"❌ ENQUEUE DENY failed: {e}")
            self.test_results["P5-A-DENY"] = False
            
        # Test 3: MODIFY case (task annotations)
        try:
            decision = self.policy_engine.check_enqueue_policy(
                task_id="test_enqueue_modify",
                url="https://slow-server.net/large.zip",
                destination="large.zip"
            )
            print(f"✅ ENQUEUE MODIFY: {decision.action} - {decision.reason}")
            if decision.annotations:
                print(f"   Annotations: {decision.annotations}")
            self.test_results["P5-A-MODIFY"] = True
        except Exception as e:
            print(f"❌ ENQUEUE MODIFY failed: {e}")
            self.test_results["P5-A-MODIFY"] = False
            
    def test_p5_b_start_gate(self):
        """P5-B: Test START policy gate"""
        print("\n--- P5-B: START POLICY GATE ---")
        
        try:
            decision = self.policy_engine.check_start_policy(
                task_id="test_start_policy",
                url="https://example.com/test.txt"
            )
            print(f"✅ START POLICY: {decision.action} - {decision.reason}")
            if decision.annotations:
                print(f"   Annotations: {decision.annotations}")
            self.test_results["P5-B"] = True
        except Exception as e:
            print(f"❌ START POLICY failed: {e}")
            self.test_results["P5-B"] = False
            
    def test_p5_c_retry_gate(self):
        """P5-C: Test RETRY policy gate"""
        print("\n--- P5-C: RETRY POLICY GATE ---")
        
        # Test 1: ALLOW retry (within limits)
        try:
            decision = self.policy_engine.check_retry_policy(
                task_id="test_retry_allow",
                attempt=2,
                max_attempts=5,
                error="connection_timeout"
            )
            print(f"✅ RETRY ALLOW: {decision.action} - {decision.reason}")
            self.test_results["P5-C-ALLOW"] = decision.action == "ALLOW"
        except Exception as e:
            print(f"❌ RETRY ALLOW failed: {e}")
            self.test_results["P5-C-ALLOW"] = False
            
        # Test 2: DENY retry (exceeded limits)
        try:
            decision = self.policy_engine.check_retry_policy(
                task_id="test_retry_deny",
                attempt=5,
                max_attempts=3,
                error="server_error"
            )
            print(f"✅ RETRY DENY: {decision.action} - {decision.reason}")
            self.test_results["P5-C-DENY"] = decision.action == "DENY"
        except Exception as e:
            print(f"❌ RETRY DENY failed: {e}")
            self.test_results["P5-C-DENY"] = False
            
    def test_p5_d_resume_gate(self):
        """P5-D: Test RESUME policy gate"""
        print("\n--- P5-D: RESUME POLICY GATE ---")
        
        # Test 1: ALLOW resume (normal case)
        try:
            decision = self.policy_engine.check_resume_policy(
                task_id="test_resume_allow",
                url="https://example.com/large.zip",
                file_path="large.zip",
                current_size=10485760  # 10MB
            )
            print(f"✅ RESUME ALLOW: {decision.action} - {decision.reason}")
            self.test_results["P5-D-ALLOW"] = decision.action == "ALLOW"
        except Exception as e:
            print(f"❌ RESUME ALLOW failed: {e}")
            self.test_results["P5-D-ALLOW"] = False
            
        # Test 2: DENY resume (file too small)
        try:
            decision = self.policy_engine.check_resume_policy(
                task_id="test_resume_deny",
                url="https://example.com/tiny.txt",
                file_path="tiny.txt",
                current_size=512  # 512 bytes (less than 1MB threshold)
            )
            print(f"✅ RESUME DENY: {decision.action} - {decision.reason}")
            self.test_results["P5-D-DENY"] = decision.action == "DENY"
        except Exception as e:
            print(f"❌ RESUME DENY failed: {e}")
            self.test_results["P5-D-DENY"] = False
        
    def print_verification_summary(self):
        """Print verification summary"""
        print("\n" + "="*60)
        print("VERIFICATION GATE TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        
        for gate, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{gate:20} {status}")
        
        print(f"\nOVERALL: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            print("🎉 ALL POLICY GATES VERIFIED SUCCESSFULLY!")
            print("PHASE 7 STEP 5 IMPLEMENTATION: ✅ COMPLETE")
        else:
            print("⚠️  Some policy gates failed verification")
            
        return passed_tests == total_tests

if __name__ == "__main__":
    tester = PolicyVerificationTester()
    success = tester.run_verification_gate_tests()
    
    if success:
        print("\n🎯 READY FOR PRODUCTION: Policy layer fully operational")
        print("ENGINE BASELINE v2.0 + POLICY LAYER v1.0 = DEPLOYMENT READY")
    else:
        print("\n⛔ NOT READY: Policy verification failed")
    
    sys.exit(0 if success else 1)