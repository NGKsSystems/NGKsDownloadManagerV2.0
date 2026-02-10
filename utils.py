"""
Utility functions and classes for the download manager
"""

import os
import json
import re
import time
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path
import configparser

class URLDetector:
    """Detect and classify URLs for appropriate downloaders"""
    
    def __init__(self):
        self.youtube_patterns = [
            r'youtube\.com/watch\?v=',
            r'youtu\.be/',
            r'youtube\.com/shorts/',
            r'youtube\.com/playlist\?list=',
            r'youtube\.com/channel/',
            r'youtube\.com/user/',
            r'youtube\.com/c/'
        ]
        
        self.social_patterns = {
            'Twitter': [r'twitter\.com/', r'x\.com/'],
            'Instagram': [r'instagram\.com/'],
            'TikTok': [r'tiktok\.com/', r'vm\.tiktok\.com/'],
            'Facebook': [r'facebook\.com/', r'fb\.watch/'],
            'Reddit': [r'reddit\.com/r/', r'redd\.it/'],
            'Twitch': [r'twitch\.tv/', r'clips\.twitch\.tv/'],
            'Vimeo': [r'vimeo\.com/'],
            'Dailymotion': [r'dailymotion\.com/'],
            'SoundCloud': [r'soundcloud\.com/']
        }
        
        self.hf_patterns = [
            r'huggingface\.co/[^/]+/[^/]+',
            r'hf\.co/[^/]+/[^/]+',
            r'huggingface\.co/datasets/[^/]+/[^/]+',
            r'huggingface\.co/spaces/[^/]+/[^/]+',
        ]
    
    def detect_url_type(self, url):
        """
        Detect the type of URL for appropriate downloader
        
        Returns:
            str: URL type ('YouTube', 'Twitter', 'Hugging Face', 'Direct', etc.)
        """
        if not url or not self._is_valid_url(url):
            return "Invalid URL"
        
        url_lower = url.lower()
        
        # Check YouTube patterns
        for pattern in self.youtube_patterns:
            if re.search(pattern, url_lower):
                return "YouTube"
        
        # Check social media patterns
        for platform, patterns in self.social_patterns.items():
            for pattern in patterns:
                if re.search(pattern, url_lower):
                    return platform
        
        # Check Hugging Face patterns
        for pattern in self.hf_patterns:
            if re.search(pattern, url_lower):
                return "Hugging Face"
        
        # Check if it's a direct download link
        if self._is_direct_download(url):
            return "Direct Download"
        
        # Check if it might be supported by yt-dlp
        if self._might_be_supported_by_ytdlp(url):
            return "Video Site"
        
        return "Unknown"
    
    def _is_valid_url(self, url):
        """Check if URL is valid"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    def _is_direct_download(self, url):
        """Check if URL points to a direct download"""
        try:
            parsed = urlparse(url.lower())
            path = parsed.path
            
            # Common file extensions that indicate direct downloads
            download_extensions = [
                '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz',
                '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp',
                '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm',
                '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma',
                '.exe', '.msi', '.deb', '.rpm', '.dmg', '.pkg',
                '.iso', '.img', '.bin',
                '.json', '.xml', '.csv', '.txt', '.log',
                '.apk', '.ipa'
            ]
            
            return any(path.endswith(ext) for ext in download_extensions)
            
        except:
            return False
    
    def _might_be_supported_by_ytdlp(self, url):
        """Check if URL might be supported by yt-dlp"""
        # Common video hosting domains that yt-dlp supports
        supported_domains = [
            'vimeo.com', 'dailymotion.com', 'twitch.tv', 'soundcloud.com',
            'bandcamp.com', 'mixcloud.com', 'pornhub.com', 'xvideos.com',
            'streamable.com', 'ted.com', 'bloomberg.com', 'cnn.com'
        ]
        
        try:
            domain = urlparse(url.lower()).netloc
            return any(supported in domain for supported in supported_domains)
        except:
            return False
    
    def extract_domain(self, url):
        """Extract domain from URL"""
        try:
            return urlparse(url).netloc
        except:
            return "Unknown"
    
    def is_playlist_url(self, url):
        """Check if URL is a playlist"""
        playlist_indicators = [
            'playlist', 'list=', 'album', 'set',
            'collection', 'series'
        ]
        
        url_lower = url.lower()
        return any(indicator in url_lower for indicator in playlist_indicators)


class ConfigManager:
    """Manage application configuration"""
    
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.default_config = {
            'hf_token': '',
            'auto_quality': True,
            'extract_audio': False,
            'max_downloads': 3,
            'destination': os.path.expanduser("~/Downloads/NGK_Downloads"),
            'theme': 'default',
            'auto_resume': True,
            'max_retries': 3,
            'chunk_size': 8192,
            'save_thumbnails': True,
            'save_metadata': True,
            'window_geometry': '800x600',
            'last_destination': '',
            'download_history': []
        }
    
    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    merged_config = self.default_config.copy()
                    merged_config.update(config)
                    return merged_config
            else:
                return self.default_config.copy()
        except Exception as e:
            print(f"Error loading config: {e}")
            return self.default_config.copy()
    
    def save_config(self, config):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get_setting(self, key, default=None):
        """Get a specific setting"""
        config = self.load_config()
        return config.get(key, default)
    
    def set_setting(self, key, value):
        """Set a specific setting"""
        config = self.load_config()
        config[key] = value
        return self.save_config(config)
    
    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        return self.save_config(self.default_config.copy())


class HistoryManager:
    """Manage V2 download history - separate from V1"""
    
    def __init__(self, history_file="data/download_history_v2.json"):
        self.history_file = history_file
        # Ensure data directory exists
        os.makedirs(os.path.dirname(history_file), exist_ok=True)
    
    def add_download(self, download_info):
        """Add download to V2 history with deduplication within V2 only"""
        try:
            history = self.load_history()
            
            # Add timestamp if not present
            if 'timestamp' not in download_info or download_info['timestamp'] is None:
                download_info['timestamp'] = int(time.time())
            
            # Create V2 history entry (native format)
            v2_entry = {
                'url': download_info.get('url', ''),
                'filename': download_info.get('filename', 'Unknown'),
                'url_type': download_info.get('url_type', 'Unknown'),  # V2 uses url_type
                'destination': download_info.get('destination', ''),
                'status': download_info.get('status', 'Completed'),
                'file_size': download_info.get('file_size', 0),
                'timestamp': download_info['timestamp'],
                'download_time': datetime.fromtimestamp(download_info['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Deduplication within V2 history only (within 10 seconds)
            current_time = v2_entry['timestamp']
            is_duplicate = False
            
            for existing in reversed(history[-20:]):  # Check last 20 V2 entries
                time_diff = abs(current_time - existing.get('timestamp', 0))
                if (time_diff < 10 and  # Within 10 seconds
                    existing.get('url') == v2_entry['url'] and
                    existing.get('filename') == v2_entry['filename'] and
                    existing.get('destination') == v2_entry['destination'] and
                    existing.get('status') == v2_entry['status']):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                history.append(v2_entry)
                
                # Keep only last 1000 entries
                if len(history) > 1000:
                    history = history[-1000:]
                
                self.save_history(history)
                return True
            else:
                print(f"Duplicate V2 history entry skipped: {v2_entry['filename']}")
                return True  # Not an error, just a skip
            
        except Exception as e:
            print(f"Error adding to V2 history: {e}")
            return False
    
    def load_history(self):
        """Load download history"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return []
        except Exception as e:
            print(f"Error loading history: {e}")
            return []
    
    def get_history(self):
        """Get download history (alias for load_history for UI compatibility)"""
        return self.load_history()
    
    def save_history(self, history):
        """Save download history"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving history: {e}")
            return False
    
    def clear_history(self):
        """Clear download history"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump([], f)
            return True
        except Exception as e:
            return False
    
    def search_history(self, query):
        """Search download history"""
        try:
            history = self.load_history()
            query_lower = query.lower()
            
            results = []
            for item in history:
                if (query_lower in item.get('filename', '').lower() or
                    query_lower in item.get('url', '').lower() or
                    query_lower in item.get('type', '').lower()):
                    results.append(item)
            
            return results
            
        except Exception as e:
            return []


