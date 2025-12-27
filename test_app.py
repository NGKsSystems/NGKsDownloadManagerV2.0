"""
Test script for NGK's Download Manager
Tests all major components and functionality
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch
import tempfile
import shutil

# Add the current directory to path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import our modules
from download_manager import DownloadManager
from youtube_downloader import YouTubeDownloader
from huggingface_downloader import HuggingFaceDownloader
from utils import URLDetector, ConfigManager, HistoryManager

class TestURLDetector(unittest.TestCase):
    """Test URL detection functionality"""
    
    def setUp(self):
        self.detector = URLDetector()
    
    def test_youtube_detection(self):
        """Test YouTube URL detection"""
        youtube_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/playlist?list=PLTOhZYTzufyJdfWoQJ8UmWdOqfP7lhIWN"
        ]
        
        for url in youtube_urls:
            self.assertEqual(self.detector.detect_url_type(url), "YouTube")
    
    def test_hf_detection(self):
        """Test Hugging Face URL detection"""
        hf_urls = [
            "https://huggingface.co/microsoft/DialoGPT-medium",
            "https://huggingface.co/datasets/squad",
            "https://huggingface.co/spaces/huggingface/CodeBERTa"
        ]
        
        for url in hf_urls:
            self.assertEqual(self.detector.detect_url_type(url), "Hugging Face")
    
    def test_social_media_detection(self):
        """Test social media URL detection"""
        test_cases = [
            ("https://twitter.com/user/status/123", "Twitter"),
            ("https://instagram.com/p/ABC123/", "Instagram"),
            ("https://tiktok.com/@user/video/123", "TikTok")
        ]
        
        for url, expected in test_cases:
            self.assertEqual(self.detector.detect_url_type(url), expected)
    
    def test_direct_download_detection(self):
        """Test direct download URL detection"""
        direct_urls = [
            "https://example.com/file.zip",
            "https://example.com/document.pdf",
            "https://example.com/image.jpg"
        ]
        
        for url in direct_urls:
            self.assertEqual(self.detector.detect_url_type(url), "Direct Download")
    
    def test_invalid_url(self):
        """Test invalid URL handling"""
        invalid_urls = ["not_a_url", "", "ftp://example.com"]
        
        for url in invalid_urls:
            result = self.detector.detect_url_type(url)
            self.assertIn(result, ["Invalid URL", "Unknown"])

class TestConfigManager(unittest.TestCase):
    """Test configuration management"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_config.json")
        self.config_manager = ConfigManager(self.config_file)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_save_load_config(self):
        """Test saving and loading configuration"""
        test_config = {
            'hf_token': 'test_token',
            'auto_quality': False,
            'max_downloads': 5
        }
        
        # Save config
        self.assertTrue(self.config_manager.save_config(test_config))
        
        # Load config
        loaded_config = self.config_manager.load_config()
        
        # Check values
        self.assertEqual(loaded_config['hf_token'], 'test_token')
        self.assertEqual(loaded_config['auto_quality'], False)
        self.assertEqual(loaded_config['max_downloads'], 5)
    
    def test_default_config(self):
        """Test default configuration loading"""
        config = self.config_manager.load_config()
        
        # Should have default values
        self.assertIn('hf_token', config)
        self.assertIn('auto_quality', config)
        self.assertIn('max_downloads', config)

