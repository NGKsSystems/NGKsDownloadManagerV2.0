"""
Enhanced dialogs and features for the download manager
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import requests
from PIL import Image, ImageTk
from io import BytesIO
import threading
import webbrowser

class QualitySelectionDialog:
    """Dialog for selecting video quality and format"""
    
    def __init__(self, parent, video_info, youtube_downloader):
        self.parent = parent
        self.video_info = video_info
        self.youtube_downloader = youtube_downloader
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Quality & Format")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (500 // 2)
        self.dialog.geometry(f"600x500+{x}+{y}")
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup dialog UI"""
        # Video info section
        info_frame = ttk.LabelFrame(self.dialog, text="Video Information", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Title
        title_label = ttk.Label(info_frame, text=self.video_info.get('title', 'Unknown Title'), 
                               font=("Arial", 12, "bold"), wraplength=550)
        title_label.pack(anchor=tk.W, pady=(0, 5))
        
        # Details
        details_frame = ttk.Frame(info_frame)
        details_frame.pack(fill=tk.X)
        
        # Left column
        left_frame = ttk.Frame(details_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(left_frame, text=f"Uploader: {self.video_info.get('uploader', 'Unknown')}").pack(anchor=tk.W)
        ttk.Label(left_frame, text=f"Duration: {self._format_duration(self.video_info.get('duration', 0))}").pack(anchor=tk.W)
        
        # Right column
        right_frame = ttk.Frame(details_frame)
        right_frame.pack(side=tk.RIGHT)
        
        ttk.Label(right_frame, text=f"Views: {self._format_number(self.video_info.get('view_count', 0))}").pack(anchor=tk.W)
        
        # Format selection
        format_frame = ttk.LabelFrame(self.dialog, text="Available Formats", padding=10)
        format_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Format list
        columns = ("Quality", "Extension", "Size", "Video Codec", "Audio Codec", "Format Note")
        self.format_tree = ttk.Treeview(format_frame, columns=columns, show="headings", height=10)
        
        for col in columns:
            self.format_tree.heading(col, text=col)
            if col == "Quality":
                self.format_tree.column(col, width=80)
            elif col == "Extension":
                self.format_tree.column(col, width=60)
            elif col == "Size":
                self.format_tree.column(col, width=80)
            elif col == "Format Note":
                self.format_tree.column(col, width=150)
            else:
                self.format_tree.column(col, width=100)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(format_frame, orient=tk.VERTICAL, command=self.format_tree.yview)
        self.format_tree.configure(yscrollcommand=scrollbar.set)
        
        self.format_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate formats
        self.populate_formats()
        
        # Options
        options_frame = ttk.LabelFrame(self.dialog, text="Download Options", padding=10)
        options_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.audio_only = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Audio only", variable=self.audio_only).pack(side=tk.LEFT)
        
        self.download_thumbnail = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Download thumbnail", variable=self.download_thumbnail).pack(side=tk.LEFT, padx=(20, 0))
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Download", command=self.download).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="Auto Select Best", command=self.auto_select).pack(side=tk.LEFT)
    
    def populate_formats(self):
        """Populate format list"""
        formats = self.video_info.get('formats', [])
        
        for fmt in formats:
            quality = f"{fmt.get('quality', 0)}p" if fmt.get('quality') else "Unknown"
            extension = fmt.get('ext', '')
            size = self._format_size(fmt.get('filesize', 0)) if fmt.get('filesize') else "Unknown"
            vcodec = fmt.get('vcodec', 'none')[:15] + "..." if len(fmt.get('vcodec', '')) > 15 else fmt.get('vcodec', '')
            acodec = fmt.get('acodec', 'none')[:15] + "..." if len(fmt.get('acodec', '')) > 15 else fmt.get('acodec', '')
            note = fmt.get('format_note', '')[:20] + "..." if len(fmt.get('format_note', '')) > 20 else fmt.get('format_note', '')
            
            self.format_tree.insert("", tk.END, values=(quality, extension, size, vcodec, acodec, note), 
                                  tags=(fmt.get('format_id', ''),))
    
    def auto_select(self):
        """Auto select best quality format"""
        # Select first item (usually best quality)
        children = self.format_tree.get_children()
        if children:
            self.format_tree.selection_set(children[0])
            self.format_tree.focus(children[0])
    
    def download(self):
        """Start download with selected format"""
        selection = self.format_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a format")
            return
        
        # Get format ID from tags
        item = self.format_tree.item(selection[0])
        format_id = item['tags'][0] if item['tags'] else None
        
        if not format_id:
            messagebox.showwarning("Warning", "Invalid format selection")
            return
        
        self.result = {
            'format_id': format_id,
            'audio_only': self.audio_only.get(),
            'download_thumbnail': self.download_thumbnail.get()
        }
        
        self.dialog.destroy()
    
    def cancel(self):
        """Cancel dialog"""
        self.result = None
        self.dialog.destroy()
    
    def _format_duration(self, seconds):
        """Format duration in HH:MM:SS"""
        if not seconds:
            return "Unknown"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    
    def _format_number(self, num):
        """Format large numbers with commas"""
        if not num:
            return "0"
        return f"{num:,}"
    
    def _format_size(self, bytes_size):
        """Format file size"""
        if not bytes_size:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} TB"


class HuggingFaceInfoDialog:
    """Dialog for displaying Hugging Face model/dataset information"""
    
    def __init__(self, parent, repo_info, hf_downloader):
        self.parent = parent
        self.repo_info = repo_info
        self.hf_downloader = hf_downloader
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Hugging Face: {repo_info.get('repo_id', 'Unknown')}")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (700 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (600 // 2)
        self.dialog.geometry(f"700x600+{x}+{y}")
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup dialog UI"""
        # Create notebook for tabs
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Info tab
        info_frame = ttk.Frame(notebook)
        notebook.add(info_frame, text="Information")
        self.setup_info_tab(info_frame)
        
        # Files tab
        files_frame = ttk.Frame(notebook)
        notebook.add(files_frame, text="Files")
        self.setup_files_tab(files_frame)
        
        # Model card tab (if available)
        if self.repo_info.get('repo_type') == 'model':
            card_frame = ttk.Frame(notebook)
            notebook.add(card_frame, text="Model Card")
            self.setup_card_tab(card_frame)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Button(button_frame, text="Download All", command=self.download_all).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Download Selected", command=self.download_selected).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT, padx=(0, 10))
        ttk.Button(button_frame, text="Open in Browser", command=self.open_browser).pack(side=tk.LEFT)
    
    def setup_info_tab(self, parent):
        """Setup information tab"""
        # Scrollable frame
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Repository info
        info_frame = ttk.LabelFrame(scrollable_frame, text="Repository Information", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Basic info
        ttk.Label(info_frame, text=f"Repository ID: {self.repo_info.get('repo_id', 'Unknown')}", 
                 font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(0, 5))
        ttk.Label(info_frame, text=f"Type: {self.repo_info.get('repo_type', 'Unknown').title()}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Author: {self.repo_info.get('author', 'Unknown')}").pack(anchor=tk.W)
        
        # Stats
        stats_frame = ttk.LabelFrame(scrollable_frame, text="Statistics", padding=10)
        stats_frame.pack(fill=tk.X, padx=10, pady=5)
        
        stats_inner = ttk.Frame(stats_frame)
        stats_inner.pack(fill=tk.X)
        
        left_stats = ttk.Frame(stats_inner)
        left_stats.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        right_stats = ttk.Frame(stats_inner)
        right_stats.pack(side=tk.RIGHT)
        
        ttk.Label(left_stats, text=f"Downloads: {self._format_number(self.repo_info.get('downloads', 0))}").pack(anchor=tk.W)
        ttk.Label(left_stats, text=f"Likes: {self._format_number(self.repo_info.get('likes', 0))}").pack(anchor=tk.W)
        
        ttk.Label(right_stats, text=f"Total Size: {self._format_size(self.repo_info.get('total_size', 0))}").pack(anchor=tk.W)
        ttk.Label(right_stats, text=f"Files: {len(self.repo_info.get('files', []))}").pack(anchor=tk.W)
        
        # Tags
        if self.repo_info.get('tags'):
            tags_frame = ttk.LabelFrame(scrollable_frame, text="Tags", padding=10)
            tags_frame.pack(fill=tk.X, padx=10, pady=5)
            
            tags_text = ", ".join(self.repo_info.get('tags', []))
            tags_label = ttk.Label(tags_frame, text=tags_text, wraplength=650)
            tags_label.pack(anchor=tk.W)
        
        # Description
        if self.repo_info.get('description'):
            desc_frame = ttk.LabelFrame(scrollable_frame, text="Description", padding=10)
            desc_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            
            desc_text = tk.Text(desc_frame, height=8, wrap=tk.WORD)
            desc_scrollbar = ttk.Scrollbar(desc_frame, orient=tk.VERTICAL, command=desc_text.yview)
            desc_text.configure(yscrollcommand=desc_scrollbar.set)
            
            desc_text.insert(tk.END, self.repo_info.get('description', ''))
            desc_text.configure(state=tk.DISABLED)
            
            desc_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            desc_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def setup_files_tab(self, parent):
        """Setup files tab"""
        # Files list
        columns = ("Filename", "Size", "Type")
        self.files_tree = ttk.Treeview(parent, columns=columns, show="tree headings", height=15)
        
        self.files_tree.heading("#0", text="")
        self.files_tree.column("#0", width=20, stretch=False)
        
        for col in columns:
            self.files_tree.heading(col, text=col)
            if col == "Filename":
                self.files_tree.column(col, width=400)
            else:
                self.files_tree.column(col, width=100)
        
        # Scrollbar
        files_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.files_tree.yview)
        self.files_tree.configure(yscrollcommand=files_scrollbar.set)
        
        # Populate files
        self.populate_files()
        
        self.files_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
        files_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10, padx=(0, 10))
    
    def setup_card_tab(self, parent):
        """Setup model card tab"""
        card_text = tk.Text(parent, wrap=tk.WORD)
        card_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=card_text.yview)
        card_text.configure(yscrollcommand=card_scrollbar.set)
        
        # Load model card in background
        def load_card():
            card_content = self.hf_downloader.get_model_card(self.repo_info.get('repo_id'))
            if card_content:
                card_text.insert(tk.END, card_content)
            else:
                card_text.insert(tk.END, "Model card not available or could not be loaded.")
            card_text.configure(state=tk.DISABLED)
        
        threading.Thread(target=load_card, daemon=True).start()
        
        card_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
        card_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10, padx=(0, 10))
    
    def populate_files(self):
        """Populate files list"""
        files = self.repo_info.get('files', [])
        
        for file in files:
            # Estimate file size (placeholder)
            size = "Unknown"
            file_type = file.split('.')[-1].upper() if '.' in file else "Unknown"
            
            self.files_tree.insert("", tk.END, values=(file, size, file_type))
    
    def download_all(self):
        """Download entire repository"""
        self.result = {'type': 'all'}
        self.dialog.destroy()
    
    def download_selected(self):
        """Download selected files"""
        selection = self.files_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select files to download")
            return
        
        selected_files = []
        for item in selection:
            filename = self.files_tree.item(item)['values'][0]
            selected_files.append(filename)
        
        self.result = {'type': 'selected', 'files': selected_files}
        self.dialog.destroy()
    
    def cancel(self):
        """Cancel dialog"""
        self.result = None
        self.dialog.destroy()
    
    def open_browser(self):
        """Open repository in browser"""
        repo_id = self.repo_info.get('repo_id')
        repo_type = self.repo_info.get('repo_type', 'model')
        
        if repo_type == 'dataset':
            url = f"https://huggingface.co/datasets/{repo_id}"
        elif repo_type == 'space':
            url = f"https://huggingface.co/spaces/{repo_id}"
        else:
            url = f"https://huggingface.co/{repo_id}"
        
        webbrowser.open(url)
    
    def _format_number(self, num):
        """Format large numbers with commas"""
        if not num:
            return "0"
        return f"{num:,}"
    
    def _format_size(self, bytes_size):
        """Format file size"""
        if not bytes_size:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"


class ThumbnailViewer:
    """Thumbnail viewer for video previews"""
    
    def __init__(self, parent):
        self.parent = parent
        self.thumbnail_cache = {}
    
    def show_thumbnail(self, url, title="Thumbnail"):
        """Show thumbnail in popup window"""
        if url in self.thumbnail_cache:
            self._display_thumbnail(self.thumbnail_cache[url], title)
            return
        
        # Download thumbnail in background
        def download_thumbnail():
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                
                image = Image.open(BytesIO(response.content))
                image.thumbnail((400, 300), Image.Resampling.LANCZOS)
                
                photo = ImageTk.PhotoImage(image)
                self.thumbnail_cache[url] = photo
                
                self.parent.after(0, self._display_thumbnail, photo, title)
                
            except Exception as e:
                self.parent.after(0, self._show_error, str(e))
        
        threading.Thread(target=download_thumbnail, daemon=True).start()
    
    def _display_thumbnail(self, photo, title):
        """Display thumbnail in popup window"""
        popup = tk.Toplevel(self.parent)
        popup.title(title)
        popup.resizable(False, False)
        popup.transient(self.parent)
        
        # Center popup
        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - (photo.width() // 2)
        y = (popup.winfo_screenheight() // 2) - (photo.height() // 2)
        popup.geometry(f"{photo.width()}x{photo.height()}+{x}+{y}")
        
        label = ttk.Label(popup, image=photo)
        label.image = photo  # Keep a reference
        label.pack()
    
    def _show_error(self, error_msg):
        """Show error message"""
        messagebox.showerror("Thumbnail Error", f"Could not load thumbnail: {error_msg}")


class ProgressDialog:
    """Progress dialog for long-running operations"""
    
    def __init__(self, parent, title="Processing..."):
        self.parent = parent
        self.cancelled = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x150")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.protocol("WM_DELETE_WINDOW", self.cancel)
        
        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (200)
        y = (self.dialog.winfo_screenheight() // 2) - (75)
        self.dialog.geometry(f"400x150+{x}+{y}")
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup progress dialog UI"""
        # Status label
        self.status_var = tk.StringVar(value="Initializing...")
        status_label = ttk.Label(self.dialog, textvariable=self.status_var)
        status_label.pack(pady=20)
        
        # Progress bar
        self.progress = ttk.Progressbar(self.dialog, mode='indeterminate')
        self.progress.pack(fill=tk.X, padx=20, pady=10)
        self.progress.start()
        
        # Cancel button
        ttk.Button(self.dialog, text="Cancel", command=self.cancel).pack(pady=10)
    
    def update_status(self, status):
        """Update status message"""
        self.status_var.set(status)
        self.dialog.update()
    
    def cancel(self):
        """Cancel operation"""
        self.cancelled = True
        self.dialog.destroy()
    
    def close(self):
        """Close dialog"""
        self.dialog.destroy()