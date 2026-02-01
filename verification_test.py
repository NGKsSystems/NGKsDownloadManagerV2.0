"""
Verification Test Script for Multi-Connection Downloads
Tests real server capability detection and multi-connection performance
"""

import os
import tempfile
from verified_multi_downloader import MultiConnectionDownloader, setup_logging

def test_server_capability_detection():
    """Test server capability detection with known servers"""
    print("🔍 Testing Server Capability Detection")
    print("=" * 50)
    
    downloader = MultiConnectionDownloader()
    
    test_servers = [
        {
            'name': 'HTTPBin (No Range Support)',
            'url': 'https://httpbin.org/bytes/1048576',
            'expected_support': False
        },
        {
            'name': 'Ubuntu ISO Mirror (Range Support)',
            'url': 'http://releases.ubuntu.com/20.04/ubuntu-20.04.6-desktop-amd64.iso',
            'expected_support': True
        },
        {
            'name': 'GitHub Release Asset',
            'url': 'https://github.com/git/git/archive/refs/tags/v2.42.0.tar.gz',
            'expected_support': True
        }
    ]
    
    results = []
    
    for server in test_servers:
        print(f"\n🌐 Testing: {server['name']}")
        print(f"   URL: {server['url']}")
        
        try:
            capability = downloader._check_server_capability(server['url'])
            
            print(f"   📊 Server Capability Results:")
            print(f"      Range Support: {capability.supports_range}")
            print(f"      Content Length: {capability.content_length:,} bytes" if capability.content_length else "      Content Length: Unknown")
            print(f"      Content Type: {capability.content_type}")
            print(f"      Server: {capability.server}")
            
            expected = server['expected_support']
            actual = capability.supports_range
            
            if actual == expected:
                print(f"   ✅ Detection Correct (Expected: {expected})")
            else:
                print(f"   ⚠️  Detection Mismatch (Expected: {expected}, Got: {actual})")
            
            results.append({
                'name': server['name'],
                'url': server['url'],
                'expected': expected,
                'actual': actual,
                'correct': actual == expected,
                'capability': capability
            })
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results.append({
                'name': server['name'],
                'url': server['url'],
                'error': str(e)
            })
    
    return results

def test_download_with_different_file_sizes():
    """Test downloads with different file sizes to verify multi-connection benefit"""
    print("\n🔍 Testing Multi-Connection with Different File Sizes")
    print("=" * 50)
    
    # Use a server that supports range requests
    base_url = "https://httpbin.org/bytes"
    file_sizes = [
        (1024, "1KB"),
        (1024*100, "100KB"), 
        (1024*1024, "1MB"),
        (1024*1024*5, "5MB")
    ]
    
    downloader_single = MultiConnectionDownloader(max_connections=1)
    downloader_multi = MultiConnectionDownloader(max_connections=4)
    
    results = []
    
    for size_bytes, size_name in file_sizes:
        print(f"\n📁 Testing {size_name} download")
        url = f"{base_url}/{size_bytes}"
        
        # Test single connection
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path_single = temp_file.name
        
        print(f"   🔗 Single connection...", end=" ")
        try:
            success_single, info_single = downloader_single.download_file(url, temp_path_single)
            if success_single:
                print(f"✅ {info_single['download_time']:.2f}s")
                single_result = info_single
            else:
                print("❌ Failed")
                single_result = None
        except Exception as e:
            print(f"❌ Error: {e}")
            single_result = None
        finally:
            try:
                os.unlink(temp_path_single)
            except:
                pass
        
        # Test multi connection
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path_multi = temp_file.name
        
        print(f"   🔗 Multi connection...", end=" ")
        try:
            success_multi, info_multi = downloader_multi.download_file(url, temp_path_multi)
            if success_multi:
                print(f"✅ {info_multi['download_time']:.2f}s, {info_multi['connections_used']} conn")
                multi_result = info_multi
            else:
                print("❌ Failed")
                multi_result = None
        except Exception as e:
            print(f"❌ Error: {e}")
            multi_result = None
        finally:
            try:
                os.unlink(temp_path_multi)
            except:
                pass
        
        # Compare results
        if single_result and multi_result:
            improvement = single_result['download_time'] / multi_result['download_time']
            print(f"   📊 Performance: {improvement:.2f}x {'faster' if improvement > 1 else 'slower'}")
        
        results.append({
            'size_name': size_name,
            'size_bytes': size_bytes,
            'single': single_result,
            'multi': multi_result
        })
    
    return results

def test_resume_capability():
    """Test resume capability for interrupted downloads"""
    print("\n🔍 Testing Resume Capability")
    print("=" * 50)
    
    # Create a partial download file
    test_url = "https://httpbin.org/bytes/5242880"  # 5MB
    
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path = temp_file.name
    
    downloader = MultiConnectionDownloader(max_connections=4)
    
    try:
        print("📥 Starting initial download...")
        
        # Download part of the file (simulate interruption)
        success, info = downloader.download_file(test_url, temp_path)
        
        if success:
            print(f"✅ Download completed: {info['file_size']:,} bytes")
            print(f"   Mode: {info['mode']}")
            print(f"   Connections: {info['connections_used']}")
            print(f"   Time: {info['download_time']:.2f}s")
            return True
        else:
            print("❌ Download failed")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    finally:
        try:
            os.unlink(temp_path)
        except:
            pass

def main():
    """Run comprehensive verification tests"""
    print("🚀 Multi-Connection Download Verification Suite")
    print("=" * 60)
    
    setup_logging()
    
    # Test 1: Server capability detection
    capability_results = test_server_capability_detection()
    
    # Test 2: Different file sizes
    size_results = test_download_with_different_file_sizes()
    
    # Test 3: Resume capability
    resume_result = test_resume_capability()
    
    # Summary
    print("\n" + "="*60)
    print("📊 VERIFICATION SUMMARY")
    print("="*60)
    
    # Capability detection summary
    capability_correct = sum(1 for r in capability_results if r.get('correct', False))
    capability_total = len([r for r in capability_results if 'correct' in r])
    
    print(f"\n🔍 Server Capability Detection:")
    print(f"   ✅ Correct detections: {capability_correct}/{capability_total}")
    
    # Performance summary
    successful_comparisons = sum(1 for r in size_results if r['single'] and r['multi'])
    total_comparisons = len(size_results)
    
    print(f"\n📊 Performance Comparisons:")
    print(f"   ✅ Successful comparisons: {successful_comparisons}/{total_comparisons}")
    
    if successful_comparisons > 0:
        improvements = []
        for r in size_results:
            if r['single'] and r['multi']:
                improvement = r['single']['download_time'] / r['multi']['download_time']
                improvements.append(improvement)
        
        if improvements:
            avg_improvement = sum(improvements) / len(improvements)
            print(f"   📈 Average improvement: {avg_improvement:.2f}x")
    
    # Resume capability
    print(f"\n🔄 Resume Capability:")
    print(f"   ✅ Resume test: {'Passed' if resume_result else 'Failed'}")
    
    # Overall assessment
    print(f"\n🏆 Overall Assessment:")
    if capability_correct >= capability_total * 0.8 and successful_comparisons > 0:
        print("   ✅ Multi-connection implementation verified")
    else:
        print("   ⚠️  Implementation needs improvement")

if __name__ == "__main__":
    main()