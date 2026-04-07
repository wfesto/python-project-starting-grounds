import os
import tkinter as tk
from tkinter import filedialog

# Define common video and picture extensions
VIDEO_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
PICTURE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}

def bytes_to_human(size):
    """Convert bytes to human-readable format."""
    for unit in ['', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"

def calculate_sizes(directory):
    """Recursively calculate video and picture sizes for dir and subdirs."""
    sizes = {}  # dict of path: (video_size, picture_size)
    
    def recurse(dir_path):
        video_total = 0
        picture_total = 0
        
        # List files and subdirs
        for entry in os.scandir(dir_path):
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                size = entry.stat().st_size
                if ext in VIDEO_EXTS:
                    video_total += size
                elif ext in PICTURE_EXTS:
                    picture_total += size
            elif entry.is_dir():
                sub_video, sub_picture = recurse(entry.path)
                video_total += sub_video
                picture_total += sub_picture
                sizes[entry.path] = (sub_video, sub_picture)
        
        sizes[dir_path] = (video_total, picture_total)
        return video_total, picture_total
    
    recurse(directory)  
    return sizes

# Tkinter to choose directory
root = tk.Tk()
root.withdraw()  # Hide the main window
base_dir = filedialog.askdirectory(title="Choose Base Directory, Mate!")

if base_dir:
    print(f"Base directory selected: {base_dir}\n")
    
    dir_sizes = calculate_sizes(base_dir)
    
    # Sort paths by total size (video + picture) in descending order
    sorted_paths = sorted(dir_sizes.keys(), key=lambda p: sum(dir_sizes[p]), reverse=False)
    
    for path in sorted_paths:
        video_size, picture_size = dir_sizes[path]
        total_size = video_size + picture_size
        rel_path = os.path.relpath(path, base_dir) if path != base_dir else '.'
        print(f"Directory: {rel_path}")
        print(f"  Total Video Size: {bytes_to_human(video_size)}")
        print(f"  Total Picture Size: {bytes_to_human(picture_size)}")
        print(f"  Total Combined Size: {bytes_to_human(total_size)}\n")
else:
    print("No directory selected, ya tease! Try again?")