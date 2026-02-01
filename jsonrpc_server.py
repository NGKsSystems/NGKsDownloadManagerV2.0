"""
JSON-RPC API Server for Advanced Download Manager
Provides aria2-like remote control interface for automation
"""

import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import logging
from typing import Dict, Any, Optional, List
from advanced_download_manager import AdvancedDownloadManager

class JSONRPCHandler(BaseHTTPRequestHandler):
    """HTTP handler for JSON-RPC requests"""
    
    def __init__(self, *args, download_manager=None, **kwargs):
        self.download_manager = download_manager
        super().__init__(*args, **kwargs)
    
    def do_POST(self):
        """Handle POST requests (JSON-RPC calls)"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            # Parse JSON-RPC request
            request = json.loads(post_data)
            
            # Process request
            response = self.process_rpc_request(request)
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            self.send_error_response(str(e))
    
    def do_GET(self):
        """Handle GET requests (for web interface)"""
        parsed_url = urlparse(self.path)
        
        if parsed_url.path == '/jsonrpc':
            # Return API documentation
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            api_doc = {
                "name": "NGK's Download Manager API",
                "version": "2.0",
                "methods": [
                    "aria2.addUri",
                    "aria2.remove",
                    "aria2.pause",
                    "aria2.unpause",
                    "aria2.tellStatus",
                    "aria2.tellActive",
                    "aria2.tellWaiting",
                    "aria2.tellStopped",
                    "aria2.getGlobalStat",
                    "aria2.getGlobalOption",
                    "aria2.changeGlobalOption"
                ]
            }
            
            self.wfile.write(json.dumps(api_doc, indent=2).encode('utf-8'))
        else:
            self.send_error(404)
    
    def process_rpc_request(self, request: Dict) -> Dict:
        """Process a JSON-RPC request"""
        method = request.get('method', '')
        params = request.get('params', [])
        request_id = request.get('id', None)
        
        try:
            result = self.handle_method(method, params)
            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32000,
                    "message": str(e)
                },
                "id": request_id
            }
    
    def handle_method(self, method: str, params: List) -> Any:
        """Handle specific RPC methods"""
        if method == 'aria2.addUri':
            return self.add_uri(params)
        elif method == 'aria2.remove':
            return self.remove_download(params)
        elif method == 'aria2.pause':
            return self.pause_download(params)
        elif method == 'aria2.tellStatus':
            return self.tell_status(params)
        elif method == 'aria2.tellActive':
            return self.tell_active(params)
        elif method == 'aria2.tellWaiting':
            return self.tell_waiting(params)
        elif method == 'aria2.getGlobalStat':
            return self.get_global_stat(params)
        elif method == 'aria2.getGlobalOption':
            return self.get_global_option(params)
        elif method == 'aria2.changeGlobalOption':
            return self.change_global_option(params)
        else:
            raise Exception(f"Unknown method: {method}")
    
    def add_uri(self, params: List) -> str:
        """Add a new download (aria2.addUri)"""
        if not params or not params[0]:
            raise Exception("URLs required")
        
        urls = params[0] if isinstance(params[0], list) else [params[0]]
        options = params[1] if len(params) > 1 else {}
        
        # Convert aria2 options to our format
        download_options = self.convert_aria2_options(options)
        
        # Add download
        task_id = self.download_manager.add_download(
            url=urls[0],  # For now, take first URL
            destination=download_options.get('dir', './downloads'),
            priority=download_options.get('priority', 5),
            max_connections=download_options.get('max_connections', 16),
            **download_options
        )
        
        return task_id
    
    def remove_download(self, params: List) -> str:
        """Remove/cancel a download (aria2.remove)"""
        if not params:
            raise Exception("Task ID required")
        
        task_id = params[0]
        success = self.download_manager.cancel_download(task_id)
        
        if success:
            return task_id
        else:
            raise Exception(f"Download {task_id} not found")
    
    def pause_download(self, params: List) -> str:
        """Pause a download (aria2.pause)"""
        if not params:
            raise Exception("Task ID required")
        
        task_id = params[0]
        success = self.download_manager.pause_download(task_id)
        
        if success:
            return task_id
        else:
            raise Exception(f"Download {task_id} not found")
    
    def tell_status(self, params: List) -> Dict:
        """Get download status (aria2.tellStatus)"""
        if not params:
            raise Exception("Task ID required")
        
        task_id = params[0]
        status = self.download_manager.get_download_status(task_id)
        
        if not status:
            raise Exception(f"Download {task_id} not found")
        
        return self.convert_to_aria2_status(task_id, status)
    
    def tell_active(self, params: List) -> List[Dict]:
        """Get all active downloads (aria2.tellActive)"""
        active = self.download_manager.get_active_downloads()
        result = []
        
        for task_id, status in active.items():
            if status['status'] in ['starting', 'downloading']:
                result.append(self.convert_to_aria2_status(task_id, status))
        
        return result
    
    def tell_waiting(self, params: List) -> List[Dict]:
        """Get waiting downloads (aria2.tellWaiting)"""
        # For now, return empty list as we don't track waiting downloads separately
        return []
    
    def get_global_stat(self, params: List) -> Dict:
        """Get global statistics (aria2.getGlobalStat)"""
        stats = self.download_manager.get_stats()
        active = self.download_manager.get_active_downloads()
        
        downloading_count = sum(1 for status in active.values() 
                              if status['status'] == 'downloading')
        
        return {
            "downloadSpeed": str(int(sum(status.get('speed', 0) 
                                       for status in active.values()))),
            "uploadSpeed": "0",
            "numActive": str(downloading_count),
            "numWaiting": "0",
            "numStopped": str(stats.get('downloads_completed', 0) + 
                            stats.get('downloads_failed', 0))
        }
    
    def get_global_option(self, params: List) -> Dict:
        """Get global options (aria2.getGlobalOption)"""
        return {
            "max-concurrent-downloads": str(self.download_manager.max_concurrent_downloads),
            "max-connection-per-server": str(self.download_manager.max_connections_per_download),
            "split": str(self.download_manager.max_connections_per_download),
            "max-overall-download-limit": "0",
            "max-download-limit": "0"
        }
    
    def change_global_option(self, params: List) -> str:
        """Change global options (aria2.changeGlobalOption)"""
        if not params:
            raise Exception("Options required")
        
        options = params[0]
        
        if 'max-concurrent-downloads' in options:
            self.download_manager.max_concurrent_downloads = int(options['max-concurrent-downloads'])
        
        if 'max-connection-per-server' in options:
            self.download_manager.max_connections_per_download = int(options['max-connection-per-server'])
        
        if 'max-overall-download-limit' in options:
            limit = int(options['max-overall-download-limit'])
            self.download_manager.set_global_bandwidth_limit(limit)
        
        if 'max-download-limit' in options:
            limit = int(options['max-download-limit'])
            self.download_manager.set_per_download_bandwidth_limit(limit)
        
        return "OK"
    
    def convert_aria2_options(self, options: Dict) -> Dict:
        """Convert aria2 options to our internal format"""
        converted = {}
        
        if 'dir' in options:
            converted['destination'] = options['dir']
        
        if 'max-connection-per-server' in options:
            converted['max_connections'] = int(options['max-connection-per-server'])
        
        if 'split' in options:
            converted['max_connections'] = int(options['split'])
        
        if 'user-agent' in options:
            converted['headers'] = {'User-Agent': options['user-agent']}
        
        if 'referer' in options:
            if 'headers' not in converted:
                converted['headers'] = {}
            converted['headers']['Referer'] = options['referer']
        
        return converted
    
    def convert_to_aria2_status(self, task_id: str, status: Dict) -> Dict:
        """Convert internal status to aria2 format"""
        task = status.get('task')
        if not task:
            return {}
        
        return {
            "gid": task_id,
            "status": self.map_status_to_aria2(status['status']),
            "totalLength": "0",  # Would need file info
            "completedLength": "0",  # Would need progress info
            "uploadLength": "0",
            "downloadSpeed": str(int(status.get('speed', 0))),
            "uploadSpeed": "0",
            "dir": task.destination,
            "files": [
                {
                    "index": "1",
                    "path": task.destination,
                    "length": "0",
                    "completedLength": "0",
                    "selected": "true",
                    "uris": [
                        {
                            "uri": task.url,
                            "status": "used"
                        }
                    ]
                }
            ]
        }
    
    def map_status_to_aria2(self, status: str) -> str:
        """Map internal status to aria2 status"""
        mapping = {
            'starting': 'waiting',
            'downloading': 'active',
            'completed': 'complete',
            'failed': 'error',
            'cancelled': 'removed',
            'paused': 'paused'
        }
        return mapping.get(status, 'unknown')
    
    def send_error_response(self, error_msg: str):
        """Send error response"""
        self.send_response(500)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        error_response = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32000,
                "message": error_msg
            },
            "id": None
        }
        
        self.wfile.write(json.dumps(error_response).encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override to use our logging"""
        pass

