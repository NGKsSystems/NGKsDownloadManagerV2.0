"""
Multi-Connection Download Benchmark Harness
Provides measurable comparison between single and multi-connection downloads
"""

import time
import os
import tempfile
import statistics
import json
from typing import Dict, List
from verified_multi_downloader import MultiConnectionDownloader, setup_logging

class DownloadBenchmark:
    """Benchmark harness for comparing download methods"""
    
    def __init__(self):
        self.results = []
        self.setup_logging()
    
    def setup_logging(self):
        """Setup benchmark logging"""
        setup_logging()
    
    def benchmark_url(self, url: str, num_trials: int = 3) -> Dict:
        """
        Benchmark a URL with both single and multi-connection downloads
        
        Args:
            url: URL to download
            num_trials: Number of trials per method
            
        Returns:
            Dict containing benchmark results
        """
        print(f"🔍 Benchmarking URL: {url}")
        print(f"   Trials per method: {num_trials}")
        
        results = {
            'url': url,
            'trials': num_trials,
            'single_connection': [],
            'multi_connection': [],
            'summary': {}
        }
        
        # Test single-connection downloads
        print("\n📊 Testing Single-Connection Downloads...")
        single_downloader = MultiConnectionDownloader(max_connections=1)
        
        for trial in range(num_trials):
            print(f"   Trial {trial + 1}/{num_trials}...", end=" ")
            
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                success, info = single_downloader.download_file(url, temp_path)
                
                if success:
                    trial_result = {
                        'trial': trial + 1,
                        'success': True,
                        'download_time': info['download_time'],
                        'file_size': info['file_size'],
                        'throughput_bps': info['throughput_bps'],
                        'connections_used': info['connections_used'],
                        'mode': info['mode']
                    }
                    results['single_connection'].append(trial_result)
                    print(f"✅ {info['download_time']:.2f}s, {info['throughput_bps']:.0f} B/s")
                else:
                    print(f"❌ Failed")
                    
            except Exception as e:
                print(f"❌ Error: {e}")
            
            finally:
                try:
                    os.unlink(temp_path)
                except:
                    pass
        
        # Test multi-connection downloads  
        print("\n📊 Testing Multi-Connection Downloads...")
        multi_downloader = MultiConnectionDownloader(max_connections=4)
        
        for trial in range(num_trials):
            print(f"   Trial {trial + 1}/{num_trials}...", end=" ")
            
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                success, info = multi_downloader.download_file(url, temp_path)
                
                if success:
                    trial_result = {
                        'trial': trial + 1,
                        'success': True,
                        'download_time': info['download_time'],
                        'file_size': info['file_size'],
                        'throughput_bps': info['throughput_bps'],
                        'connections_used': info['connections_used'],
                        'mode': info['mode']
                    }
                    results['multi_connection'].append(trial_result)
                    print(f"✅ {info['download_time']:.2f}s, {info['throughput_bps']:.0f} B/s, {info['connections_used']} conn")
                else:
                    print(f"❌ Failed")
                    
            except Exception as e:
                print(f"❌ Error: {e}")
            
            finally:
                try:
                    os.unlink(temp_path)
                except:
                    pass
        
        # Calculate summary statistics
        results['summary'] = self._calculate_summary(results)
        
        return results
    
    def _calculate_summary(self, results: Dict) -> Dict:
        """Calculate summary statistics from benchmark results"""
        single_times = [r['download_time'] for r in results['single_connection'] if r['success']]
        single_throughputs = [r['throughput_bps'] for r in results['single_connection'] if r['success']]
        
        multi_times = [r['download_time'] for r in results['multi_connection'] if r['success']]
        multi_throughputs = [r['throughput_bps'] for r in results['multi_connection'] if r['success']]
        
        summary = {
            'single_connection': {
                'successful_trials': len(single_times),
                'avg_time': statistics.mean(single_times) if single_times else 0,
                'avg_throughput': statistics.mean(single_throughputs) if single_throughputs else 0,
                'min_time': min(single_times) if single_times else 0,
                'max_time': max(single_times) if single_times else 0
            },
            'multi_connection': {
                'successful_trials': len(multi_times),
                'avg_time': statistics.mean(multi_times) if multi_times else 0,
                'avg_throughput': statistics.mean(multi_throughputs) if multi_throughputs else 0,
                'min_time': min(multi_times) if multi_times else 0,
                'max_time': max(multi_times) if multi_times else 0
            }
        }
        
        # Calculate improvement ratios
        if summary['single_connection']['avg_time'] > 0 and summary['multi_connection']['avg_time'] > 0:
            summary['time_improvement'] = summary['single_connection']['avg_time'] / summary['multi_connection']['avg_time']
            summary['throughput_improvement'] = summary['multi_connection']['avg_throughput'] / summary['single_connection']['avg_throughput']
        else:
            summary['time_improvement'] = 1.0
            summary['throughput_improvement'] = 1.0
        
        return summary
    
    def print_results(self, results: Dict):
        """Print formatted benchmark results"""
        print("\n" + "="*60)
        print("📊 BENCHMARK RESULTS")
        print("="*60)
        
        print(f"\n🎯 URL: {results['url']}")
        print(f"🔄 Trials: {results['trials']} per method")
        
        summary = results['summary']
        
        print(f"\n📈 Single-Connection Results:")
        single = summary['single_connection']
        if single['successful_trials'] > 0:
            print(f"   ✅ Successful: {single['successful_trials']}/{results['trials']}")
            print(f"   ⏱️  Average Time: {single['avg_time']:.2f}s")
            print(f"   🚀 Average Throughput: {self._format_speed(single['avg_throughput'])}")
            print(f"   📊 Time Range: {single['min_time']:.2f}s - {single['max_time']:.2f}s")
        else:
            print("   ❌ No successful downloads")
        
        print(f"\n📈 Multi-Connection Results:")
        multi = summary['multi_connection']
        if multi['successful_trials'] > 0:
            print(f"   ✅ Successful: {multi['successful_trials']}/{results['trials']}")
            print(f"   ⏱️  Average Time: {multi['avg_time']:.2f}s")
            print(f"   🚀 Average Throughput: {self._format_speed(multi['avg_throughput'])}")
            print(f"   📊 Time Range: {multi['min_time']:.2f}s - {multi['max_time']:.2f}s")
            print(f"   🔗 Connections Used: 4")
        else:
            print("   ❌ No successful downloads")
        
        # Performance comparison
        print(f"\n🏆 Performance Comparison:")
        if (single['successful_trials'] > 0 and multi['successful_trials'] > 0):
            time_improvement = summary['time_improvement']
            throughput_improvement = summary['throughput_improvement']
            
            if time_improvement > 1.1:
                print(f"   ⚡ Speed Improvement: {time_improvement:.2f}x faster")
            elif time_improvement < 0.9:
                print(f"   🐌 Speed Degradation: {1/time_improvement:.2f}x slower")
            else:
                print(f"   ➡️  Similar Performance: {time_improvement:.2f}x")
            
            print(f"   📊 Throughput Ratio: {throughput_improvement:.2f}x")
            
            if throughput_improvement > 1.2:
                print(f"   ✅ Multi-connection shows improvement")
            else:
                print(f"   ⚠️  Multi-connection shows minimal benefit")
        else:
            print("   ❌ Cannot compare - insufficient successful downloads")
    
    def _format_speed(self, bytes_per_second: float) -> str:
        """Format speed in human readable format"""
        for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
            if bytes_per_second < 1024.0:
                return f"{bytes_per_second:.1f} {unit}"
            bytes_per_second /= 1024.0
        return f"{bytes_per_second:.1f} TB/s"
    
    def save_results(self, results: Dict, filename: str):
        """Save benchmark results to JSON file"""
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved to: {filename}")

