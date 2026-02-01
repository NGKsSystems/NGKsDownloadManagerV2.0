#!/usr/bin/env python3
"""
Technical Verification Script - Download Manager V2.0
Systematically tests each claimed feature for actual functionality
"""

import sys
import time
import os
import tempfile
import hashlib
from urllib.parse import urlparse

def test_multi_connection_download():
    """Test if multi-connection downloads actually use multiple TCP connections"""
    print("🔍 Testing Multi-Connection Downloads...")
    
    try:
        from advanced_download_manager import AdvancedDownloadManager
        
        # Test file that supports range requests
        test_url = "https://httpbin.org/bytes/1048576"  # 1MB
        
        with tempfile.TemporaryDirectory() as temp_dir:
            dm = AdvancedDownloadManager(max_connections_per_download=4)
            
            # Test file info first
            file_info = dm.get_file_info(test_url)
            print(f"   File info: {file_info}")
            
            if not file_info or not file_info.get('supports_resume', False):
                print("   ❌ FAIL: Server doesn't support Range requests - multi-connection impossible")
                return False
            
            # Add download with multiple connections
            task_id = dm.add_download(
                url=test_url,
                destination=temp_dir,
                max_connections=4
            )
            
            print(f"   Task ID: {task_id}")
            
            # Wait for completion and check
            timeout = 30
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                status = dm.get_download_status(task_id)
                if status and status['status'] == 'completed':
                    print("   ✅ PASS: Multi-connection download completed")
                    
                    # Check if segments were actually used
                    segments = status.get('segments', [])
                    if len(segments) > 1:
                        print(f"   ✅ PASS: Used {len(segments)} segments")
                        return True
                    else:
                        print("   ⚠️  PARTIAL: Completed but may not have used multiple connections")
                        return False
                
                elif status and status['status'] == 'failed':
                    print(f"   ❌ FAIL: Download failed - {status.get('error', 'Unknown error')}")
                    return False
                
                time.sleep(1)
            
            print("   ❌ FAIL: Download timed out")
            return False
            
    except ImportError as e:
        print(f"   ❌ FAIL: Cannot import advanced download manager - {e}")
        return False
    except Exception as e:
        print(f"   ❌ FAIL: Exception during test - {e}")
        return False

def test_bandwidth_limiting():
    """Test if bandwidth limiting actually works"""
    print("\n🔍 Testing Bandwidth Limiting...")
    
    try:
        from advanced_download_manager import AdvancedDownloadManager
        
        dm = AdvancedDownloadManager()
        
        # Set a very low bandwidth limit
        dm.set_per_download_bandwidth_limit(1024)  # 1 KB/s
        
        # This doesn't actually test enforcement - would need network monitoring
        print("   ⚠️  PARTIAL: Bandwidth controller exists but enforcement not verified")
        print("   ⚠️  LIMITATION: Requires network monitoring to verify actual throttling")
        
        return False  # Cannot verify without actual network measurement
        
    except Exception as e:
        print(f"   ❌ FAIL: Exception during test - {e}")
        return False

def test_protocol_support():
    """Test actual protocol support"""
    print("\n🔍 Testing Protocol Support...")
    
    try:
        from protocol_handlers import ProtocolManager
        
        pm = ProtocolManager()
        
        # Test HTTP
        http_info = pm.get_file_info("https://httpbin.org/bytes/1024")
        if http_info:
            print("   ✅ PASS: HTTP/HTTPS protocol working")
        else:
            print("   ❌ FAIL: HTTP protocol not working")
        
        # Test FTP - need a test server
        try:
            ftp_info = pm.get_file_info("ftp://test.rebex.net/readme.txt")
            if ftp_info:
                print("   ✅ PASS: FTP protocol working")
            else:
                print("   ❌ FAIL: FTP protocol not working")
        except Exception as e:
            print(f"   ❌ FAIL: FTP protocol error - {e}")
        
        # Test SFTP
        try:
            import paramiko
            print("   ✅ PASS: SFTP dependencies available")
        except ImportError:
            print("   ❌ FAIL: SFTP not available - paramiko not installed")
        
        return True
        
    except Exception as e:
        print(f"   ❌ FAIL: Exception during test - {e}")
        return False