class JSONRPCServer:
    """JSON-RPC server for download manager"""
    
    def __init__(self, download_manager: AdvancedDownloadManager, 
                 host: str = 'localhost', port: int = 6800):
        self.download_manager = download_manager
        self.host = host
        self.port = port
        self.server = None
        self.thread = None
        self.running = False
        
        self.logger = logging.getLogger(__name__)
    
    def start(self):
        """Start the JSON-RPC server"""
        if self.running:
            return
        
        # Create server with download manager reference
        def handler(*args, **kwargs):
            return JSONRPCHandler(*args, download_manager=self.download_manager, **kwargs)
        
        try:
            self.server = HTTPServer((self.host, self.port), handler)
            self.running = True
            
            # Start in separate thread
            self.thread = threading.Thread(target=self._run_server, daemon=True)
            self.thread.start()
            
            self.logger.info(f"JSON-RPC server started on {self.host}:{self.port}")
            
        except Exception as e:
            self.logger.error(f"Failed to start JSON-RPC server: {e}")
            raise
    
    def stop(self):
        """Stop the JSON-RPC server"""
        if not self.running:
            return
        
        self.running = False
        
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        
        if self.thread:
            self.thread.join(timeout=5)
        
        self.logger.info("JSON-RPC server stopped")
    
    def _run_server(self):
        """Run the server in a thread"""
        try:
            self.server.serve_forever()
        except Exception as e:
            if self.running:  # Only log if we weren't stopped intentionally
                self.logger.error(f"Server error: {e}")
    
    def is_running(self) -> bool:
        """Check if server is running"""
        return self.running and self.thread and self.thread.is_alive()

