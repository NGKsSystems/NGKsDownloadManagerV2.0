"""Test GitHub range request support"""

import requests

def test_github_range_support():
    url = 'https://github.com/git/git/archive/refs/heads/master.zip'
    
    # Try a range request
    headers = {'Range': 'bytes=0-1023'}
    resp = requests.get(url, headers=headers, allow_redirects=True)
    
    print(f'Range request status: {resp.status_code}')
    print(f'Content-Length: {resp.headers.get("content-length", "NOT PRESENT")}')
    print(f'Content-Range: {resp.headers.get("content-range", "NOT PRESENT")}')
    print(f'Accept-Ranges: {resp.headers.get("accept-ranges", "NOT PRESENT")}')
    print(f'Data received: {len(resp.content)} bytes')
    
    if resp.status_code == 206:
        print('✅ Server supports range requests!')
        return True
    else:
        print('❌ Server does not support range requests')
        return False

if __name__ == "__main__":
    test_github_range_support()