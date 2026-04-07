import os
from tkinter import Tk
from tkinter.filedialog import askdirectory
from humanfriendly import format_size

def get_dir_sizes(root_dir):
    dir_sizes = []
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        total_size = 0
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            try:
                total_size += os.path.getsize(file_path)
            except (OSError, FileNotFoundError):
                continue
        dir_sizes.append((dirpath, total_size))
    
    return sorted(dir_sizes, key=lambda x: x[1], reverse=True)

def main():
    # Hide the root tkinter window
    root = Tk()
    root.withdraw()
    
    # Pop up the directory chooser dialog
    print("Oi, mate! Pick a directory to scan!")
    chosen_dir = askdirectory(title="Choose a Directory, ya legend!")
    
    if not chosen_dir:
        print("No directory picked, you cheeky bugger! Exiting...")
        return
    
    print(f"\nScanning {chosen_dir}... Hold onto your hat!\n")
    
    # Get and sort directory sizes
    dir_sizes = get_dir_sizes(chosen_dir)
    
    # Print results in a human-readable format
    print("Subdirectory sizes (biggest to smallest):")
    print("-" * 50)
    for dirpath, size in dir_sizes:
        human_size = format_size(size)
        print(f"{dirpath}: {human_size}")
    
    print("\nAll done, you ripper! Cheers!")

if __name__ == "__main__":
    main()