# Example usage and testing functions
def test_rpc_server():
    """Test the JSON-RPC server"""
    import requests
    
    # Test JSON-RPC call
    rpc_url = "http://localhost:6800/jsonrpc"
    
    # Add download
    payload = {
        "jsonrpc": "2.0",
        "method": "aria2.addUri",
        "params": [
            ["https://httpbin.org/bytes/1048576"],
            {"dir": "./downloads"}
        ],
        "id": "1"
    }
    
    try:
        response = requests.post(rpc_url, json=payload, timeout=10)
        print("Add URI Response:", response.json())
        
        # Get status
        if response.ok:
            result = response.json().get('result')
            if result:
                status_payload = {
                    "jsonrpc": "2.0",
                    "method": "aria2.tellStatus",
                    "params": [result],
                    "id": "2"
                }
                
                status_response = requests.post(rpc_url, json=status_payload, timeout=10)
                print("Status Response:", status_response.json())
        
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    # Example usage
    from advanced_download_manager import AdvancedDownloadManager
    
    # Create download manager
    dm = AdvancedDownloadManager()
    
    # Create and start RPC server
    rpc_server = JSONRPCServer(dm)
    
    try:
        rpc_server.start()
        print("Server started. Press Ctrl+C to stop.")
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping server...")
        rpc_server.stop()
        dm.stop()