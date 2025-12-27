"""
Test the YouTube quality selection dialog
"""

import tkinter as tk
from tkinter import ttk

def test_dialog():
    root = tk.Tk()
    root.title("Test Dialog")
    root.geometry("400x200")
    
    def show_quality_dialog():
        quality_options = [
            ("Best Quality", "best"),
            ("720p", "720p"),
            ("480p", "480p"), 
            ("Audio Only (MP3)", "audio"),
            ("Auto (Best Available)", "auto")
        ]
        
        # Create simple selection dialog
        dialog = tk.Toplevel(root)
        dialog.title("Select Quality")
        dialog.geometry("350x300")
        dialog.transient(root)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (350 // 2)
        y = (dialog.winfo_screenheight() // 2) - (300 // 2)
        dialog.geometry(f"350x300+{x}+{y}")
        
        result = {"quality": None, "audio_only": False}
        
        # Title
        ttk.Label(dialog, text="Select Download Quality:", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Quality selection
        quality_var = tk.StringVar(value="auto")
        
        # Create frame for radio buttons
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
            print(f"Selected: {selected}, audio_only: {result['audio_only']}")
            dialog.destroy()
            
            # Show result in main window
            result_label.config(text=f"Selected: {selected} (Audio Only: {result['audio_only']})")
        
        def on_cancel():
            print("Cancelled")
            dialog.destroy()
            result_label.config(text="Cancelled")
        
        # Create buttons
        download_btn = ttk.Button(button_frame, text="Download", command=on_download)
        download_btn.pack(side=tk.LEFT, padx=10)
        
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=on_cancel)
        cancel_btn.pack(side=tk.LEFT, padx=10)
        
        # Make Download button default
        download_btn.focus_set()
        dialog.bind('<Return>', lambda e: on_download())
        
        # Wait for dialog
        root.wait_window(dialog)
    
    # Main window content
    ttk.Label(root, text="Test Quality Selection Dialog", font=("Arial", 14, "bold")).pack(pady=20)
    
    ttk.Button(root, text="Show Quality Dialog", command=show_quality_dialog).pack(pady=10)
    
    result_label = ttk.Label(root, text="No selection made yet", font=("Arial", 10))
    result_label.pack(pady=10)
    
    root.mainloop()

if __name__ == "__main__":
    test_dialog()