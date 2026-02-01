"""Find a server that supports range requests"""

import requests

def test_range_support(url):
    try:
        print(f'Testing: {url}')
        headers = {'Range': 'bytes=0-1023'}
        resp = requests.get(url, headers=headers, timeout=10)
        print(f'  Status: {resp.status_code}')
        print(f'  Accept-Ranges: {resp.headers.get("accept-ranges", "NOT PRESENT")}')
        print(f'  Content-Range: {resp.headers.get("content-range", "NOT PRESENT")}')
        if resp.status_code == 206:
            print(f'  ✅ SUPPORTS RANGE REQUESTS!')
            return True
        else:
            print(f'  ❌ Does not support range requests')
            return False
    except Exception as e:
        print(f'  Error: {e}')
        return False

def main():
    # Test with servers known to support range requests
    urls_to_test = [
        'https://www.learningcontainer.com/wp-content/uploads/2020/05/sample-zip-file.zip',
        'https://file-examples.com/storage/febb10b7b58e39ac8e92e11/2017/10/file_example_JPG_100kB.jpg',
        'https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.1.tar.xz',
        'https://archive.org/download/BigBuckBunny_124/Content/big_buck_bunny_720p_surround.mp4'
    ]
    
    supporting_servers = []
    
    for url in urls_to_test:
        if test_range_support(url):
            supporting_servers.append(url)
        print()
    
    print(f"Found {len(supporting_servers)} servers that support range requests:")
    for url in supporting_servers:
        print(f"  {url}")

if __name__ == "__main__":
    main()