def main():
    """Run benchmark suite"""
    print("🚀 Multi-Connection Download Benchmark Suite")
    print("=" * 60)
    
    benchmark = DownloadBenchmark()
    
    # Test URLs with different characteristics
    test_urls = [
        {
            'name': 'Small File (1MB)',
            'url': 'https://httpbin.org/bytes/1048576',
            'description': '1MB test file from httpbin'
        },
        {
            'name': 'Medium File (10MB)', 
            'url': 'https://httpbin.org/bytes/10485760',
            'description': '10MB test file from httpbin'
        }
    ]
    
    all_results = []
    
    for test_case in test_urls:
        print(f"\n🧪 Testing: {test_case['name']}")
        print(f"   Description: {test_case['description']}")
        
        try:
            results = benchmark.benchmark_url(test_case['url'], num_trials=3)
            results['test_name'] = test_case['name']
            results['description'] = test_case['description']
            
            benchmark.print_results(results)
            all_results.append(results)
            
        except Exception as e:
            print(f"❌ Benchmark failed for {test_case['name']}: {e}")
    
    # Save comprehensive results
    if all_results:
        timestamp = int(time.time())
        filename = f"benchmark_results_{timestamp}.json"
        
        comprehensive_results = {
            'timestamp': timestamp,
            'benchmark_version': '2.1',
            'test_cases': all_results
        }
        
        benchmark.save_results(comprehensive_results, filename)
        
        # Print overall summary
        print("\n" + "="*60)
        print("📊 OVERALL BENCHMARK SUMMARY")
        print("="*60)
        
        successful_tests = len([r for r in all_results if 
                               r['summary']['single_connection']['successful_trials'] > 0 and
                               r['summary']['multi_connection']['successful_trials'] > 0])
        
        if successful_tests > 0:
            avg_improvement = statistics.mean([
                r['summary']['time_improvement'] for r in all_results
                if r['summary']['time_improvement'] > 0
            ])
            
            print(f"✅ Successful test cases: {successful_tests}/{len(all_results)}")
            print(f"📊 Average speed improvement: {avg_improvement:.2f}x")
            
            if avg_improvement > 1.2:
                print("🎉 Multi-connection downloads show significant improvement")
            elif avg_improvement > 1.0:
                print("✅ Multi-connection downloads show modest improvement")
            else:
                print("⚠️  Multi-connection downloads show no improvement")
        else:
            print("❌ No successful benchmark comparisons")

if __name__ == "__main__":
    main()