def test_jsonrpc_api():
    """Test JSON-RPC API functionality"""
    print("\n🔍 Testing JSON-RPC API...")
    
    try:
        from jsonrpc_server import JSONRPCServer
        from advanced_download_manager import AdvancedDownloadManager
        import requests
        import threading
        
        dm = AdvancedDownloadManager()
        server = JSONRPCServer(dm, port=6801)  # Use different port
        
        # Start server in thread
        def start_server():
            server.start()
        
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()
        time.sleep(2)  # Let server start
        
        # Test API call
        try:
            response = requests.get("http://localhost:6801/jsonrpc", timeout=5)
            if response.ok:
                print("   ✅ PASS: JSON-RPC server responds")
                
                # Test actual RPC call
                rpc_payload = {
                    "jsonrpc": "2.0",
                    "method": "aria2.getGlobalStat",
                    "params": [],
                    "id": "test1"
                }
                
                rpc_response = requests.post("http://localhost:6801/jsonrpc", 
                                           json=rpc_payload, timeout=5)
                if rpc_response.ok:
                    result = rpc_response.json()
                    print("   ✅ PASS: RPC calls work")
                    print(f"   Response: {result}")
                else:
                    print(f"   ❌ FAIL: RPC call failed - {rpc_response.text}")
            else:
                print("   ❌ FAIL: JSON-RPC server not responding")
                return False
        
        except requests.exceptions.ConnectionError:
            print("   ❌ FAIL: Cannot connect to JSON-RPC server")
            return False
        finally:
            server.stop()
        
        return True
        
    except Exception as e:
        print(f"   ❌ FAIL: Exception during test - {e}")
        return False

def test_resume_capability():
    """Test download resume functionality"""
    print("\n🔍 Testing Resume Capability...")
    
    try:
        from download_manager import DownloadManager
        
        # This would require interrupting a download mid-stream
        # and restarting to test properly
        print("   ⚠️  LIMITATION: Resume testing requires controlled interruption")
        print("   ⚠️  LIMITATION: Cannot verify without actual network interruption")
        
        return False  # Cannot properly test without setup
        
    except Exception as e:
        print(f"   ❌ FAIL: Exception during test - {e}")
        return False

def test_async_vs_sync():
    """Check if async components are actually used"""
    print("\n🔍 Testing Async Implementation...")
    
    try:
        # Check if async imports exist but are actually used
        from advanced_download_manager import AdvancedDownloadManager
        import inspect
        
        dm = AdvancedDownloadManager()
        
        # Check if any methods are actually async
        async_methods = []
        for name, method in inspect.getmembers(dm, predicate=inspect.ismethod):
            if inspect.iscoroutinefunction(method):
                async_methods.append(name)
        
        if async_methods:
            print(f"   ✅ PASS: Found async methods: {async_methods}")
        else:
            print("   ❌ FAIL: No async methods found - aiohttp imported but not used")
            
        # The implementation uses threading, not async/await
        print("   ⚠️  FINDING: Implementation uses threading, not asyncio")
        print("   ⚠️  FINDING: aiohttp imported but appears unused")
        
        return False
        
    except Exception as e:
        print(f"   ❌ FAIL: Exception during test - {e}")
        return False

def main():
    """Run all verification tests"""
    print("🔍 TECHNICAL VERIFICATION - Download Manager V2.0")
    print("=" * 60)
    
    tests = [
        ("Multi-Connection Downloads", test_multi_connection_download),
        ("Bandwidth Limiting", test_bandwidth_limiting), 
        ("Protocol Support", test_protocol_support),
        ("JSON-RPC API", test_jsonrpc_api),
        ("Resume Capability", test_resume_capability),
        ("Async Implementation", test_async_vs_sync),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"\n❌ CRITICAL ERROR in {test_name}: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 VERIFICATION SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nOverall: {passed}/{len(tests)} tests passed")
    
    if passed < len(tests):
        print("\n⚠️  CONCLUSION: Implementation has significant gaps")
    else:
        print("\n✅ CONCLUSION: Implementation verified")

if __name__ == "__main__":
    main()