"""
V2.1 Integration Demo
Demonstrates the integrated multi-connection download capability
"""

import tempfile
import os
from download_manager import DownloadManager

def demo_v21_integration():
    print("NGK's DL Manager V2.1 - Integration Demo")
    print("=" * 50)
    
    # Initialize download manager
    dm = DownloadManager(enable_multi_connection=True, debug_logging=True)
    
    # Demo URL that supports range requests 
    url = "https://www.learningcontainer.com/wp-content/uploads/2020/05/sample-zip-file.zip"
    
    print(f"Demo URL: {url}")
    print("This is a small ZIP file that supports range requests")
    
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        print("\nStarting download...")
        success = dm.download(url, temp_path)
        
        if success:
            file_size = os.path.getsize(temp_path)
            print(f"\n✓ Download completed successfully!")
            print(f"  File size: {file_size:,} bytes")
            print(f"  Check the logs above to see if multi-connection was used")
        else:
            print("✗ Download failed")
            
    except Exception as e:
        print(f"✗ Error: {e}")
    
    finally:
        try:
            os.unlink(temp_path)
            print("  Temporary file cleaned up")
        except:
            pass

if __name__ == "__main__":
    demo_v21_integration()