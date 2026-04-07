import tkinter as tk
from tkinter import filedialog
import bencodepy as bp
import os
import shutil
import sys

# Hide the main Tk window, keep it tidy
root = tk.Tk()
root.withdraw()

# Pick the torrent file, you beauty
torrent_path = filedialog.askopenfilename(title="Select Torrent File, You Legend!", filetypes=[("Torrent files", "*.torrent")])
if not torrent_path:
    print("No torrent selected? You're teasin' me! Quittin'.")
    sys.exit()

# Pick the data dir to scan and sort
dir_path = filedialog.askdirectory(title="Select Directory with Data, Gorgeous!")
if not dir_path:
    print("No dir picked? Fair dinkum, quittin'.")
    sys.exit()

try:
    # Decode the torrent file
    with open(torrent_path, 'rb') as f:
        torrent_data = bp.decode(f.read())

    # Extract info dictionary
    info = torrent_data[b'info']
    single_file = b'length' in info  # Single-file or multi-file torrent

    # Grab torrent files with paths and sizes
    torrent_files = []
    if single_file:
        # Single-file torrent
        name = info[b'name'].decode('utf-8')
        size = info[b'length']
        torrent_files.append({'path': name, 'size': size})
    else:
        # Multi-file torrent
        for file_info in info[b'files']:
            # Join path components for multi-file torrents
            path = '/'.join(p.decode('utf-8') for p in file_info[b'path'])
            size = file_info[b'length']
            torrent_files.append({'path': path, 'size': size})

    # Sort by size desc to match unique big files first
    torrent_files.sort(key=lambda x: x['size'], reverse=True)

    # Scan the entire subdir tree for data files
    data_files = []
    for rootdir, _, filenames in os.walk(dir_path):
        for fname in filenames:
            fullpath = os.path.join(rootdir, fname)
            try:
                size = os.path.getsize(fullpath)
                relpath = os.path.relpath(fullpath, dir_path)
                data_files.append({'full': fullpath, 'rel': relpath, 'size': size})
            except OSError as e:
                print(f"Couldn’t get size for '{fullpath}': {e}")

    # Sort data files by size desc
    data_files.sort(key=lambda x: x['size'], reverse=True)

    # Track matched files to avoid double-ups
    matched = {}

    for t in torrent_files:
        # Find candidates with exact size match, not already matched
        candidates = [d for d in data_files if d['size'] == t['size'] and d['full'] not in matched]

        if len(candidates) == 1:
            d = candidates[0]
            matched[d['full']] = t['path']
            # Move to the proper path in the dir
            new_path = os.path.join(dir_path, t['path'])
            try:
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                shutil.move(d['full'], new_path)
                print(f"Moved '{d['rel']}' to '{t['path']}' – lookin’ ace!")
            except (OSError, shutil.Error) as e:
                print(f"Failed to move '{d['rel']}' to '{t['path']}': {e}")

        elif len(candidates) > 1:
            # Try matchin’ by basename if sizes tie
            basename = os.path.basename(t['path'])
            name_matches = [d for d in candidates if os.path.basename(d['rel']) == basename]
            if len(name_matches) == 1:
                d = name_matches[0]
                matched[d['full']] = t['path']
                new_path = os.path.join(dir_path, t['path'])
                try:
                    os.makedirs(os.path.dirname(new_path), exist_ok=True)
                    shutil.move(d['full'], new_path)
                    print(f"Moved '{d['rel']}' to '{t['path']}' (name match) – too easy!")
                except (OSError, shutil.Error) as e:
                    print(f"Failed to move '{d['rel']}' to '{t['path']}': {e}")
            else:
                print(f"Ambiguous matches for '{t['path']}' (size {t['size']}) – skippin’ to stay safe!")

        else:
            print(f"No match found for '{t['path']}' (size {t['size']}) – bummer, mate!")

    print("All done, you ripper! Check your dir for the restored structure.")

except Exception as e:
    print(f"Oops, hit a snag: {e}. Double-check your torrent file and data dir, you cheeky bugger!")