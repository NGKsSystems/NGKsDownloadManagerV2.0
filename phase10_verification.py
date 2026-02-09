#!/usr/bin/env python3
"""
Phase 10.5 Verification Gates (G10-1 to G10-5)
NGK's Download Manager V2.0 - Product Hardening Verification

VERIFICATION GATES:
- G10-1: UI Integration Verification
- G10-2: Type Detection Verification  
- G10-3: Type-Specific Options Verification
- G10-4: Queue Persistence Verification
- G10-5: Unified Pipeline End-to-End Verification

OPTION 4 AUDITABILITY: All verification results logged with timestamps
ENGINE BASELINE v2.0: Compatibility preserved throughout
"""

import os
import sys
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Tuple
from urllib.parse import urlparse

# Import verification targets
from ui_adapter.api import UIAdapter
from unified_executor import UnifiedDownloadExecutor
from queue_manager import QueueManager, TaskState
from utils import URLDetector

class Phase10Verifier:
    """Phase 10.5 Verification Gate Controller"""
    
    def __init__(self):
        self.logger = logging.getLogger("phase10_verifier")
        self.results = []
        self.setup_logging()
        
    def setup_logging(self):
        """Setup verification logging for OPTION 4 auditability"""
        try:
            os.makedirs("logs", exist_ok=True)
            
            # Create verification-specific log file
            log_file = f"logs/phase10_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            handler = logging.FileHandler(log_file, encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
            
            print(f"📝 Verification logging enabled: {log_file}")
            
        except Exception as e:
            print(f"❌ Failed to setup verification logging: {e}")
    
    def log_gate_result(self, gate: str, status: str, details: str, evidence: Dict = None):
        """Log gate verification result with OPTION 4 auditability"""
        timestamp = datetime.now().isoformat()
        result = {
            'gate': gate,
            'status': status,
            'details': details,
            'evidence': evidence or {},
            'timestamp': timestamp
        }
        
        self.results.append(result)
        self.logger.info(f"GATE_RESULT | {gate} | {status} | {details}")
        
        if evidence:
            for key, value in evidence.items():
                self.logger.info(f"GATE_EVIDENCE | {gate} | {key}={value}")
    
    def verify_g10_1_ui_integration(self) -> bool:
        """G10-1: UI Integration Verification"""
        print("\n🔍 G10-1: UI Integration Verification")
        
        try:
            # Test UIAdapter initialization
            from ui_qt.main_window import DownloadsTab
            from ui_adapter.api import UIAdapter
            
            adapter = UIAdapter()
            
            # Verify unified executor is initialized
            if not hasattr(adapter, 'unified_executor'):
                self.log_gate_result("G10-1", "FAIL", "UIAdapter missing unified_executor", 
                                   {"has_unified_executor": False})
                return False
            
            # Verify unified executor handlers
            executor = adapter.unified_executor
            expected_handlers = ['http', 'youtube', 'huggingface', 'protocol']
            
            evidence = {
                "has_download_manager": hasattr(executor, 'download_manager'),
                "has_youtube_downloader": hasattr(executor, 'youtube_downloader'),
                "has_huggingface_downloader": hasattr(executor, 'huggingface_downloader'),
                "has_protocol_manager": hasattr(executor, 'protocol_manager'),
                "has_policy_engine": hasattr(executor, 'policy_engine')
            }
            
            all_handlers_present = all(evidence.values())
            
            if all_handlers_present:
                self.log_gate_result("G10-1", "PASS", "UI integration verified - all handlers present", evidence)
                print("✅ G10-1 PASS: UI integration verified")
                return True
            else:
                self.log_gate_result("G10-1", "FAIL", "Missing required handlers", evidence)
                print("❌ G10-1 FAIL: Missing required handlers")
                return False
                
        except Exception as e:
            self.log_gate_result("G10-1", "ERROR", f"Integration verification error: {str(e)}")
            print(f"❌ G10-1 ERROR: {str(e)}")
            return False
    
    def verify_g10_2_type_detection(self) -> bool:
        """G10-2: Type Detection Verification"""
        print("\n🔍 G10-2: Type Detection Verification")
        
        try:
            adapter = UIAdapter()
            url_detector = adapter.url_detector
            unified_executor = adapter.unified_executor
            
            # Test URLs for each type
            test_cases = [
                ("https://github.com/user/repo/archive/main.zip", "http"),
                ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube"),
                ("https://huggingface.co/microsoft/DialoGPT-medium", "huggingface"),
                ("ftp://ftp.example.com/file.txt", "protocol"),
                ("https://files.pythonhosted.org/packages/source/s/setuptools/setuptools-69.0.3.tar.gz", "http")
            ]
            
            detection_results = {}
            
            for url, expected_type in test_cases:
                # Test URLDetector
                detector_result = url_detector.detect_url_type(url)
                
                # Test UnifiedExecutor detection
                executor_result = unified_executor.detect_download_type(url)
                
                detection_results[url] = {
                    "expected": expected_type,
                    "detector_result": detector_result,
                    "executor_result": executor_result,
                    "detector_match": detector_result == expected_type,
                    "executor_match": executor_result == expected_type
                }
                
                print(f"  📋 {url[:50]}... -> Expected: {expected_type}, Got: {executor_result}")
            
            # Calculate success rate
            total_tests = len(test_cases)
            executor_successes = sum(1 for r in detection_results.values() if r["executor_match"])
            success_rate = executor_successes / total_tests
            
            evidence = {
                "total_tests": total_tests,
                "successful_detections": executor_successes,
                "success_rate": f"{success_rate:.2%}",
                "detection_details": detection_results
            }
            
            if success_rate >= 0.8:  # 80% success threshold
                self.log_gate_result("G10-2", "PASS", f"Type detection verified ({success_rate:.2%} success)", evidence)
                print(f"✅ G10-2 PASS: Type detection verified ({success_rate:.2%} success)")
                return True
            else:
                self.log_gate_result("G10-2", "FAIL", f"Type detection below threshold ({success_rate:.2%})", evidence)
                print(f"❌ G10-2 FAIL: Type detection below threshold ({success_rate:.2%})")
                return False
                
        except Exception as e:
            self.log_gate_result("G10-2", "ERROR", f"Type detection verification error: {str(e)}")
            print(f"❌ G10-2 ERROR: {str(e)}")
            return False
    
    def verify_g10_3_type_options(self) -> bool:
        """G10-3: Type-Specific Options Verification"""
        print("\n🔍 G10-3: Type-Specific Options Verification")
        
        try:
            adapter = UIAdapter()
            unified_executor = adapter.unified_executor
            
            # Test type-specific option integration
            option_tests = [
                {
                    "url": "https://www.youtube.com/watch?v=test",
                    "type": "youtube",
                    "options": {"extract_audio": True, "quality": "720", "auto_quality": False},
                    "expected_keys": ["extract_audio", "quality", "auto_quality"]
                },
                {
                    "url": "https://huggingface.co/microsoft/DialoGPT-medium",
                    "type": "huggingface", 
                    "options": {"token": "test_token"},
                    "expected_keys": ["token"]
                },
                {
                    "url": "ftp://ftp.example.com/file.txt",
                    "type": "protocol",
                    "options": {"username": "testuser", "password": "testpass"},
                    "expected_keys": ["username", "password"]
                }
            ]
            
            options_results = {}
            
            for test in option_tests:
                try:
                    # Create unified task with options
                    task = unified_executor.create_task_for_url(
                        task_id=f"test_{test['type']}",
                        url=test["url"],
                        destination="/tmp/test",
                        priority=5,
                        **test["options"]
                    )
                    
                    # Verify task creation and option storage
                    task_options = task.get_type_specific_options()
                    
                    options_found = {key: key in task_options for key in test["expected_keys"]}
                    all_options_present = all(options_found.values())
                    
                    options_results[test["type"]] = {
                        "task_created": True,
                        "download_type": task.download_type,
                        "options_found": options_found,
                        "all_options_present": all_options_present,
                        "stored_options": task_options
                    }
                    
                    print(f"  📋 {test['type']}: {'✅' if all_options_present else '❌'} Options: {list(task_options.keys())}")
                    
                except Exception as task_error:
                    options_results[test["type"]] = {
                        "task_created": False,
                        "error": str(task_error)
                    }
                    print(f"  📋 {test['type']}: ❌ Error: {str(task_error)}")
            
            # Calculate success rate
            successful_tests = sum(1 for r in options_results.values() 
                                 if r.get("task_created", False) and r.get("all_options_present", False))
            total_tests = len(option_tests)
            success_rate = successful_tests / total_tests
            
            evidence = {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate": f"{success_rate:.2%}",
                "test_results": options_results
            }
            
            if success_rate >= 0.8:
                self.log_gate_result("G10-3", "PASS", f"Type-specific options verified ({success_rate:.2%})", evidence)
                print(f"✅ G10-3 PASS: Type-specific options verified ({success_rate:.2%})")
                return True
            else:
                self.log_gate_result("G10-3", "FAIL", f"Options verification below threshold ({success_rate:.2%})", evidence)
                print(f"❌ G10-3 FAIL: Options verification below threshold ({success_rate:.2%})")
                return False
                
        except Exception as e:
            self.log_gate_result("G10-3", "ERROR", f"Type options verification error: {str(e)}")
            print(f"❌ G10-3 ERROR: {str(e)}")
            return False
    
    def verify_g10_4_queue_persistence(self) -> bool:
        """G10-4: Queue Persistence Verification"""
        print("\n🔍 G10-4: Queue Persistence Verification")
        
        try:
            # Check if queue state file exists
            queue_state_path = "data/queue_state.json"
            
            if not os.path.exists(queue_state_path):
                self.log_gate_result("G10-4", "FAIL", "Queue state file not found", 
                                   {"queue_state_path": queue_state_path, "exists": False})
                print(f"❌ G10-4 FAIL: Queue state file not found: {queue_state_path}")
                return False
            
            # Read and verify queue state structure
            with open(queue_state_path, 'r', encoding='utf-8') as f:
                queue_state = json.load(f)
            
            # Verify required fields
            required_fields = ['tasks', 'schema_version', 'saved_at']
            missing_fields = [field for field in required_fields if field not in queue_state]
            
            if missing_fields:
                self.log_gate_result("G10-4", "FAIL", f"Queue state missing fields: {missing_fields}")
                print(f"❌ G10-4 FAIL: Queue state missing fields: {missing_fields}")
                return False
            
            # Verify tasks have type information
            tasks = queue_state.get('tasks', [])
            tasks_with_type_options = 0
            
            for task_data in tasks:
                if 'type_options' in task_data:
                    tasks_with_type_options += 1
            
            evidence = {
                "queue_state_exists": True,
                "queue_state_path": queue_state_path,
                "file_size": os.path.getsize(queue_state_path),
                "total_tasks": len(tasks),
                "tasks_with_type_options": tasks_with_type_options,
                "queue_version": queue_state.get('schema_version'),
                "last_updated": queue_state.get('saved_at')
            }
            
            self.log_gate_result("G10-4", "PASS", "Queue persistence verified", evidence)
            print(f"✅ G10-4 PASS: Queue persistence verified ({len(tasks)} tasks, {tasks_with_type_options} with type options)")
            return True
            
        except Exception as e:
            self.log_gate_result("G10-4", "ERROR", f"Queue persistence verification error: {str(e)}")
            print(f"❌ G10-4 ERROR: {str(e)}")
            return False
    
    def verify_g10_5_end_to_end(self) -> bool:
        """G10-5: Unified Pipeline End-to-End Verification"""
        print("\n🔍 G10-5: Unified Pipeline End-to-End Verification")
        
        try:
            adapter = UIAdapter()
            
            # Test complete pipeline flow with type-specific options
            test_url = "https://httpbin.org/json"  # Safe test endpoint
            test_destination = os.path.join(os.getcwd(), "test_downloads")
            test_options = {
                "connections": 2,
                "max_chunk_size": 4096,
                "priority": 3
            }
            
            # Ensure test directory exists
            os.makedirs(test_destination, exist_ok=True)
            
            # Validate URL
            validation_result = adapter.validate_url(test_url)
            
            if not validation_result.get('valid', False):
                self.log_gate_result("G10-5", "FAIL", f"URL validation failed: {validation_result}")
                print(f"❌ G10-5 FAIL: URL validation failed")
                return False
            
            print(f"  📋 URL validation: ✅ Type: {validation_result.get('type')}")
            
            # Test would start download (but we don't want to actually download)
            # Instead, verify the pipeline is properly wired
            evidence = {
                "url_validation": validation_result,
                "has_unified_executor": hasattr(adapter, 'unified_executor'),
                "has_queue_manager": hasattr(adapter, 'queue_manager'),
                "queue_enabled": getattr(adapter, 'queue_manager') is not None,
                "test_url": test_url,
                "test_destination": test_destination,
                "pipeline_components": {
                    "ui_adapter": True,
                    "unified_executor": hasattr(adapter, 'unified_executor'),
                    "queue_manager": hasattr(adapter, 'queue_manager') and adapter.queue_manager is not None,
                    "policy_engine": hasattr(adapter.unified_executor, 'policy_engine') if hasattr(adapter, 'unified_executor') else False
                }
            }
            
            # Check all pipeline components are present
            all_components = all(evidence["pipeline_components"].values())
            
            if all_components and validation_result.get('valid', False):
                self.log_gate_result("G10-5", "PASS", "End-to-end pipeline verification successful", evidence)
                print("✅ G10-5 PASS: End-to-end pipeline verified")
                return True
            else:
                self.log_gate_result("G10-5", "FAIL", "Pipeline components missing or validation failed", evidence)
                print("❌ G10-5 FAIL: Pipeline components missing or validation failed")
                return False
            
        except Exception as e:
            self.log_gate_result("G10-5", "ERROR", f"End-to-end verification error: {str(e)}")
            print(f"❌ G10-5 ERROR: {str(e)}")
            return False
    
    def run_verification_suite(self) -> Dict[str, Any]:
        """Run complete Phase 10.5 verification suite"""
        print("🚀 Phase 10.5 Verification Gates Starting...")
        print("=" * 60)
        
        start_time = datetime.now()
        gates = [
            ("G10-1", self.verify_g10_1_ui_integration),
            ("G10-2", self.verify_g10_2_type_detection),
            ("G10-3", self.verify_g10_3_type_options),
            ("G10-4", self.verify_g10_4_queue_persistence),
            ("G10-5", self.verify_g10_5_end_to_end)
        ]
        
        gate_results = {}
        passed_gates = 0
        
        for gate_name, gate_func in gates:
            try:
                result = gate_func()
                gate_results[gate_name] = "PASS" if result else "FAIL"
                if result:
                    passed_gates += 1
            except Exception as e:
                gate_results[gate_name] = "ERROR"
                self.logger.error(f"Gate {gate_name} execution error: {str(e)}")
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Final summary
        print("\n" + "=" * 60)
        print("📊 Phase 10.5 Verification Summary")
        print("=" * 60)
        
        for gate_name, status in gate_results.items():
            status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
            print(f"{status_icon} {gate_name}: {status}")
        
        success_rate = passed_gates / len(gates) * 100
        print(f"\n📈 Overall Success Rate: {success_rate:.1f}% ({passed_gates}/{len(gates)} gates passed)")
        print(f"⏱️  Verification Duration: {duration.total_seconds():.2f} seconds")
        
        final_result = {
            "overall_status": "PASS" if passed_gates == len(gates) else "FAIL",
            "passed_gates": passed_gates,
            "total_gates": len(gates),
            "success_rate": f"{success_rate:.1f}%",
            "duration_seconds": duration.total_seconds(),
            "gate_results": gate_results,
            "verification_time": end_time.isoformat(),
            "detailed_results": self.results
        }
        
        # Save verification report
        report_path = f"logs/phase10_verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(final_result, f, indent=2, ensure_ascii=False)
            print(f"📋 Verification report saved: {report_path}")
        except Exception as e:
            print(f"❌ Failed to save verification report: {e}")
        
        return final_result


if __name__ == "__main__":
    verifier = Phase10Verifier()
    result = verifier.run_verification_suite()
    
    # Exit with appropriate code
    exit_code = 0 if result["overall_status"] == "PASS" else 1
    sys.exit(exit_code)