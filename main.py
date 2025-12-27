"""
NGK's Download Manager
A comprehensive download manager with support for:
- YouTube and multi-site video downloads (yt-dlp)
- Hugging Face model/dataset downloads
- Direct HTTP/HTTPS downloads
- Resume capability and progress tracking
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import threading
import os
import sys
import json
from urllib.parse import urlparse
import webbrowser
from datetime import datetime

# Import our custom modules
from download_manager import DownloadManager
from youtube_downloader import YouTubeDownloader
from huggingface_downloader import HuggingFaceDownloader
from utils import URLDetector, ConfigManager, HistoryManager
from dialogs import HuggingFaceInfoDialog, ThumbnailViewer, ProgressDialog

class DownloadManagerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("NGK's Download Manager v1.0")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)
        
        # Initialize managers
        self.config_manager = ConfigManager()
        self.history_manager = HistoryManager()
        self.download_manager = DownloadManager()
        self.youtube_downloader = YouTubeDownloader()
        self.hf_downloader = HuggingFaceDownloader()
        self.url_detector = URLDetector()
        self.thumbnail_viewer = ThumbnailViewer(self.root)
        
        # Download tracking
        self.active_downloads = {}
        self.download_counter = 0
        
        self.setup_ui()
        self.load_config()
        self.load_history()  # Load download history on startup
        
    def setup_ui(self):
        """Setup the main user interface"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Download tab
        self.download_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.download_frame, text="Downloads")
        self.setup_download_tab()
        
        # Settings tab
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="Settings")
        self.setup_settings_tab()
        
        # History tab
        self.history_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.history_frame, text="History")
        self.setup_history_tab()
        
    def setup_download_tab(self):
        """Setup the main download interface"""
        # URL input section
        url_frame = ttk.LabelFrame(self.download_frame, text="Download URL", padding=10)
        url_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var, font=("Arial", 11))
        self.url_entry.pack(fill=tk.X, pady=(0, 10))
        self.url_entry.bind('<Return>', self.on_url_enter)
        
        # URL analysis display
        self.url_info_var = tk.StringVar()
        self.url_info_label = ttk.Label(url_frame, textvariable=self.url_info_var, foreground="blue")
        self.url_info_label.pack(anchor=tk.W)
        
        # Bind URL change event
        self.url_var.trace('w', self.on_url_change)
        
        # Download options frame
        options_frame = ttk.LabelFrame(self.download_frame, text="Download Options", padding=10)
        options_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Destination folder
        dest_frame = ttk.Frame(options_frame)
        dest_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(dest_frame, text="Destination:").pack(side=tk.LEFT)
        self.dest_var = tk.StringVar(value=os.path.expanduser("~/Downloads"))
        self.dest_entry = ttk.Entry(dest_frame, textvariable=self.dest_var, state="readonly")
        self.dest_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 10))
        ttk.Button(dest_frame, text="Browse", command=self.browse_destination).pack(side=tk.RIGHT)
        
        # Download button
        button_frame = ttk.Frame(options_frame)
        button_frame.pack(fill=tk.X)
        
        self.download_btn = ttk.Button(button_frame, text="Download", command=self.start_download, style="Accent.TButton")
        self.download_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.paste_btn = ttk.Button(button_frame, text="Paste URL", command=self.paste_url)
        self.paste_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.clear_btn = ttk.Button(button_frame, text="Clear", command=self.clear_url)
        self.clear_btn.pack(side=tk.LEFT)
        
        # Progress section
        progress_frame = ttk.LabelFrame(self.download_frame, text="Download Progress", padding=10)
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Downloads list
        columns = ("ID", "Filename", "URL Type", "Progress", "Speed", "Status")
        self.downloads_tree = ttk.Treeview(progress_frame, columns=columns, show="tree headings", height=8)
        
        # Configure columns
        self.downloads_tree.heading("#0", text="")
        self.downloads_tree.column("#0", width=0, stretch=False)
        
        for col in columns:
            self.downloads_tree.heading(col, text=col)
            if col == "Filename":
                self.downloads_tree.column(col, width=200)
            elif col == "Progress":
                self.downloads_tree.column(col, width=100)
            else:
                self.downloads_tree.column(col, width=80)
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(progress_frame, orient=tk.VERTICAL, command=self.downloads_tree.yview)
        self.downloads_tree.configure(yscrollcommand=scrollbar.set)
        
        self.downloads_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Context menu for downloads
        self.setup_context_menu()
        
    def setup_settings_tab(self):
        """Setup the settings interface"""
        # Hugging Face settings
        hf_frame = ttk.LabelFrame(self.settings_frame, text="Hugging Face Settings", padding=10)
        hf_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(hf_frame, text="HF Token:").pack(anchor=tk.W)
        self.hf_token_var = tk.StringVar()
        token_frame = ttk.Frame(hf_frame)
        token_frame.pack(fill=tk.X, pady=(5, 10))
        
        self.hf_token_entry = ttk.Entry(token_frame, textvariable=self.hf_token_var, show="*")
        self.hf_token_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        ttk.Button(token_frame, text="Test Token", command=self.test_hf_token).pack(side=tk.RIGHT)
        
        # YouTube settings
        yt_frame = ttk.LabelFrame(self.settings_frame, text="YouTube Settings", padding=10)
        yt_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.auto_quality = tk.BooleanVar(value=True)
        ttk.Checkbutton(yt_frame, text="Auto-select best quality", variable=self.auto_quality).pack(anchor=tk.W)
        
        self.extract_audio = tk.BooleanVar(value=False)
        ttk.Checkbutton(yt_frame, text="Extract audio only", variable=self.extract_audio).pack(anchor=tk.W)
        
        # General settings
        general_frame = ttk.LabelFrame(self.settings_frame, text="General Settings", padding=10)
        general_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(general_frame, text="Max concurrent downloads:").pack(anchor=tk.W)
        self.max_downloads_var = tk.IntVar(value=3)
        ttk.Spinbox(general_frame, from_=1, to=10, textvariable=self.max_downloads_var, width=10).pack(anchor=tk.W, pady=(5, 10))
        
        # Save settings button
        ttk.Button(self.settings_frame, text="Save Settings", command=self.save_config).pack(pady=20)
        
    def setup_history_tab(self):
        """Setup the download history interface"""
        # History list
        history_columns = ("Date", "Filename", "URL", "Status", "Size")
        self.history_tree = ttk.Treeview(self.history_frame, columns=history_columns, show="headings")
        
        for col in history_columns:
            self.history_tree.heading(col, text=col)
            if col == "Filename":
                self.history_tree.column(col, width=200)
            elif col == "URL":
                self.history_tree.column(col, width=300)
            else:
                self.history_tree.column(col, width=100)
        
        # Scrollbar for history
        history_scrollbar = ttk.Scrollbar(self.history_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scrollbar.set)
        
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)
        
        # History buttons
        history_btn_frame = ttk.Frame(self.history_frame)
        history_btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Button(history_btn_frame, text="Clear History", command=self.clear_history).pack(side=tk.LEFT)
        ttk.Button(history_btn_frame, text="Export History", command=self.export_history).pack(side=tk.LEFT, padx=(10, 0))
        
    def setup_context_menu(self):
        """Setup context menu for downloads"""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Pause", command=self.pause_download)
        self.context_menu.add_command(label="Resume", command=self.resume_download)
        self.context_menu.add_command(label="Cancel", command=self.cancel_download)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Open File", command=self.open_file)
        self.context_menu.add_command(label="Open Folder", command=self.open_folder)
        
        self.downloads_tree.bind("<Button-3>", self.show_context_menu)
        
    def on_url_change(self, *args):
        """Handle URL input change"""
        url = self.url_var.get().strip()
        if url:
            url_type = self.url_detector.detect_url_type(url)
            self.url_info_var.set(f"Detected: {url_type}")
        else:
            self.url_info_var.set("")
    
    def on_url_enter(self, event):
        """Handle Enter key in URL entry"""
        self.start_download()
    
    def paste_url(self):
        """Paste URL from clipboard"""
        try:
            clipboard = self.root.clipboard_get()
            if clipboard:
                self.url_var.set(clipboard.strip())
        except tk.TclError:
            pass
    
    def clear_url(self):
        """Clear URL input"""
        self.url_var.set("")
        self.url_info_var.set("")
    
    def browse_destination(self):
        """Browse for destination folder"""
        folder = filedialog.askdirectory(initialdir=self.dest_var.get())
        if folder:
            self.dest_var.set(folder)
    
    def start_download(self):
        """Start a new download with enhanced features"""
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a URL to download")
            return
        
        destination = self.dest_var.get()
        if not os.path.exists(destination):
            os.makedirs(destination, exist_ok=True)
        
        # Detect URL type and show appropriate options
        url_type = self.url_detector.detect_url_type(url)
        
        # Handle different URL types with enhanced features
        if url_type == "YouTube":
            self._handle_youtube_download(url, destination)
        elif url_type == "Hugging Face":
            self._handle_hf_download(url, destination)
        elif url_type in ["Twitter", "Instagram", "TikTok", "Facebook", "Video Site"]:
            self._handle_video_download(url, destination, url_type)
        else:
            self._handle_direct_download(url, destination, url_type)
    
    def _handle_youtube_download(self, url, destination):
        """Handle YouTube download with simple quality selection"""
        # Show simple quality selection dialog
        quality_options = [
            ("Best Quality", "best"),
            ("720p", "720p"),
            ("480p", "480p"), 
            ("Audio Only (MP3)", "audio"),
            ("Auto (Best Available)", "auto")
        ]
        
        # Create simple selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Quality")
        dialog.geometry("350x300")  # Increased height
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (350 // 2)
        y = (dialog.winfo_screenheight() // 2) - (300 // 2)  # Updated for new height
        dialog.geometry(f"350x300+{x}+{y}")
        
        result = {"quality": None, "audio_only": False}
        
        # Title
        ttk.Label(dialog, text="Select Download Quality:", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Quality selection
        quality_var = tk.StringVar(value="auto")
        
        # Create frame for radio buttons to better control spacing
        radio_frame = ttk.Frame(dialog)
        radio_frame.pack(pady=10, padx=20, fill=tk.X)
        
        for text, value in quality_options:
            ttk.Radiobutton(radio_frame, text=text, variable=quality_var, value=value).pack(anchor=tk.W, pady=3)
        
        # Buttons frame
        button_frame = ttk.Frame(dialog)
        button_frame.pack(side=tk.BOTTOM, pady=15)
        
        def on_download():
            selected = quality_var.get()
            result["quality"] = selected
            result["audio_only"] = (selected == "audio")
            print(f"User selected: {selected}, audio_only: {result['audio_only']}")  # Debug
            dialog.destroy()
        
        def on_cancel():
            print("User cancelled")  # Debug
            dialog.destroy()
        
        # Create buttons with better styling
        download_btn = ttk.Button(button_frame, text="Download", command=on_download)
        download_btn.pack(side=tk.LEFT, padx=10)
        
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=on_cancel)
        cancel_btn.pack(side=tk.LEFT, padx=10)
        
        # Make Download button default
        download_btn.focus_set()
        dialog.bind('<Return>', lambda e: on_download())
        
        # Wait for dialog
        self.root.wait_window(dialog)
        
        if result["quality"]:
            # Start download with selected options
            download_id = self.download_counter
            self.download_counter += 1
            
            item_id = self.downloads_tree.insert("", tk.END, values=(
                download_id, "Preparing...", "YouTube", "0%", "0 B/s", "Starting"
            ))
            
            self.active_downloads[download_id] = {
                'item_id': item_id,
                'url': url,
                'type': 'YouTube',
                'destination': destination,
                'status': 'starting',
                'options': result
            }
            
            # Start download with selected format
            thread = threading.Thread(
                target=self._youtube_download_worker,
                args=(download_id, url, destination, result),
                daemon=True
            )
            thread.start()
    
    def _handle_hf_download(self, url, destination):
        """Handle Hugging Face download with repo info"""
        # Parse HF URL first
        repo_info_raw = self.hf_downloader._parse_hf_url(url)
        
        if not repo_info_raw:
            messagebox.showerror("Error", "Invalid Hugging Face URL")
            return
        
        # If it's a direct file URL, start download immediately
        if repo_info_raw.get('filename'):
            self._start_hf_file_download(url, destination, repo_info_raw)
            return
        
        # For repository URLs, show info dialog
        progress_dialog = ProgressDialog(self.root, "Getting repository information...")
        
        def get_repo_info():
            try:
                progress_dialog.update_status("Fetching repository details...")
                
                repo_info = self.hf_downloader.get_repository_info(
                    repo_info_raw['repo_id'], 
                    repo_info_raw['repo_type']
                )
                
                self.root.after(0, progress_dialog.close)
                
                if repo_info:
                    self.root.after(0, self._show_hf_dialog, url, destination, repo_info)
                else:
                    self.root.after(0, lambda: messagebox.showerror("Error", "Could not get repository information. The repository might be private or not exist."))
                    
            except Exception as e:
                self.root.after(0, progress_dialog.close)
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to get repository info: {str(e)}"))
        
        threading.Thread(target=get_repo_info, daemon=True).start()
    
    def _start_hf_file_download(self, url, destination, repo_info):
        """Start direct file download from Hugging Face"""
        download_id = self.download_counter
        self.download_counter += 1
        
        filename = repo_info.get('filename', 'Unknown File')
        
        item_id = self.downloads_tree.insert("", tk.END, values=(
            download_id, filename, "Hugging Face", "0%", "0 B/s", "Starting"
        ))
        
        self.active_downloads[download_id] = {
            'item_id': item_id,
            'url': url,
            'type': 'Hugging Face',
            'destination': destination,
            'status': 'starting',
            'options': {'type': 'file', 'filename': filename}
        }
        
        # Start download
        thread = threading.Thread(
            target=self._hf_download_worker,
            args=(download_id, url, destination, {'type': 'file'}),
            daemon=True
        )
        thread.start()
        
        self.clear_url()
    
    def _show_hf_dialog(self, url, destination, repo_info):
        """Show Hugging Face repository dialog"""
        dialog = HuggingFaceInfoDialog(self.root, repo_info, self.hf_downloader)
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            # Start download based on selection
            download_id = self.download_counter
            self.download_counter += 1
            
            item_id = self.downloads_tree.insert("", tk.END, values=(
                download_id, repo_info.get('repo_id', 'Unknown'), "Hugging Face", "0%", "0 B/s", "Starting"
            ))
            
            self.active_downloads[download_id] = {
                'item_id': item_id,
                'url': url,
                'type': 'Hugging Face',
                'destination': destination,
                'status': 'starting',
                'options': dialog.result
            }
            
            # Start download
            thread = threading.Thread(
                target=self._hf_download_worker,
                args=(download_id, url, destination, dialog.result),
                daemon=True
            )
            thread.start()
            
            self.clear_url()
    
    def _handle_video_download(self, url, destination, url_type):
        """Handle other video site downloads"""
        # For non-YouTube video sites, use yt-dlp with auto settings
        download_id = self.download_counter
        self.download_counter += 1
        
        item_id = self.downloads_tree.insert("", tk.END, values=(
            download_id, "Preparing...", url_type, "0%", "0 B/s", "Starting"
        ))
        
        self.active_downloads[download_id] = {
            'item_id': item_id,
            'url': url,
            'type': url_type,
            'destination': destination,
            'status': 'starting'
        }
        
        # Start download
        thread = threading.Thread(
            target=self.download_worker,
            args=(download_id, url, url_type, destination),
            daemon=True
        )
        thread.start()
        
        self.clear_url()
    
    def _handle_direct_download(self, url, destination, url_type):
        """Handle direct downloads"""
        download_id = self.download_counter
        self.download_counter += 1
        
        item_id = self.downloads_tree.insert("", tk.END, values=(
            download_id, "Preparing...", url_type, "0%", "0 B/s", "Starting"
        ))
        
        self.active_downloads[download_id] = {
            'item_id': item_id,
            'url': url,
            'type': url_type,
            'destination': destination,
            'status': 'starting'
        }
        
        # Start download
        thread = threading.Thread(
            target=self.download_worker,
            args=(download_id, url, url_type, destination),
            daemon=True
        )
        thread.start()
        
        self.clear_url()
    
    def _youtube_download_worker(self, download_id, url, destination, options):
        """Worker for YouTube downloads with simple quality selection"""
        try:
            def progress_callback(progress_info):
                self.root.after(0, self.update_progress, download_id, progress_info)
            
            quality = options.get('quality', 'auto')
            audio_only = options.get('audio_only', False)
            
            # Map quality options to yt-dlp format
            if quality == 'best':
                format_selector = 'best'
            elif quality == '720p':
                format_selector = 'best[height<=720]'
            elif quality == '480p':
                format_selector = 'best[height<=480]'
            elif quality == 'audio':
                audio_only = True
                format_selector = None
            else:  # auto
                format_selector = None
            
            if format_selector:
                # Use specific format
                result = self.youtube_downloader.download_with_format(
                    url, destination, format_selector, progress_callback
                )
            else:
                # Use default download method
                result = self.youtube_downloader.download(
                    url, destination, progress_callback,
                    extract_audio=audio_only,
                    auto_quality=True
                )
            
            # Handle the new dictionary result format
            if isinstance(result, dict) and result.get('status') == 'success':
                self.root.after(0, self.download_completed, download_id, result)
            else:
                self.root.after(0, self.download_failed, download_id)
                if isinstance(result, dict) and result.get('error'):
                    self.root.after(0, self.download_error, download_id, result['error'])
                
        except Exception as e:
            self.root.after(0, self.download_error, download_id, str(e))
    
    def _hf_download_worker(self, download_id, url, destination, options):
        """Worker for Hugging Face downloads"""
        try:
            def progress_callback(progress_info):
                self.root.after(0, self.update_progress, download_id, progress_info)
            
            result = self.hf_downloader.download(
                url, destination, progress_callback,
                token=self.hf_token_var.get()
            )
            
            # Handle the new dictionary result format
            if isinstance(result, dict) and result.get('status') == 'success':
                self.root.after(0, self.download_completed, download_id, result)
            else:
                self.root.after(0, self.download_failed, download_id)
                if isinstance(result, dict) and result.get('error'):
                    self.root.after(0, self.download_error, download_id, result['error'])
                
        except Exception as e:
            self.root.after(0, self.download_error, download_id, str(e))
    
    def download_worker(self, download_id, url, url_type, destination):
        """Worker thread for downloads"""
        try:
            def progress_callback(progress_info):
                self.root.after(0, self.update_progress, download_id, progress_info)
            
            if url_type in ["YouTube", "Twitter", "Instagram", "TikTok"]:
                result = self.youtube_downloader.download(
                    url, destination, progress_callback,
                    extract_audio=self.extract_audio.get(),
                    auto_quality=self.auto_quality.get()
                )
            elif url_type == "Hugging Face":
                result = self.hf_downloader.download(
                    url, destination, progress_callback,
                    token=self.hf_token_var.get()
                )
            else:  # Direct download
                result = self.download_manager.download(
                    url, destination, progress_callback
                )
            
            # Handle both boolean (legacy) and dictionary (new) result formats
            if isinstance(result, dict):
                if result.get('status') == 'success':
                    self.root.after(0, self.download_completed, download_id, result)
                else:
                    self.root.after(0, self.download_failed, download_id)
                    if result.get('error'):
                        self.root.after(0, self.download_error, download_id, result['error'])
            elif result:  # Legacy boolean True
                self.root.after(0, self.download_completed, download_id, None)
            else:  # Legacy boolean False
                self.root.after(0, self.download_failed, download_id)
                
        except Exception as e:
            self.root.after(0, self.download_error, download_id, str(e))
    
    def update_progress(self, download_id, progress_info):
        """Update progress in UI"""
        if download_id not in self.active_downloads:
            return
        
        download = self.active_downloads[download_id]
        item_id = download['item_id']
        
        # Update treeview
        current_values = list(self.downloads_tree.item(item_id)['values'])
        
        if len(current_values) >= 6:
            current_values[1] = progress_info.get('filename', current_values[1])
            current_values[3] = progress_info.get('progress', current_values[3])
            current_values[4] = progress_info.get('speed', current_values[4])
            current_values[5] = progress_info.get('status', current_values[5])
            
            self.downloads_tree.item(item_id, values=current_values)
    
    def download_completed(self, download_id, result=None):
        """Handle download completion"""
        if download_id not in self.active_downloads:
            return
        
        download = self.active_downloads[download_id]
        item_id = download['item_id']
        
        # Get the actual filename from result if available, otherwise from treeview
        if result and isinstance(result, dict) and result.get('filename'):
            actual_filename = result['filename']
        else:
            # Fallback to current treeview value
            current_values = list(self.downloads_tree.item(item_id)['values'])
            actual_filename = current_values[1] if len(current_values) > 1 else "Unknown"
        
        # Update treeview with final values
        current_values = list(self.downloads_tree.item(item_id)['values'])
        if len(current_values) >= 6:
            current_values[1] = actual_filename  # Use actual filename
            current_values[3] = "100%"
            current_values[5] = "Completed"
            self.downloads_tree.item(item_id, values=current_values)
        
        # Add to history with actual filename
        history_entry = {
            'filename': actual_filename,
            'url': download['url'],
            'type': download['type'],
            'destination': download['destination'],
            'status': 'Completed',
            'size': 'Unknown'  # Could be enhanced to get actual file size
        }
        self.history_manager.add_download(history_entry)
        self.load_history()  # Refresh history display
        
        # Clean up
        download['status'] = 'completed'
        
        # Show notification with actual filename
        messagebox.showinfo("Download Complete", f"Downloaded: {actual_filename}")
    
    def download_failed(self, download_id):
        """Handle download failure"""
        if download_id not in self.active_downloads:
            return
        
        download = self.active_downloads[download_id]
        item_id = download['item_id']
        
        # Update status
        current_values = list(self.downloads_tree.item(item_id)['values'])
        current_values[5] = "Failed"
        self.downloads_tree.item(item_id, values=current_values)
        
        download['status'] = 'failed'
    
    def download_error(self, download_id, error_msg):
        """Handle download error"""
        self.download_failed(download_id)
        messagebox.showerror("Download Error", f"Download failed: {error_msg}")
    
    def show_context_menu(self, event):
        """Show context menu for downloads"""
        item = self.downloads_tree.selection()[0] if self.downloads_tree.selection() else None
        if item:
            self.context_menu.post(event.x_root, event.y_root)
    
    def pause_download(self):
        """Pause selected download"""
        # TODO: Implement pause functionality
        messagebox.showinfo("Info", "Pause functionality coming soon!")
    
    def resume_download(self):
        """Resume selected download"""
        # TODO: Implement resume functionality
        messagebox.showinfo("Info", "Resume functionality coming soon!")
    
    def cancel_download(self):
        """Cancel selected download"""
        # TODO: Implement cancel functionality
        messagebox.showinfo("Info", "Cancel functionality coming soon!")
    
    def open_file(self):
        """Open downloaded file"""
        # TODO: Implement open file functionality
        messagebox.showinfo("Info", "Open file functionality coming soon!")
    
    def open_folder(self):
        """Open download folder"""
        selection = self.downloads_tree.selection()
        if selection:
            download_id = int(self.downloads_tree.item(selection[0])['values'][0])
            if download_id in self.active_downloads:
                folder = self.active_downloads[download_id]['destination']
                os.startfile(folder)
    
    def test_hf_token(self):
        """Test Hugging Face token validity"""
        token = self.hf_token_var.get().strip()
        if not token:
            messagebox.showwarning("Warning", "Please enter a Hugging Face token")
            return
        
        if self.hf_downloader.validate_token(token):
            messagebox.showinfo("Success", "Hugging Face token is valid!")
        else:
            messagebox.showerror("Error", "Invalid Hugging Face token")
    
    def save_config(self):
        """Save configuration settings"""
        config = {
            'hf_token': self.hf_token_var.get(),
            'auto_quality': self.auto_quality.get(),
            'extract_audio': self.extract_audio.get(),
            'max_downloads': self.max_downloads_var.get(),
            'destination': self.dest_var.get()
        }
        self.config_manager.save_config(config)
        messagebox.showinfo("Success", "Settings saved successfully!")
    
    def load_config(self):
        """Load configuration settings"""
        config = self.config_manager.load_config()
        if config:
            self.hf_token_var.set(config.get('hf_token', ''))
            self.auto_quality.set(config.get('auto_quality', True))
            self.extract_audio.set(config.get('extract_audio', False))
            self.max_downloads_var.set(config.get('max_downloads', 3))
            self.dest_var.set(config.get('destination', os.path.expanduser("~/Downloads")))
    
    def load_history(self):
        """Load and display download history"""
        # Clear existing items
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        # Load history from file
        history = self.history_manager.load_history()
        
        # Add items to tree (most recent first)
        for entry in reversed(history[-50:]):  # Show last 50 entries
            self.history_tree.insert("", 0, values=(
                entry.get('date', 'Unknown'),
                entry.get('filename', 'Unknown'),
                entry.get('url', '')[:50] + "..." if len(entry.get('url', '')) > 50 else entry.get('url', ''),
                entry.get('status', 'Unknown'),
                entry.get('size', 'Unknown')
            ))
    
    def add_to_history(self, download):
        """Add download to history (deprecated - use history_manager directly)"""
        pass
    
    def clear_history(self):
        """Clear download history"""
        if messagebox.askyesno("Confirm", "Are you sure you want to clear all download history?"):
            self.history_manager.clear_history()
            self.load_history()
            messagebox.showinfo("Success", "Download history cleared")
    
    def export_history(self):
        """Export download history"""
        from tkinter import filedialog
        
        filename = filedialog.asksaveasfilename(
            title="Export History",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            history = self.history_manager.load_history()
            try:
                import json
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(history, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Success", f"History exported to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export history: {str(e)}")

def main():
    """Main application entry point"""
    root = tk.Tk()
    app = DownloadManagerGUI(root)
    
    # Set application icon (if available)
    try:
        root.iconbitmap("icon.ico")
    except:
        pass
    
    # Center window on screen
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")
    
    root.mainloop()

if __name__ == "__main__":
    main()