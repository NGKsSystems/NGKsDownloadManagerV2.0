"""
YouTube and Multi-Site Video Downloader
Uses yt-dlp for downloading videos from YouTube, Twitter, Instagram, TikTok, etc.
"""

import os
import yt_dlp
import threading
import time
from pathlib import Path
import json

class YouTubeDownloader:
    def __init__(self):
        self.active_downloads = {}
        
    def check_existing_download(self, url, destination):
        """Check if video is already downloaded or partially downloaded"""
        try:
            # Get video info to determine filename
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'outtmpl': os.path.join(destination, '%(title)s.%(ext)s'),
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None
                
                # Generate the expected filename
                filename = ydl.prepare_filename(info)
                partial_filename = filename + '.part'
                
                # Check for complete file
                if os.path.exists(filename):
                    return {
                        'status': 'complete',
                        'filepath': filename,
                        'filename': os.path.basename(filename),
                        'size': os.path.getsize(filename)
                    }
                
                # Check for partial file
                if os.path.exists(partial_filename):
                    return {
                        'status': 'partial', 
                        'filepath': partial_filename,
                        'filename': os.path.basename(filename),
                        'size': os.path.getsize(partial_filename)
                    }
                
                return None
                
        except Exception as e:
            return None
    
    def download(self, url, destination, progress_callback=None, extract_audio=False, auto_quality=True, quality="best"):
        """
        Download video from supported sites using yt-dlp
        
        Args:
            url: Video URL
            destination: Destination folder
            progress_callback: Function to call with progress updates
            extract_audio: Extract audio only
            auto_quality: Auto-select best quality
            quality: Quality preference if not auto
            
        Returns:
            bool: True if download successful, False otherwise
        """
        try:
            # Create destination directory
            os.makedirs(destination, exist_ok=True)
            
            # Check for existing download
            existing = self.check_existing_download(url, destination)
            if existing and existing['status'] == 'complete':
                if progress_callback:
                    progress_callback({
                        'filename': existing['filename'],
                        'progress': "100%",
                        'speed': "0 B/s",
                        'status': 'Already downloaded'
                    })
                return {
                    'status': 'success',
                    'filepath': existing['filepath'],
                    'filename': existing['filename'],
                    'url': url,
                    'resumed': False
                }
            
            # Configure yt-dlp options
            ydl_opts = {
                'outtmpl': os.path.join(destination, '%(title)s.%(ext)s'),
                'progress_hooks': [self._progress_hook],
                'extract_flat': False,
                'writethumbnail': True,
                'writeinfojson': True,
                'continue_dl': True,  # Resume incomplete downloads
                'part': True,  # Keep partial files for resume
                'retries': 3,  # Retry failed downloads
                'fragment_retries': 3,  # Retry failed fragments
                'ignoreerrors': False,  # Don't ignore errors
            }
            
            # Configure quality settings
            if extract_audio:
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })
            else:
                if auto_quality:
                    ydl_opts['format'] = 'best[height<=1080]/best'
                else:
                    ydl_opts['format'] = quality
            
            # Store callback for this download
            self.current_callback = progress_callback
            self.current_filename = "Preparing..."
            was_resumed = existing and existing['status'] == 'partial'
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Get video info first
                info = ydl.extract_info(url, download=False)
                self.current_filename = info.get('title', 'Unknown')
                
                if progress_callback:
                    status_msg = 'Resuming download' if was_resumed else 'Starting'
                    progress_callback({
                        'filename': self.current_filename,
                        'progress': "0%",
                        'speed': "0 B/s",
                        'status': status_msg
                    })
                
                # Download video
                ydl.download([url])
            
            if progress_callback:
                progress_callback({
                    'filename': self.current_filename,
                    'progress': "100%",
                    'speed': "0 B/s",
                    'status': 'Completed'
                })
            
            # Return proper result dictionary
            return {
                'status': 'success',
                'filepath': destination,
                'filename': self.current_filename,
                'url': url,
                'resumed': was_resumed
            }
            
        except Exception as e:
            error_msg = str(e)
            
            # Provide more helpful error messages
            if "Video unavailable" in error_msg:
                error_msg = "Video is unavailable (private, deleted, or region-blocked)"
            elif "Sign in to confirm your age" in error_msg:
                error_msg = "Age-restricted video requires sign-in"
            elif "This video is not available" in error_msg:
                error_msg = "Video is not available in your region"
            elif "Unable to extract" in error_msg:
                error_msg = "Unable to extract video information (unsupported format or site)"
            elif "HTTP Error 429" in error_msg:
                error_msg = "Rate limited - too many requests. Try again later"
            elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                error_msg = "Network connection error - check your internet connection"
            
            if progress_callback:
                progress_callback({
                    'filename': getattr(self, 'current_filename', 'Unknown'),
                    'progress': "0%",
                    'speed': "0 B/s",
                    'status': f'Error: {error_msg}'
                })
            return {
                'status': 'error',
                'error': error_msg,
                'filename': getattr(self, 'current_filename', 'Unknown'),
                'url': url
            }
    
    def _progress_hook(self, d):
        """Progress hook for yt-dlp"""
        if not hasattr(self, 'current_callback') or not self.current_callback:
            return
        
        if d['status'] == 'downloading':
            filename = os.path.basename(d.get('filename', self.current_filename))
            
            # Calculate progress and format display
            downloaded_bytes = d.get('downloaded_bytes', 0)
            
            if 'total_bytes' in d and d['total_bytes']:
                total_bytes = d['total_bytes']
                progress = (downloaded_bytes / total_bytes) * 100
                progress_str = f"{progress:.1f}%"
                # Enhanced filename with size info like HF downloader
                filename_display = f"{filename} ({self._format_size(downloaded_bytes)}/{self._format_size(total_bytes)})"
            elif 'total_bytes_estimate' in d and d['total_bytes_estimate']:
                total_bytes = d['total_bytes_estimate'] 
                progress = (downloaded_bytes / total_bytes) * 100
                progress_str = f"{progress:.1f}%"
                filename_display = f"{filename} (~{self._format_size(downloaded_bytes)}/{self._format_size(total_bytes)})"
            else:
                progress_str = f"{self._format_size(downloaded_bytes)}"
                filename_display = f"{filename} ({progress_str})"
            
            # Calculate speed with ETA
            speed_str = "0 B/s"
            if 'speed' in d and d['speed']:
                speed_bytes = d['speed']
                speed_str = f"{self._format_size(speed_bytes)}/s"
                
                # Calculate ETA if we have total size
                if ('total_bytes' in d or 'total_bytes_estimate' in d) and speed_bytes > 0:
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    if total > downloaded_bytes:
                        remaining_bytes = total - downloaded_bytes
                        eta_seconds = remaining_bytes / speed_bytes
                        eta_str = self._format_time(eta_seconds)
                        speed_str = f"{self._format_size(speed_bytes)}/s - ETA: {eta_str}"
            
            self.current_callback({
                'filename': filename_display,
                'progress': progress_str,
                'speed': speed_str,
                'status': 'Downloading'
            })
        
        elif d['status'] == 'finished':
            filename = os.path.basename(d.get('filename', self.current_filename))
            self.current_callback({
                'filename': filename,
                'progress': "100%",
                'speed': "0 B/s",
                'status': 'Processing'
            })
    
    def get_video_info(self, url):
        """Get video information without downloading"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Extract relevant information
                video_info = {
                    'title': info.get('title', 'Unknown'),
                    'uploader': info.get('uploader', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'view_count': info.get('view_count', 0),
                    'description': info.get('description', ''),
                    'thumbnail': info.get('thumbnail', ''),
                    'formats': []
                }
                
                # Get available formats
                if 'formats' in info:
                    for fmt in info['formats']:
                        if fmt.get('vcodec') != 'none':  # Video formats
                            format_info = {
                                'format_id': fmt.get('format_id', ''),
                                'ext': fmt.get('ext', ''),
                                'quality': fmt.get('height', 0),
                                'fps': fmt.get('fps', 0),
                                'filesize': fmt.get('filesize', 0),
                                'vcodec': fmt.get('vcodec', ''),
                                'acodec': fmt.get('acodec', ''),
                                'format_note': fmt.get('format_note', '')
                            }
                            video_info['formats'].append(format_info)
                
                return video_info
                
        except Exception as e:
            return None
    
    def get_supported_sites(self):
        """Get list of supported sites"""
        try:
            return yt_dlp.extractor.gen_extractors()
        except:
            # Return common supported sites
            return [
                'YouTube', 'Twitter', 'Instagram', 'TikTok', 'Facebook',
                'Vimeo', 'Dailymotion', 'Reddit', 'Twitch', 'SoundCloud'
            ]
    
    def is_supported_url(self, url):
        """Check if URL is supported by yt-dlp"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Try to extract info without downloading
                ydl.extract_info(url, download=False)
                return True
        except:
            return False
    
    def get_available_qualities(self, url):
        """Get available video qualities for a URL"""
        try:
            video_info = self.get_video_info(url)
            if not video_info or not video_info.get('formats'):
                return []
            
            qualities = []
            seen_qualities = set()
            
            for fmt in video_info['formats']:
                quality = fmt.get('quality', 0)
                if quality > 0 and quality not in seen_qualities:
                    quality_str = f"{quality}p"
                    if fmt.get('fps', 0) > 30:
                        quality_str += f" {fmt['fps']}fps"
                    
                    qualities.append({
                        'format_id': fmt.get('format_id'),
                        'quality': quality_str,
                        'filesize': self._format_size(fmt.get('filesize', 0)) if fmt.get('filesize') else 'Unknown',
                        'ext': fmt.get('ext', ''),
                        'vcodec': fmt.get('vcodec', ''),
                        'acodec': fmt.get('acodec', '')
                    })
                    seen_qualities.add(quality)
            
            # Sort by quality (highest first)
            qualities.sort(key=lambda x: int(x['quality'].split('p')[0]), reverse=True)
            
            return qualities
            
        except Exception as e:
            return []
    
    def _format_size(self, bytes_size):
        """Format file size in human readable format"""
        if not bytes_size:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"
    
    def _format_time(self, seconds):
        """Format time in human readable format"""
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
    
    def download_with_format(self, url, destination, format_id, progress_callback=None):
        """Download video with specific format"""
        try:
            os.makedirs(destination, exist_ok=True)
            
            ydl_opts = {
                'outtmpl': os.path.join(destination, '%(title)s.%(ext)s'),
                'progress_hooks': [self._progress_hook],
                'format': format_id,
                'writethumbnail': True,
                'writeinfojson': True,
                'continue_dl': True,  # Resume incomplete downloads
                'part': True,  # Keep partial files for resume
                'retries': 3,  # Retry failed downloads
                'fragment_retries': 3,  # Retry failed fragments
                'ignoreerrors': False,  # Don't ignore errors
            }
            
            self.current_callback = progress_callback
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                self.current_filename = info.get('title', 'Unknown')
                
                if progress_callback:
                    progress_callback({
                        'filename': self.current_filename,
                        'progress': "0%",
                        'speed': "0 B/s",
                        'status': 'Starting'
                    })
                
                ydl.download([url])
            
            return {
                'status': 'success',
                'filepath': destination,
                'filename': self.current_filename,
                'url': url
            }
            
        except Exception as e:
            error_msg = str(e)
            if progress_callback:
                progress_callback({
                    'filename': getattr(self, 'current_filename', 'Unknown'),
                    'progress': "0%",
                    'speed': "0 B/s",
                    'status': f'Error: {error_msg}'
                })
            return {
                'status': 'error',
                'error': error_msg,
                'filename': getattr(self, 'current_filename', 'Unknown'),
                'url': url
            }