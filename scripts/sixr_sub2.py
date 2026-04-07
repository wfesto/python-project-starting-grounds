import os
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

def convert_bytes_to_human_readable(size_bytes):
    """Convert bytes to human-readable format (KB, MB, GB, etc.)."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"

def get_directory_size(directory):
    """Calculate total size of all files in directory and its subdirectories."""
    total_size = 0
    try:
        for dirpath, _, filenames in os.walk(directory):
            for filename in filenames:
                file_path = Path(dirpath) / filename
                try:
                    total_size += file_path.stat().st_size
                except (FileNotFoundError, PermissionError):
                    continue
    except (PermissionError, OSError):
        return 0
    return total_size

def main():
    # Initialize Tkinter and hide the root window
    root = tk.Tk()
    root.withdraw()

    # Open directory selection dialog
    print("Please select a base directory...")
    base_dir = filedialog.askdirectory(title="Select Base Directory")
    
    if not base_dir:
        print("No directory selected. Exiting.")
        return

    print(f"\nCalculating sizes for subdirectories in: {base_dir}\n")
    
    # Get immediate subdirectories and their sizes
    try:
        subdirs = [d for d in Path(base_dir).iterdir() if d.is_dir()]
        if not subdirs:
            print("No subdirectories found.")
            return

        # Calculate sizes and store as list of tuples (subdir, size)
        dir_sizes = []
        for subdir in subdirs:
            total_size = get_directory_size(subdir)
            dir_sizes.append((subdir.name, total_size))
        
        # Sort by size in descending order
        dir_sizes.sort(key=lambda x: x[1], reverse=True)
        
        # Print results
        for subdir_name, total_size in dir_sizes:
            human_readable_size = convert_bytes_to_human_readable(total_size)
            print(f"{subdir_name}: {human_readable_size}")
            
    except (PermissionError, OSError) as e:
        print(f"Error accessing directory: {e}")

if __name__ == "__main__":
    main()