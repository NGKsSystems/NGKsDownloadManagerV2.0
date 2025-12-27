"""
Test GUI filename update mechanism
"""

import tkinter as tk
from tkinter import ttk

def test_treeview_update():
    """Test how the treeview updates work"""
    root = tk.Tk()
    root.title("Test Treeview Update")
    root.geometry("800x300")
    
    # Create treeview like the main app
    columns = ("ID", "Filename", "URL Type", "Progress", "Speed", "Status")
    tree = ttk.Treeview(root, columns=columns, show="headings", height=10)
    
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120)
    
    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Insert initial item like the main app does
    download_id = 0
    item_id = tree.insert("", tk.END, values=(
        download_id, "Preparing...", "YouTube", "0%", "0 B/s", "Starting"
    ))
    
    print(f"Initial item inserted with ID: {item_id}")
    print(f"Initial values: {tree.item(item_id)['values']}")
    
    def update_progress_test():
        """Test progress update"""
        progress_info = {
            'filename': 'Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)',
            'progress': '50%',
            'speed': '2.1 MB/s - ETA: 1m 30s',
            'status': 'Downloading'
        }
        
        print(f"\nUpdating with progress_info: {progress_info}")
        
        # Update like the main app does
        current_values = list(tree.item(item_id)['values'])
        print(f"Current values before update: {current_values}")
        
        if len(current_values) >= 6:
            current_values[1] = progress_info.get('filename', current_values[1])
            current_values[3] = progress_info.get('progress', current_values[3])
            current_values[4] = progress_info.get('speed', current_values[4])
            current_values[5] = progress_info.get('status', current_values[5])
            
            print(f"New values after update: {current_values}")
            tree.item(item_id, values=current_values)
            
            # Verify the update
            updated_values = tree.item(item_id)['values']
            print(f"Verified values in tree: {updated_values}")
    
    def complete_download_test():
        """Test download completion"""
        current_values = list(tree.item(item_id)['values'])
        current_values[3] = "100%"
        current_values[5] = "Completed"
        tree.item(item_id, values=current_values)
        
        print(f"\nDownload completed. Final values: {tree.item(item_id)['values']}")
    
    # Add buttons to test updates
    button_frame = tk.Frame(root)
    button_frame.pack(pady=10)
    
    tk.Button(button_frame, text="Update Progress", command=update_progress_test).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="Complete Download", command=complete_download_test).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="Close", command=root.quit).pack(side=tk.LEFT, padx=5)
    
    print("\nClick 'Update Progress' to test filename update")
    print("Click 'Complete Download' to test completion")
    
    root.mainloop()

if __name__ == "__main__":
    test_treeview_update()