import tkinter as tk
from tkinter import filedialog
import os
import shutil
import logging
import sys

# Set up logging to track the action
logging.basicConfig(
    filename='subtitle_sort.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Hide the main Tk window, keep it sleek
root = tk.Tk()
root.withdraw()

# Pick the base directory, you beauty
base_dir = filedialog.askdirectory(title="Select Base Directory with MP4s, You Legend!")
if not base_dir:
    logging.error("No base directory selected. Quittin'.")
    print("No base dir picked? You're teasin' me! Quittin'.")
    sys.exit()

# Path to Subs directory
subs_dir = os.path.join(base_dir, "Subs")
if not os.path.exists(subs_dir):
    logging.error(f"Subs directory not found at '{subs_dir}'. Quittin'.")
    print(f"No Subs folder in '{base_dir}'? Fair dinkum, quittin'.")
    sys.exit()

try:
    # Find all .mp4 files in the base directory
    mp4_files = [f for f in os.listdir(base_dir) if f.lower().endswith('.mp4')]
    if not mp4_files:
        logging.warning("No .mp4 files found in base directory.")
        print("No .mp4 files in the base dir? Bummer, mate!")
        sys.exit()

    for mp4_file in mp4_files:
        # Get the video name without .mp4
        video_name = os.path.splitext(mp4_file)[0]
        subdir_path = os.path.join(subs_dir, video_name)

        # Check if matching subdirectory exists
        if not os.path.isdir(subdir_path):
            logging.warning(f"No subdirectory found for '{mp4_file}' at '{subdir_path}'.")
            print(f"No subdir for '{mp4_file}' in Subs. Skippin'!")
            continue

        # Find all .srt files in the matching subdirectory
        srt_files = [
            os.path.join(subdir_path, f) for f in os.listdir(subdir_path)
            if f.lower().endswith('.srt')
        ]

        if not srt_files:
            logging.warning(f"No .srt files found in '{subdir_path}' for '{mp4_file}'.")
            print(f"No .srt files for '{mp4_file}' in '{subdir_path}'. Skippin'!")
            continue

        # Find the largest .srt file by size
        largest_srt = max(srt_files, key=os.path.getsize)
        largest_size = os.path.getsize(largest_srt)
        logging.info(f"Found largest .srt for '{mp4_file}': '{largest_srt}' ({largest_size} bytes)")

        # Destination path in base directory
        dest_srt = os.path.join(base_dir, f"{video_name}.srt")

        # Copy the largest .srt to base dir with new name
        try:
            shutil.copy2(largest_srt, dest_srt)
            logging.info(f"Copied '{largest_srt}' to '{dest_srt}'.")
            print(f"Copied '{os.path.basename(largest_srt)}' to '{video_name}.srt' – lookin’ ace!")
        except (OSError, shutil.Error) as e:
            logging.error(f"Failed to copy '{largest_srt}' to '{dest_srt}': {e}")
            print(f"Oops, couldn’t copy '{os.path.basename(largest_srt)}' to '{video_name}.srt': {e}")

    logging.info("All done! Check your base dir and log file.")
    print("All done, you ripper! Check your base dir for the .srt files and subtitle_sort.log for deets.")

except Exception as e:
    logging.error(f"Hit a snag: {e}")
    print(f"Oops, hit a snag: {e}. Check subtitle_sort.log for more, you cheeky bugger!")