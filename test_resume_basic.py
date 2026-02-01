"""
Simple test for resume functionality
"""

from integrated_multi_downloader import IntegratedMultiDownloader
import tempfile
import json
import os

def test_resume_basic():
    """Test basic resume functionality"""
    downloader = IntegratedMultiDownloader(max_connections=4)

    # Test state file creation
    test_dest = 'test_file.txt'
    test_segments = [(0, 999, 'test_file.txt.part000', 0), (1000, 1999, 'test_file.txt.part001', 1)]

    print('Testing state persistence...')
    downloader._save_state(
        'http://example.com/test.txt',
        test_dest,
        2000,
        test_segments,
        etag='test-etag',
        last_modified='Wed, 21 Oct 2015 07:28:00 GMT'
    )

    # Test state loading
    state = downloader._load_state(test_dest)
    if state:
        print('✓ State loaded successfully')
        print(f'  URL: {state["url"]}')
        print(f'  Total size: {state["total_size"]}')
        print(f'  Segments: {len(state["segments"])}')
        print(f'  ETag: {state["etag"]}')
    else:
        print('✗ Failed to load state')
        return False

    # Test compatibility validation
    compatible = downloader._validate_state_compatibility(
        state,
        'http://example.com/test.txt',
        2000,
        'test-etag',
        'Wed, 21 Oct 2015 07:28:00 GMT'
    )

    print(f'✓ State compatibility: {compatible}')

    # Cleanup
    state_file = downloader._get_state_file_path(test_dest)
    if os.path.exists(state_file):
        os.remove(state_file)
        print('✓ Cleanup completed')

    return True

if __name__ == "__main__":
    success = test_resume_basic()
    if success:
        print('✓ Resume functionality tests passed')
    else:
        print('✗ Resume functionality tests failed')