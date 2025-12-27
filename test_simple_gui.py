"""
Test a simple GUI integration with YouTube downloader
"""

import tkinter as tk
from tkinter import ttk
import threading
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from youtube_downloader import YouTubeDownloader

class SimpleDownloadTest:
    def __init__(self, root):
        self.root = root
        self.root.title("Simple Download Test")
        self.root.geometry("800x400")
        
        self.youtube_downloader = YouTubeDownloader()
        
        # Create GUI elements
        self.create_widgets()
        
        self.download_counter = 0
        self.active_downloads = {}
    
    def create_widgets(self):
        # URL input
        url_frame = tk.Frame(self.root)
        url_frame.pack(pady=10, padx=10, fill=tk.X)
        
        tk.Label(url_frame, text="URL:").pack(side=tk.LEFT)
        self.url_var = tk.StringVar(value="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        tk.Entry(url_frame, textvariable=self.url_var, width=60).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Download button
        tk.Button(url_frame, text="Download", command=self.start_download).pack(side=tk.RIGHT)
        
        # Progress display
        columns = ("ID", "Filename", "Progress", "Speed", "Status")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", height=8)
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150)
        
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Log area
        self.log_text = tk.Text(self.root, height=8)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add scrollbar for log
        scrollbar = tk.Scrollbar(self.log_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.log_text.yview)
    
    def log(self, message):
        """Add message to log"""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        print(f"LOG: {message}")
    
    def start_download(self):
        """Start download test"""
        url = self.url_var.get().strip()
        if not url:
            self.log("Error: No URL provided")
            return
        
        self.log(f"Starting download test for: {url}")
        
        download_id = self.download_counter
        self.download_counter += 1
        
        # Insert initial item
        item_id = self.tree.insert("", tk.END, values=(
            download_id, "Preparing...", "0%", "0 B/s", "Starting"
        ))
        
        self.active_downloads[download_id] = {
            'item_id': item_id,
            'url': url
        }
        
        self.log(f"Created download entry with ID: {download_id}")
        
        # Start download in thread
        thread = threading.Thread(
            target=self.download_worker,
            args=(download_id, url),
            daemon=True
        )
        thread.start()
    
    def download_worker(self, download_id, url):
        """Worker thread for download"""
        try:
            self.log(f"Worker thread started for download {download_id}")
            
            def progress_callback(progress_info):
                self.log(f"Progress callback: {progress_info}")
                self.root.after(0, self.update_progress, download_id, progress_info)
            
            output_dir = r"C:\Users\suppo\Desktop\NGKsSystems\NGKs DL Manager\downloads"
            os.makedirs(output_dir, exist_ok=True)
            
            self.log(f"Starting YouTube download to: {output_dir}")
            
            result = self.youtube_downloader.download(
                url, output_dir, progress_callback
            )
            
            self.log(f"Download result: {result}")
            
            if isinstance(result, dict) and result.get('status') == 'success':
                self.root.after(0, self.download_completed, download_id, result)
            else:
                self.root.after(0, self.download_failed, download_id, result)
                
        except Exception as e:
            self.log(f"Exception in worker: {e}")
            self.root.after(0, self.download_failed, download_id, {'error': str(e)})
    
    def update_progress(self, download_id, progress_info):
        """Update progress in GUI"""
        self.log(f"update_progress called: ID={download_id}, info={progress_info}")
        
        if download_id not in self.active_downloads:
            self.log(f"Warning: Download ID {download_id} not found in active downloads")
            return
        
        download = self.active_downloads[download_id]
        item_id = download['item_id']
        
        # Update treeview
        current_values = list(self.tree.item(item_id)['values'])
        self.log(f"Current values: {current_values}")
        
        if len(current_values) >= 5:
            new_filename = progress_info.get('filename', current_values[1])
            new_progress = progress_info.get('progress', current_values[2])
            new_speed = progress_info.get('speed', current_values[3])
            new_status = progress_info.get('status', current_values[4])
            
            current_values[1] = new_filename
            current_values[2] = new_progress
            current_values[3] = new_speed
            current_values[4] = new_status
            
            self.log(f"New values: {current_values}")
            self.tree.item(item_id, values=current_values)
            
            # Verify update
            updated_values = self.tree.item(item_id)['values']
            self.log(f"Verified values: {updated_values}")
    
    def download_completed(self, download_id, result):
        """Handle download completion"""
        self.log(f"Download {download_id} completed: {result}")
        
        if download_id in self.active_downloads:
            download = self.active_downloads[download_id]
            item_id = download['item_id']
            
            current_values = list(self.tree.item(item_id)['values'])
            current_values[2] = "100%"
            current_values[4] = "Completed"
            self.tree.item(item_id, values=current_values)
    
    def download_failed(self, download_id, result):
        """Handle download failure"""
        self.log(f"Download {download_id} failed: {result}")
        
        if download_id in self.active_downloads:
            download = self.active_downloads[download_id]
            item_id = download['item_id']
            
            current_values = list(self.tree.item(item_id)['values'])
            current_values[4] = "Failed"
            self.tree.item(item_id, values=current_values)

def main():
    root = tk.Tk()
    app = SimpleDownloadTest(root)
    root.mainloop()

if __name__ == "__main__":
    main()