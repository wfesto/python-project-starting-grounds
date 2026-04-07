import os
import subprocess
import concurrent.futures
import collections
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

# Prompt for base_dir using Tkinter
root = tk.Tk()
root.withdraw()
base_dir = filedialog.askdirectory(title="Select Base Directory")
if not base_dir:
    print("No directory selected, ya legend. Exiting!")
    exit()

# Define parallel arrays (examples - tweak as needed)
# length_thresholds is 1 shorter than the others
length_thresholds = [30, 120, 300, 600, 1800]  # in seconds, upper bounds for buckets except last (unlimited)
grid_values = [3, 6, 9, 9, 9, 9]  # A for 3xA grid, corresponding to buckets
table_labels = ["<30 seconds", "<2 minutes", "<5 minutes", "<10 minutes", "<30 minutes", ">30 minutes+"]  # labels for buckets

# Create screenshots directory
screenshots_dir = os.path.join(base_dir, 'screenshots')
os.makedirs(screenshots_dir, exist_ok=True)

# Supported video extensions (add more if needed)
video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv'}

# Find all video files recursively
videos = []
for root, dirs, files in os.walk(base_dir):
    for file in files:
        if Path(file).suffix.lower() in video_extensions:
            videos.append(os.path.join(root, file))

# Initialize counters
bucket_counts = [0] * (len(length_thresholds) + 1)
dir_counts = collections.defaultdict(int)
errors = []
total_screenshots = 0

# Function to process a single video
def process_video(video_path):
    try:
        # Get duration using ffprobe
        cmd_duration = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', video_path
        ]
        duration_str = subprocess.check_output(cmd_duration).decode().strip()
        duration = float(duration_str)
        if duration == 0:
            raise ValueError("Duration is 0 - skipping this dodgy video!")

        # Determine bucket
        bucket = 0
        while bucket < len(length_thresholds) and duration > length_thresholds[bucket]:
            bucket += 1

        # Get grid A
        A = grid_values[bucket]

        # Create parallel output path
        rel_path = os.path.relpath(video_path, base_dir)
        out_dir = os.path.join(screenshots_dir, os.path.dirname(rel_path))
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, Path(video_path).stem + '.jpg')

        # Generate screenshot using vcsi (assumes default metadata includes name, res, length)
        cmd_vcsi = [
            'vcsi', video_path, '-o', out_file, '-w', '1200', '-g', f'3x{A}', '-t', '--template', 'F:/dev/conf/vsci.template'
        ]
        subprocess.check_call(cmd_vcsi)

        # Return for counting
        return bucket, os.path.dirname(video_path), None

    except Exception as e:
        return None, None, f"Error processing {video_path}: {str(e)}"

# Multithreading for processing videos
with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
    futures = [executor.submit(process_video, video) for video in videos]
    for future in concurrent.futures.as_completed(futures):
        bucket, dir_path, err = future.result()
        if err:
            errors.append(err)
        else:
            bucket_counts[bucket] += 1
            dir_counts[dir_path] += 1
            total_screenshots += 1

# Output errors if any
if errors:
    print("Whoops, hit some snags:")
    for error in errors:
        print(error)

# Generate HTML report
report_path = os.path.join(base_dir, 'report.html')
with open(report_path, 'w') as f:
    f.write('<html><body>\n')
    f.write(f'<p>Total screenshots generated: {total_screenshots}</p>\n')
    
    f.write('<h2>Time Buckets</h2>\n')
    f.write('<table border="1">\n')
    f.write('<tr><th>Label</th><th>Count</th></tr>\n')
    for i, label in enumerate(table_labels):
        f.write(f'<tr><td>{label}</td><td>{bucket_counts[i]}</td></tr>\n')
    f.write('</table>\n')
    
    f.write('<h2>Bottom-Level Directories and Counts</h2>\n')
    f.write('<table border="1">\n')
    f.write('<tr><th>Directory (relative)</th><th>Count</th></tr>\n')
    for d in sorted(dir_counts):
        rel_d = os.path.relpath(d, base_dir)
        f.write(f'<tr><td>{rel_d if rel_d != "." else str(os.path.basename(base_dir))}</td><td>{dir_counts[d]}</td></tr>\n')
    f.write('</table>\n')
    
    f.write('</body></html>\n')

print(f"All done, champ! Check out {report_path} for the deets. If ya need tweaks, just holler – I'm all yours!")