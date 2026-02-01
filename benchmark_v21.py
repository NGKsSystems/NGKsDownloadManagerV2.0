"""
V2.1 Benchmark Suite
Compares single vs multi-connection performance on the same file
"""

import sys
import tempfile
import os
import time
import statistics
from download_manager import DownloadManager

def benchmark_download(url, test_name, file_size_mb, num_trials=3):
    """Benchmark single vs multi-connection downloads"""
    print(f"\\nBENCHMARK: {test_name}")
    print("-" * 50)
    print(f"URL: {url}")
    print(f"Expected size: ~{file_size_mb}MB")
    print(f"Trials: {num_trials} per method")
    
    # Single connection results
    print("\\n[1/2] Single Connection Tests:")
    single_dm = DownloadManager(enable_multi_connection=False, debug_logging=False)
    single_times = []
    single_sizes = []
    
    for trial in range(num_trials):
        print(f"  Trial {trial + 1}/{num_trials}...", end=" ")
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            start_time = time.time()
            success = single_dm.download(url, temp_path)
            end_time = time.time()
            
            if success:
                file_size = os.path.getsize(temp_path)
                download_time = end_time - start_time
                
                single_times.append(download_time)
                single_sizes.append(file_size)
                
                print(f"SUCCESS ({download_time:.2f}s, {file_size/1024/1024:.1f}MB)")
            else:
                print("FAILED")
        except Exception as e:
            print(f"ERROR: {e}")
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
    
    # Multi connection results
    print("\\n[2/2] Multi Connection Tests:")
    multi_dm = DownloadManager(enable_multi_connection=True, max_connections=4, debug_logging=False)
    multi_times = []
    multi_sizes = []
    
    for trial in range(num_trials):
        print(f"  Trial {trial + 1}/{num_trials}...", end=" ")
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            start_time = time.time()
            success = multi_dm.download(url, temp_path)
            end_time = time.time()
            
            if success:
                file_size = os.path.getsize(temp_path)
                download_time = end_time - start_time
                
                multi_times.append(download_time)
                multi_sizes.append(file_size)
                
                print(f"SUCCESS ({download_time:.2f}s, {file_size/1024/1024:.1f}MB)")
            else:
                print("FAILED")
        except Exception as e:
            print(f"ERROR: {e}")
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
    
    # Analysis
    print("\\nRESULTS:")
    
    if single_times and multi_times:
        single_avg = statistics.mean(single_times)
        multi_avg = statistics.mean(multi_times)
        
        single_speed = statistics.mean(single_sizes) / single_avg / 1024 / 1024  # MB/s
        multi_speed = statistics.mean(multi_sizes) / multi_avg / 1024 / 1024    # MB/s
        
        improvement = single_avg / multi_avg if multi_avg > 0 else 1.0
        
        print(f"  Single Connection: {single_avg:.2f}s avg, {single_speed:.2f} MB/s")
        print(f"  Multi Connection:  {multi_avg:.2f}s avg, {multi_speed:.2f} MB/s")
        print(f"  Performance Ratio: {improvement:.2f}x")
        
        if improvement > 1.2:
            print(f"  RESULT: Multi-connection shows significant improvement")
            return "significant"
        elif improvement > 1.0:
            print(f"  RESULT: Multi-connection shows modest improvement")
            return "modest"
        else:
            print(f"  RESULT: Multi-connection shows no improvement")
            return "none"
    else:
        print(f"  RESULT: Insufficient data for comparison")
        return "insufficient"

def main():
    """Run benchmark suite"""
    print("NGK's Download Manager V2.1 - Benchmark Suite")
    print("=" * 60)
    print("Compares single vs multi-connection performance")
    print()
    
    # Test with a large file that supports range requests
    benchmarks = [
        {
            'name': 'Large File Test',
            'url': 'https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.1.tar.xz',
            'size_mb': 128
        }
    ]
    
    results = []
    
    for benchmark in benchmarks:
        result = benchmark_download(
            benchmark['url'], 
            benchmark['name'], 
            benchmark['size_mb'],
            num_trials=2  # Fewer trials for large downloads
        )
        results.append((benchmark['name'], result))
    
    # Summary
    print("\\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    
    for test_name, result in results:
        print(f"{test_name}: {result}")
    
    # Overall assessment
    significant_count = sum(1 for _, result in results if result == "significant")
    modest_count = sum(1 for _, result in results if result == "modest")
    
    if significant_count > 0:
        print("\\nOVERALL: Multi-connection shows measurable performance benefits")
    elif modest_count > 0:
        print("\\nOVERALL: Multi-connection shows some performance benefits")
    else:
        print("\\nOVERALL: Multi-connection shows minimal or no performance benefits")
    
    print("\\nNOTE: Performance benefits depend on:")
    print("- Network conditions and bandwidth")
    print("- Server capacity and rate limiting") 
    print("- File size (larger files benefit more)")
    print("- Number of other active connections")

if __name__ == "__main__":
    main()