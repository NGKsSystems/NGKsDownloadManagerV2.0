"""
YouTube and Multi-Site Video Downloader
Uses yt-dlp for downloading videos from YouTube, Twitter/X, Instagram, TikTok, etc.

Adds Twitter/X support via cookies + headers:
- DL_COOKIES_BROWSER = edge|chrome|firefox|brave|opera (default edge)
- DL_COOKIEFILE = full path to cookies.txt (Netscape format)
- DL_FFMPEG_LOCATION = folder containing ffmpeg.exe or full path to ffmpeg.exe (optional)
"""

import os
import yt_dlp
import json
import re
from pathlib import Path


class YouTubeDownloader:
    def __init__(self):
        self.active_downloads = {}

    # -----------------------------
    # Helpers
    # -----------------------------
    @staticmethod
    def _is_twitter(url: str) -> bool:
        u = (url or "").lower()
        return ("twitter.com" in u) or ("x.com" in u)

    @staticmethod
    def _map_quality_to_format(quality: str) -> str:
        """Map UI quality preset to a yt-dlp format selector string."""
        _PRESETS = {
            "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "720":  "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "480":  "bestvideo[height<=480]+bestaudio/best[height<=480]",
            "360":  "bestvideo[height<=360]+bestaudio/best[height<=360]",
            "240":  "bestvideo[height<=240]+bestaudio/best[height<=240]",
        }
        return _PRESETS.get(quality, "best[height<=1080]/best")

    @staticmethod
    def _is_youtube(url: str) -> bool:
        u = (url or "").lower()
        return ("youtube.com" in u) or ("youtu.be" in u)
    
    @staticmethod
    def _is_youtube_shorts(url: str) -> bool:
        u = (url or "").lower()
        return ("/shorts/" in u) and YouTubeDownloader._is_youtube(url)
    
    @staticmethod
    def _convert_shorts_to_watch_url(url: str) -> str:
        """Convert YouTube Shorts URL to regular watch URL for better compatibility"""
        if not url:
            return url
            
        original_url = url
        
        # Handle different YouTube Shorts URL formats:
        # https://youtube.com/shorts/VIDEO_ID
        # https://www.youtube.com/shorts/VIDEO_ID
        # https://m.youtube.com/shorts/VIDEO_ID
        # https://youtu.be/shorts/VIDEO_ID (less common)
        # URLs with parameters: ...?feature=share&t=30
        
        # More comprehensive regex pattern
        shorts_patterns = [
            r'(?:https?://)?(?:www\.|m\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?youtu\.be/shorts/([a-zA-Z0-9_-]{11})'
        ]
        
        video_id = None
        for pattern in shorts_patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                video_id = match.group(1)
                break
        
        if video_id:
            # Always use standard YouTube format
            converted_url = f"https://www.youtube.com/watch?v={video_id}"
            return converted_url
        
        return original_url

    @staticmethod
    def _ffmpeg_opts() -> dict:
        ff = os.environ.get("DL_FFMPEG_LOCATION", "").strip()
        return {"ffmpeg_location": ff} if ff else {}

    @staticmethod
    def _cookie_and_header_opts(url: str) -> dict:
        """
        Twitter/X often requires authenticated cookies to fetch HLS playlists.
        Prefer DL_COOKIEFILE (most reliable for an app). Otherwise use cookies-from-browser.
        Default browser is EDGE (avoids Chrome cookie DB lock issues).
        """
        if not YouTubeDownloader._is_twitter(url):
            return {}

        opts = {}

        cookiefile = os.environ.get("DL_COOKIEFILE", "").strip()
        if cookiefile:
            opts["cookiefile"] = cookiefile
        else:
            browser = os.environ.get("DL_COOKIES_BROWSER", "edge").strip().lower()
            opts["cookiesfrombrowser"] = (browser,)

        # Browser-like headers help on X
        opts["http_headers"] = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://x.com/",
        }

        # X frequently serves segmented HLS; tune for stability
        opts["concurrent_fragment_downloads"] = 1
        opts["retries"] = 10
        opts["fragment_retries"] = 10
        opts["sleep_interval"] = 1
        opts["max_sleep_interval"] = 5

        return opts

    def _base_ydl_opts(self, url: str, destination: str) -> dict:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "outtmpl": os.path.join(destination, "%(title)s.%(ext)s"),
        }
        ydl_opts.update(self._cookie_and_header_opts(url))
        ydl_opts.update(self._ffmpeg_opts())
        
        # Add YouTube-specific options to prevent 403 errors
        if self._is_youtube(url):
            # Use browser cookies for YouTube (helps with age-restricted/member content)
            cookiefile = os.environ.get("DL_COOKIEFILE", "").strip()
            if cookiefile:
                ydl_opts["cookiefile"] = cookiefile
            else:
                # Try to get cookies from browser (edge is most reliable on Windows)
                browser = os.environ.get("DL_COOKIES_BROWSER", "edge").strip().lower()
                ydl_opts["cookiesfrombrowser"] = (browser,)
            
            # Add browser-like headers for YouTube
            ydl_opts["http_headers"] = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-us,en;q=0.5",
                "Sec-Fetch-Mode": "navigate",
            }
            
            # Special handling for YouTube Shorts
            if self._is_youtube_shorts(url):
                # Shorts often need more aggressive retry settings
                ydl_opts.update({
                    "retries": 15,
                    "fragment_retries": 15,
                    "sleep_interval": 2,
                    "max_sleep_interval": 10,
                    "sleep_interval_requests": 1,
                    "sleep_interval_subtitles": 1,
                    # Use mobile user agent for better Shorts compatibility
                    "http_headers": {
                        "User-Agent": (
                            "Mozilla/5.0 (Linux; Android 11; Pixel 5) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/90.0.4430.91 Mobile Safari/537.36"
                        ),
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-us,en;q=0.5",
                        "Sec-Fetch-Mode": "navigate",
                    }
                })
        
        return ydl_opts

    # -----------------------------
    # Existing download check
    # -----------------------------
    def check_existing_download(self, url, destination):
        """Check if video is already downloaded or partially downloaded"""
        try:
            os.makedirs(destination, exist_ok=True)

            ydl_opts = self._base_ydl_opts(url, destination)

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None

                filename = ydl.prepare_filename(info)
                partial_filename = filename + ".part"

                if os.path.exists(filename):
                    return {
                        "status": "complete",
                        "filepath": filename,
                        "filename": os.path.basename(filename),
                        "size": os.path.getsize(filename),
                    }

                if os.path.exists(partial_filename):
                    return {
                        "status": "partial",
                        "filepath": partial_filename,
                        "filename": os.path.basename(filename),
                        "size": os.path.getsize(partial_filename),
                    }

                return None

        except Exception:
            return None

    # -----------------------------
    # Download
    # -----------------------------
    def download(self, url, destination, progress_callback=None, extract_audio=False, auto_quality=True, quality="best"):
        """
        Download video from supported sites using yt-dlp
        """
        try:
            # Auto-convert Shorts URLs to regular YouTube URLs for better compatibility
            original_url = url
            url = self._convert_shorts_to_watch_url(url)
            
            # Notify user if URL was converted
            if url != original_url:
                if progress_callback:
                    progress_callback({
                        "filename": "Converting Shorts URL...",
                        "progress": "0%",
                        "speed": "0 B/s",
                        "status": f"Shorts URL detected, converting to: {url[:80]}...",
                    })
                print(f"[DEBUG] Converted Shorts URL:")
                print(f"[DEBUG] From: {original_url}")
                print(f"[DEBUG] To: {url}")
            
            os.makedirs(destination, exist_ok=True)

            existing = self.check_existing_download(url, destination)
            if existing and existing["status"] == "complete":
                if progress_callback:
                    progress_callback({
                        "filename": existing["filename"],
                        "progress": "100%",
                        "speed": "0 B/s",
                        "status": "Already downloaded",
                    })
                return {
                    "status": "success",
                    "filepath": existing["filepath"],
                    "filename": existing["filename"],
                    "url": url,
                    "resumed": False,
                }

            # Configure yt-dlp options
            ydl_opts = self._base_ydl_opts(url, destination)
            ydl_opts.update({
                "progress_hooks": [self._progress_hook],
                "extract_flat": False,
                "continue_dl": True,
                "part": True,
                "ignoreerrors": False,
                # Explicitly disable extra files for ALL downloads
                "writethumbnail": False,
                "writeinfojson": False,
                "writesubtitles": False,
                "writeautomaticsub": False,
                "writedescription": False,
                "writeannotations": False,
            })

            # Configure quality and format based on download type
            if extract_audio:
                # For audio-only downloads
                ydl_opts.update({
                    "format": "bestaudio[ext=m4a]/bestaudio/best",
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }],
                })
            else:
                # For video downloads
                if auto_quality:
                    ydl_opts["format"] = "best[height<=1080]/best"
                else:
                    ydl_opts["format"] = self._map_quality_to_format(quality)

            import logging
            logging.getLogger("youtube_downloader").info(
                f"YT.FORMAT.SELECTED | quality={quality} | auto_quality={auto_quality}"
                f" | extract_audio={extract_audio} | format={ydl_opts['format']}"
            )

            self.current_callback = progress_callback
            self.current_filename = "Preparing..."
            was_resumed = bool(existing and existing.get("status") == "partial")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                self.current_filename = (info or {}).get("title", "Unknown")

                if progress_callback:
                    progress_callback({
                        "filename": self.current_filename,
                        "progress": "0%",
                        "speed": "0 B/s",
                        "status": ("Resuming download" if was_resumed else "Starting"),
                    })

                ydl.download([url])

            if progress_callback:
                progress_callback({
                    "filename": self.current_filename,
                    "progress": "100%",
                    "speed": "0 B/s",
                    "status": "Completed",
                })

            return {
                "status": "success",
                "filepath": destination,
                "filename": self.current_filename,
                "url": url,
                "resumed": was_resumed,
            }

        except Exception as e:
            error_msg = str(e)

            # Improve common errors
            if "Could not copy" in error_msg and "cookie database" in error_msg:
                error_msg = (
                    "Cookie DB is locked. If using Chrome cookies, close Chrome or switch to Edge.\n"
                    "Set DL_COOKIES_BROWSER=edge or use DL_COOKIEFILE."
                )
            elif "Video unavailable" in error_msg:
                error_msg = "Video is unavailable (private, deleted, or region-blocked)"
            elif "Unable to extract" in error_msg:
                if self._is_youtube_shorts(url):
                    error_msg = "Unable to extract Shorts video. Try using the full YouTube URL instead of the Shorts URL"
                else:
                    error_msg = "Unable to extract video information (unsupported format or site)"
            elif "HTTP Error 429" in error_msg:
                error_msg = "Rate limited - too many requests. Try again later"
            elif "HTTP Error 403" in error_msg and self._is_youtube_shorts(url):
                error_msg = "Access denied for YouTube Shorts. Try using browser cookies or the full YouTube URL"
            elif "Sign in to confirm" in error_msg or "age-restricted" in error_msg.lower():
                error_msg = "Age-restricted content. Browser cookies required for access"

            if progress_callback:
                progress_callback({
                    "filename": getattr(self, "current_filename", "Unknown"),
                    "progress": "0%",
                    "speed": "0 B/s",
                    "status": f"Error: {error_msg}",
                })

            return {
                "status": "error",
                "error": error_msg,
                "filename": getattr(self, "current_filename", "Unknown"),
                "url": url,
            }

    # -----------------------------
    # Progress hook
    # -----------------------------
    def _progress_hook(self, d):
        if not hasattr(self, "current_callback") or not self.current_callback:
            return

        if d.get("status") == "downloading":
            filename = os.path.basename(d.get("filename", self.current_filename))
            downloaded_bytes = d.get("downloaded_bytes", 0)

            if d.get("total_bytes"):
                total_bytes = d["total_bytes"]
                progress = (downloaded_bytes / total_bytes) * 100
                progress_str = f"{progress:.1f}%"
                filename_display = f"{filename} ({self._format_size(downloaded_bytes)}/{self._format_size(total_bytes)})"
            elif d.get("total_bytes_estimate"):
                total_bytes = d["total_bytes_estimate"]
                progress = (downloaded_bytes / total_bytes) * 100
                progress_str = f"{progress:.1f}%"
                filename_display = f"{filename} (~{self._format_size(downloaded_bytes)}/{self._format_size(total_bytes)})"
            else:
                progress_str = f"{self._format_size(downloaded_bytes)}"
                filename_display = f"{filename} ({progress_str})"

            speed = d.get("speed", 0) or 0
            speed_str = self._format_size(speed) + "/s" if speed else "0 B/s"

            # Pass raw yt-dlp dict with additional fields for enhanced progress parsing
            progress_info = {
                "filename": filename_display,
                "progress": progress_str,  # Keep for compatibility
                "speed": speed_str,
                "status": "Downloading",
                # Add raw yt-dlp fields for byte-based progress calculation
                "percent": progress_str,
                "downloaded_bytes": downloaded_bytes,
                "total_bytes": d.get("total_bytes"),
                "total_bytes_estimate": d.get("total_bytes_estimate")
            }
            
            self.current_callback(progress_info)

        elif d.get("status") == "finished":
            self.current_callback({
                "filename": getattr(self, "current_filename", "Unknown"),
                "progress": "100%",
                "speed": "0 B/s",
                "status": "Processing",
            })

    @staticmethod
    def _format_size(num_bytes: float) -> str:
        try:
            num = float(num_bytes)
        except Exception:
            return "0 B"

        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if num < 1024.0:
                return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} {unit}"
            num /= 1024.0
        return f"{num:.1f} PB"
