"""
Test the main GUI with a simple YouTube URL to verify filename display
"""

import tkinter as tk
from main import DownloadManagerGUI

def test_youtube_gui():
    """Test YouTube download through the main GUI"""
    root = tk.Tk()
    app = DownloadManagerGUI(root)
    
    # Set a test URL
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    app.url_var.set(test_url)
    
    print("GUI loaded successfully")
    print(f"Test URL set: {test_url}")
    print("GUI is ready - try downloading to test filename display")
    
    root.mainloop()

if __name__ == "__main__":
    test_youtube_gui()