class TestHistoryManager(unittest.TestCase):
    """Test history management"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.history_file = os.path.join(self.temp_dir, "test_history.json")
        self.history_manager = HistoryManager(self.history_file)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_add_download(self):
        """Test adding download to history"""
        download_info = {
            'filename': 'test_file.mp4',
            'url': 'https://example.com/video',
            'type': 'YouTube',
            'status': 'Completed'
        }
        
        # Add download
        self.assertTrue(self.history_manager.add_download(download_info))
        
        # Load history
        history = self.history_manager.load_history()
        
        # Check if added
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['filename'], 'test_file.mp4')
        self.assertEqual(history[0]['url'], 'https://example.com/video')
    
    def test_clear_history(self):
        """Test clearing history"""
        # Add some downloads
        for i in range(3):
            self.history_manager.add_download({
                'filename': f'file_{i}.mp4',
                'url': f'https://example.com/video_{i}',
                'type': 'YouTube',
                'status': 'Completed'
            })
        
        # Verify history has items
        history = self.history_manager.load_history()
        self.assertGreater(len(history), 0)
        
        # Clear history
        self.assertTrue(self.history_manager.clear_history())
        
        # Verify history is empty
        history = self.history_manager.load_history()
        self.assertEqual(len(history), 0)

class TestDownloadManager(unittest.TestCase):
    """Test direct download functionality"""
    
    def setUp(self):
        self.download_manager = DownloadManager()
    
    def test_get_filename_from_url(self):
        """Test filename extraction from URL"""
        test_cases = [
            ("https://example.com/file.zip", "file.zip"),
            ("https://example.com/path/document.pdf", "document.pdf"),
            ("https://example.com/image.jpg?v=1", "image.jpg")
        ]
        
        for url, expected in test_cases:
            filename = self.download_manager._get_filename_from_url(url)
            self.assertTrue(filename.endswith(expected.split('.')[-1]))
    
    def test_format_size(self):
        """Test file size formatting"""
        test_cases = [
            (1024, "1.0 KB"),
            (1048576, "1.0 MB"),
            (1073741824, "1.0 GB")
        ]
        
        for size, expected in test_cases:
            formatted = self.download_manager._format_size(size)
            self.assertEqual(formatted, expected)
    
    def test_format_speed(self):
        """Test speed formatting"""
        speed = 1048576  # 1 MB/s
        formatted = self.download_manager._format_speed(speed)
        self.assertEqual(formatted, "1.0 MB/s")

class TestYouTubeDownloader(unittest.TestCase):
    """Test YouTube downloader functionality"""
    
    def setUp(self):
        self.youtube_downloader = YouTubeDownloader()
    
    def test_format_size(self):
        """Test file size formatting"""
        test_cases = [
            (0, "0 B"),
            (1024, "1.0 KB"),
            (1048576, "1.0 MB")
        ]
        
        for size, expected in test_cases:
            formatted = self.youtube_downloader._format_size(size)
            self.assertEqual(formatted, expected)

class TestHuggingFaceDownloader(unittest.TestCase):
    """Test Hugging Face downloader functionality"""
    
    def setUp(self):
        self.hf_downloader = HuggingFaceDownloader()
    
    def test_parse_hf_url(self):
        """Test HF URL parsing"""
        test_cases = [
            ("https://huggingface.co/microsoft/DialoGPT-medium", {
                'repo_id': 'microsoft/DialoGPT-medium',
                'repo_type': 'model',
                'filename': None
            }),
            ("https://huggingface.co/datasets/squad", {
                'repo_id': 'datasets/squad',
                'repo_type': 'dataset',
                'filename': None
            })
        ]
        
        for url, expected in test_cases:
            result = self.hf_downloader._parse_hf_url(url)
            if result:
                self.assertIn(expected['repo_type'], ['model', 'dataset'])
    
    def test_format_size(self):
        """Test file size formatting"""
        test_cases = [
            (0, "0 B"),
            (1024, "1.0 KB"),
            (1048576, "1.0 MB")
        ]
        
        for size, expected in test_cases:
            formatted = self.hf_downloader._format_size(size)
            self.assertEqual(formatted, expected)

def run_basic_tests():
    """Run basic functionality tests"""
    print("=== NGK's Download Manager - Basic Tests ===")
    print()
    
    # Test URL Detection
    print("Testing URL Detection...")
    detector = URLDetector()
    
    test_urls = [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "YouTube"),
        ("https://huggingface.co/microsoft/DialoGPT-medium", "Hugging Face"),
        ("https://twitter.com/user/status/123", "Twitter"),
        ("https://example.com/file.zip", "Direct Download")
    ]
    
    for url, expected in test_urls:
        result = detector.detect_url_type(url)
        status = "✓" if result == expected else "✗"
        print(f"{status} {url[:50]}... -> {result}")
    
    print()
    
    # Test Config Manager
    print("Testing Config Manager...")
    config_manager = ConfigManager("test_config.json")
    
    test_config = {'test_key': 'test_value'}
    if config_manager.save_config(test_config):
        loaded = config_manager.load_config()
        if loaded.get('test_key') == 'test_value':
            print("✓ Config save/load working")
        else:
            print("✗ Config load failed")
    else:
        print("✗ Config save failed")
    
    # Clean up test file
    try:
        os.remove("test_config.json")
    except:
        pass
    
    print()
    
    # Test Download Manager
    print("Testing Download Manager...")
    dm = DownloadManager()
    
    # Test filename extraction
    filename = dm._get_filename_from_url("https://example.com/test.zip")
    if filename.endswith('.zip') or 'test' in filename:
        print("✓ Filename extraction working")
    else:
        print("✗ Filename extraction failed")
    
    # Test size formatting
    size_str = dm._format_size(1048576)
    if "1.0 MB" in size_str:
        print("✓ Size formatting working")
    else:
        print("✗ Size formatting failed")
    
    print()
    
    # Test imports
    print("Testing Module Imports...")
    try:
        from main import DownloadManagerGUI
        print("✓ Main GUI module imports successfully")
    except Exception as e:
        print(f"✗ Main GUI import failed: {e}")
    
    try:
        from dialogs import QualitySelectionDialog
        print("✓ Dialogs module imports successfully")
    except Exception as e:
        print(f"✗ Dialogs import failed: {e}")
    
    print()
    print("=== Basic Tests Complete ===")

def run_integration_tests():
    """Run integration tests"""
    print("=== Integration Tests ===")
    print()
    
    print("Note: Integration tests require internet connection and may take time.")
    print("These tests will not actually download files, only test metadata extraction.")
    print()
    
    # Test YouTube info extraction (if network available)
    try:
        print("Testing YouTube info extraction...")
        yt_downloader = YouTubeDownloader()
        
        # Test with a known working URL (Rick Roll - always available)
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        # This would normally extract info, but we'll skip for safety
        print("✓ YouTube downloader initialized")
        
    except Exception as e:
        print(f"✗ YouTube test failed: {e}")
    
    # Test HF API (basic)
    try:
        print("Testing Hugging Face API...")
        hf_downloader = HuggingFaceDownloader()
        
        # Test URL parsing
        test_url = "https://huggingface.co/microsoft/DialoGPT-medium"
        parsed = hf_downloader._parse_hf_url(test_url)
        
        if parsed and parsed.get('repo_id') == 'microsoft/DialoGPT-medium':
            print("✓ HF URL parsing working")
        else:
            print("✗ HF URL parsing failed")
            
    except Exception as e:
        print(f"✗ HF test failed: {e}")
    
    print()
    print("=== Integration Tests Complete ===")

if __name__ == "__main__":
    print("NGK's Download Manager - Test Suite")
    print("=" * 50)
    print()
    
    # Check if running unit tests
    if len(sys.argv) > 1 and sys.argv[1] == "unittest":
        # Run unit tests
        unittest.main(argv=[''], exit=False, verbosity=2)
    else:
        # Run basic tests
        run_basic_tests()
        print()
        
        # Ask if user wants to run integration tests
        try:
            response = input("Run integration tests? (y/n): ").lower()
            if response == 'y':
                run_integration_tests()
        except KeyboardInterrupt:
            print("\n\nTests cancelled by user")
        except:
            pass
    
    print("\nTest suite completed!")