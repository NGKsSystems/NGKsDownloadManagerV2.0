"""Test multi-connection with working range server"""

from verified_multi_downloader import MultiConnectionDownloader
import tempfile
import os
import time

def test_with_range_server():
    # Use Linux kernel mirror - supports range requests
    url = 'https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.1.tar.xz'
    
    print("🔍 Testing Multi-Connection Download Performance")
    print("=" * 50)
    print(f"URL: {url}")
    
    # Test single connection
    print("\n📊 Single Connection Test:")
    downloader_single = MultiConnectionDownloader(max_connections=1)
    
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path_single = temp_file.name
    
    try:
        start_time = time.time()
        success_single, info_single = downloader_single.download_file(url, temp_path_single)
        
        if success_single:
            print(f"  ✅ Success!")
            print(f"  📁 File size: {info_single['file_size']:,} bytes ({info_single['file_size']/1024/1024:.1f} MB)")
            print(f"  ⏱️  Time: {info_single['download_time']:.2f}s")
            print(f"  🔗 Connections: {info_single['connections_used']}")
            print(f"  🚀 Speed: {info_single['file_size']/info_single['download_time']/1024/1024:.2f} MB/s")
        else:
            print(f"  ❌ Failed")
            return
            
    finally:
        try:
            os.unlink(temp_path_single)
        except:
            pass
    
    # Test multi-connection
    print("\n📊 Multi-Connection Test:")
    downloader_multi = MultiConnectionDownloader(max_connections=4)
    
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path_multi = temp_file.name
    
    try:
        start_time = time.time()
        success_multi, info_multi = downloader_multi.download_file(url, temp_path_multi)
        
        if success_multi:
            print(f"  ✅ Success!")
            print(f"  📁 File size: {info_multi['file_size']:,} bytes ({info_multi['file_size']/1024/1024:.1f} MB)")
            print(f"  ⏱️  Time: {info_multi['download_time']:.2f}s")
            print(f"  🔗 Connections: {info_multi['connections_used']}")
            print(f"  🚀 Speed: {info_multi['file_size']/info_multi['download_time']/1024/1024:.2f} MB/s")
            
            # Compare performance
            print(f"\n🏆 Performance Comparison:")
            if info_single and info_multi:
                time_improvement = info_single['download_time'] / info_multi['download_time']
                speed_improvement = (info_multi['file_size']/info_multi['download_time']) / (info_single['file_size']/info_single['download_time'])
                
                print(f"  ⚡ Time improvement: {time_improvement:.2f}x")
                print(f"  📈 Speed improvement: {speed_improvement:.2f}x")
                
                if time_improvement > 1.2:
                    print(f"  🎉 Multi-connection shows significant improvement!")
                elif time_improvement > 1.0:
                    print(f"  ✅ Multi-connection shows improvement")
                else:
                    print(f"  ⚠️  Multi-connection shows no improvement")
        else:
            print(f"  ❌ Failed")
            
    finally:
        try:
            os.unlink(temp_path_multi)
        except:
            pass

if __name__ == "__main__":
    test_with_range_server()