class FileUtils:
    """File utility functions"""
    
    @staticmethod
    def format_size(bytes_size):
        """Format file size in human readable format"""
        if not bytes_size:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"
    
    @staticmethod
    def format_speed(bytes_per_second):
        """Format download speed in human readable format"""
        return f"{FileUtils.format_size(bytes_per_second)}/s"
    
    @staticmethod
    def format_time(seconds):
        """Format time duration"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes:.0f}m {secs:.0f}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours:.0f}h {minutes:.0f}m"
    
    @staticmethod
    def sanitize_filename(filename):
        """Sanitize filename for safe saving"""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Remove leading/trailing spaces and dots
        filename = filename.strip(' .')
        
        # Limit length
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200-len(ext)] + ext
        
        return filename or "download"
    
    @staticmethod
    def ensure_directory(path):
        """Ensure directory exists"""
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except Exception as e:
            print(f"Error creating directory {path}: {e}")
            return False
    
    @staticmethod
    def get_available_filename(filepath):
        """Get available filename if file already exists"""
        if not os.path.exists(filepath):
            return filepath
        
        base, ext = os.path.splitext(filepath)
        counter = 1
        
        while os.path.exists(f"{base}_{counter}{ext}"):
            counter += 1
        
        return f"{base}_{counter}{ext}"
    
    @staticmethod
    def calculate_checksum(filepath, algorithm='md5'):
        """Calculate file checksum"""
        import hashlib
        
        try:
            hash_obj = hashlib.new(algorithm)
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except Exception as e:
            return None