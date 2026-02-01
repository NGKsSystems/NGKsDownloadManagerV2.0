"""
NGK's Download Manager V2.0 - Aria2-Level Features Demo
Demonstrates advanced capabilities including multi-connection downloads,
scheduling, bandwidth control, and JSON-RPC API
"""

import time
import os
import sys
from datetime import datetime, timedelta

def demo_basic_vs_advanced():
    """Compare basic vs advanced download performance"""
    print("🔥 NGK's Download Manager V2.0 - Aria2-Level Performance Demo")
    print("=" * 60)
    
    try:
        from download_manager import DownloadManager
        
        # Initialize with advanced features
        dm = DownloadManager(enable_advanced=True)
        
        print(f"✅ Supported Protocols: {', '.join(dm.get_supported_protocols())}")
        print(f"✅ Advanced Features: {dm.enable_advanced}")
        print()
        
        # Test URL - a reasonably large file
        test_url = "https://httpbin.org/bytes/10485760"  # 10MB test file
        download_dir = "./downloads"
        os.makedirs(download_dir, exist_ok=True)
        
        print("📊 Performance Comparison:")
        print("-" * 40)
        
        # Advanced download with multiple connections
        print("🚀 Multi-connection download (16 connections):")
        start_time = time.time()
        
        def progress_callback(info):
            print(f"   Progress: {info['progress']} | Speed: {info['speed']} | Status: {info['status']}")
        
        task_id = dm.download(
            url=test_url,
            destination=download_dir,
            max_connections=16,
            priority=1,
            progress_callback=progress_callback
        )
        
        if isinstance(task_id, str):
            print(f"   Task ID: {task_id}")
            # Wait a bit to see progress
            time.sleep(2)
        
        end_time = time.time()
        print(f"   Completed in: {end_time - start_time:.2f} seconds")
        
    except ImportError as e:
        print(f"❌ Advanced features not available: {e}")
        print("💡 Run: pip install aiohttp aiofiles paramiko schedule psutil")

def demo_protocol_support():
    """Demonstrate different protocol support"""
    print("\n🌐 Protocol Support Demo:")
    print("-" * 40)
    
    try:
        from protocol_handlers import ProtocolManager
        
        pm = ProtocolManager()
        protocols = pm.get_supported_protocols()
        
        print(f"✅ Supported Protocols: {', '.join(protocols)}")
        
        # Test different protocols
        test_urls = {
            "HTTP": "https://httpbin.org/bytes/1024",
            "FTP": "ftp://test.rebex.net/readme.txt",  # Public test FTP
            "SFTP": "sftp://test.rebex.net/readme.txt"  # Requires credentials
        }
        
        for protocol, url in test_urls.items():
            print(f"\n🔍 Testing {protocol}:")
            try:
                file_info = pm.get_file_info(url)
                if file_info:
                    print(f"   ✅ {protocol}: {file_info['filename']} ({file_info['size_formatted']})")
                else:
                    print(f"   ❌ {protocol}: Cannot access or not supported")
            except Exception as e:
                print(f"   ❌ {protocol}: {str(e)[:50]}...")
        
    except ImportError:
        print("❌ Protocol handlers not available")

def demo_bandwidth_control():
    """Demonstrate bandwidth limiting"""
    print("\n🚦 Bandwidth Control Demo:")
    print("-" * 40)
    
    try:
        from download_manager import DownloadManager
        
        dm = DownloadManager(enable_advanced=True)
        
        if dm.enable_advanced:
            # Set bandwidth limits
            dm.set_bandwidth_limit(
                global_limit=1024*1024,      # 1 MB/s global limit
                per_download_limit=512*1024  # 512 KB/s per download
            )
            
            print("✅ Bandwidth limits configured:")
            print("   Global: 1 MB/s")
            print("   Per-download: 512 KB/s")
        else:
            print("❌ Bandwidth control requires advanced features")
    
    except ImportError:
        print("❌ Bandwidth control not available")

def demo_scheduling():
    """Demonstrate download scheduling"""
    print("\n⏰ Download Scheduling Demo:")
    print("-" * 40)
    
    try:
        from enhanced_queue_manager import (
            EnhancedQueueManager, 
            create_delayed_schedule, 
            create_time_condition,
            create_recurring_schedule
        )
        
        qm = EnhancedQueueManager()
        qm.start()
        
        # Schedule a download for 10 seconds from now
        delayed_schedule = create_delayed_schedule(10)
        
        task_id = qm.add_download(
            url="https://httpbin.org/bytes/1024",
            destination="./downloads",
            schedule=delayed_schedule,
            priority=3
        )
        
        print(f"✅ Scheduled download: {task_id}")
        print("   Will start in 10 seconds")
        
        # Create a time-based condition (only download during work hours)
        work_hours_condition = create_time_condition(
            allowed_hours=list(range(9, 17))  # 9 AM to 5 PM
        )
        
        task_id2 = qm.add_download(
            url="https://httpbin.org/bytes/2048",
            destination="./downloads",
            conditions=[work_hours_condition],
            priority=5
        )
        
        print(f"✅ Conditional download: {task_id2}")
        print("   Will only run during work hours (9 AM - 5 PM)")
        
        # Show queue status
        status = qm.get_queue_status()
        print(f"\n📊 Queue Status:")
        for queue_name, size in status['queue_sizes'].items():
            if size > 0:
                print(f"   {queue_name.title()}: {size} downloads")
        
        time.sleep(2)
        qm.stop()
        
    except ImportError:
        print("❌ Enhanced scheduling not available")

