"""
HTTP Range Request Capability Detection
Provides reliable detection of server support for HTTP Range requests
"""

import requests
import logging

def supports_http_range(url, timeout=10):
    """
    Detect if a server supports HTTP Range requests
    
    Args:
        url (str): URL to test
        timeout (int): Request timeout in seconds
        
    Returns:
        tuple: (supports_range: bool, info: dict)
    """
    info = {
        'url': url,
        'method_used': None,
        'status_code': None,
        'accept_ranges': None,
        'content_range': None,
        'content_length': None,
        'reason': 'unknown'
    }
    
    try:
        # Step 1: Try HEAD request as hint
        logging.info(f"Range detection: checking HEAD for {url}")
        head_resp = requests.head(url, allow_redirects=True, timeout=timeout)
        info['accept_ranges'] = head_resp.headers.get('accept-ranges', 'none')
        info['content_length'] = head_resp.headers.get('content-length')
        
        if info['accept_ranges'].lower() == 'bytes':
            logging.info("Range detection: HEAD indicates bytes support")
        else:
            logging.info(f"Range detection: HEAD shows accept-ranges={info['accept_ranges']}")
            
    except Exception as e:
        logging.warning(f"Range detection: HEAD request failed for {url}: {e}")
        info['accept_ranges'] = 'unknown'
    
    try:
        # Step 2: Probe with minimal range request (definitive test)
        logging.info(f"Range detection: probing with range request for {url}")
        probe_headers = {'Range': 'bytes=0-0', 'Accept-Encoding': 'identity'}
        probe_resp = requests.get(url, headers=probe_headers, stream=True, allow_redirects=True, timeout=timeout)
        
        info['method_used'] = 'range_probe'
        info['status_code'] = probe_resp.status_code
        info['content_range'] = probe_resp.headers.get('content-range')
        
        # Range support requires status 206 AND Content-Range header
        if probe_resp.status_code == 206 and info['content_range']:
            info['reason'] = f"status=206 content-range={info['content_range']}"
            logging.info(f"Range detection: SUCCESS - {info['reason']}")
            probe_resp.close()
            return True, info
        else:
            # Read at most 1KB then close to avoid full download on range-ignored servers
            if probe_resp.status_code != 206:
                content_read = b''
                for chunk in probe_resp.iter_content(chunk_size=1024):
                    content_read += chunk
                    if len(content_read) >= 1024:
                        break
                probe_resp.close()
                
            if probe_resp.status_code == 200:
                info['reason'] = "status=200 (range ignored, full content returned)"
            else:
                info['reason'] = f"status={probe_resp.status_code} content-range={info['content_range']}"
            logging.info(f"Range detection: FAILED - {info['reason']}")
            return False, info
            
    except Exception as e:
        info['method_used'] = 'range_probe'
        info['reason'] = f"probe_error: {str(e)}"
        logging.warning(f"Range detection: FAILED - {info['reason']}")
        return False, info