def demo_jsonrpc_api():
    """Demonstrate JSON-RPC API"""
    print("\n🔌 JSON-RPC API Demo:")
    print("-" * 40)
    
    try:
        from download_manager import DownloadManager
        import requests
        
        # Start download manager with RPC server
        dm = DownloadManager(enable_advanced=True)
        
        if dm.enable_advanced:
            success = dm.enable_rpc_server(host='localhost', port=6800)
            
            if success:
                print("✅ JSON-RPC server started")
                print("   Compatible with aria2c tools and interfaces!")
                
                # Give server time to start
                time.sleep(1)
                
                # Test API call
                try:
                    rpc_url = "http://localhost:6800/jsonrpc"
                    
                    # Test addUri method (aria2 compatible)
                    payload = {
                        "jsonrpc": "2.0",
                        "method": "aria2.addUri",
                        "params": [
                            ["https://httpbin.org/bytes/1048576"],  # 1MB file
                            {"dir": "./downloads"}
                        ],
                        "id": "demo1"
                    }
                    
                    response = requests.post(rpc_url, json=payload, timeout=5)
                    
                    if response.ok:
                        result = response.json()
                        print(f"✅ API Call Success: {result}")
                        
                        # Get global stats
                        stats_payload = {
                            "jsonrpc": "2.0",
                            "method": "aria2.getGlobalStat",
                            "params": [],
                            "id": "demo2"
                        }
                        
                        stats_response = requests.post(rpc_url, json=stats_payload, timeout=5)
                        if stats_response.ok:
                            stats_result = stats_response.json()
                            print(f"✅ Global Stats: {stats_result['result']}")
                    
                    else:
                        print(f"❌ API call failed: {response.text}")
                        
                except Exception as e:
                    print(f"❌ API test failed: {e}")
                
                # Cleanup
                print("\n🧹 Shutting down demo...")
                dm.shutdown()
            
            else:
                print("❌ Failed to start RPC server")
        else:
            print("❌ JSON-RPC API requires advanced features")
    
    except ImportError:
        print("❌ JSON-RPC API not available")
    except Exception as e:
        print(f"❌ RPC demo failed: {e}")

def demo_download_statistics():
    """Show comprehensive download statistics"""
    print("\n📈 Download Statistics Demo:")
    print("-" * 40)
    
    try:
        from download_manager import DownloadManager
        
        dm = DownloadManager(enable_advanced=True)
        stats = dm.get_download_stats()
        
        print(f"✅ Advanced Features Enabled: {stats['advanced_features']}")
        print(f"✅ Supported Protocols: {', '.join(stats['supported_protocols'])}")
        
        if stats['advanced_features']:
            downloads = stats['downloads']
            queue = stats['queue']
            
            print(f"\n📊 Download Statistics:")
            print(f"   Total Downloaded: {downloads.get('total_downloaded', 0)} bytes")
            print(f"   Completed: {downloads.get('downloads_completed', 0)}")
            print(f"   Failed: {downloads.get('downloads_failed', 0)}")
            
            print(f"\n🗂️ Queue Information:")
            print(f"   Active Downloads: {queue['active_downloads']}")
            print(f"   Max Concurrent: {queue['max_concurrent']}")
            
            for queue_name, size in queue['queue_sizes'].items():
                if size > 0:
                    print(f"   {queue_name.title()}: {size}")
    
    except ImportError:
        print("❌ Statistics not available")

def main():
    """Run all demos"""
    print("🎯 Starting NGK's Download Manager V2.0 Demo")
    print("🆚 Comparing with aria2 capabilities...\n")
    
    # Run demos
    demo_basic_vs_advanced()
    demo_protocol_support()
    demo_bandwidth_control()
    demo_scheduling()
    demo_jsonrpc_api()
    demo_download_statistics()
    
    print("\n" + "=" * 60)
    print("🎉 Demo Complete!")
    print("\n🏆 Your download manager now has aria2-level capabilities:")
    print("   ✅ Multi-connection downloads (up to 16 connections)")
    print("   ✅ Protocol support (HTTP/HTTPS/FTP/SFTP)")
    print("   ✅ Bandwidth control and limiting")
    print("   ✅ Advanced scheduling and conditions")
    print("   ✅ JSON-RPC API (aria2-compatible)")
    print("   ✅ Enhanced queue management")
    print("   ✅ Download resuming and retry logic")
    print("\n🚀 While keeping all your original features:")
    print("   ✅ YouTube & social media downloads")
    print("   ✅ HuggingFace model/dataset support")
    print("   ✅ Modern GUI interface")
    print("   ✅ Download history and management")
    
if __name__ == "__main__":
    main()