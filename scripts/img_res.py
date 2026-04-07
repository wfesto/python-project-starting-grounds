import os
from collections import Counter
from tkinter import Tk
from tkinter import filedialog
import imagesize
import concurrent.futures

# Define common image file extensions
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff')

def get_resolution(path):
    try:
        width, height = imagesize.get(path)
        return (width, height)
    except Exception as e:
        print(f"Error processing {path}: {e}")
        return None

# Hide the root window
root = Tk()
root.withdraw()

# Ask user to select a directory
directory = filedialog.askdirectory(title="Select Directory")

if not directory:
    print("No directory selected. Exiting.")
    exit()

# Collect all image file paths
image_paths = []
for root_dir, _, files in os.walk(directory):
    for file in files:
        if file.lower().endswith(IMAGE_EXTENSIONS):
            image_paths.append(os.path.join(root_dir, file))

if not image_paths:
    print("No image files found in the selected directory.")
    exit()

# Process images using multithreading
resolutions = []
with concurrent.futures.ThreadPoolExecutor() as executor:
    for res in executor.map(get_resolution, image_paths):
        if res is not None:
            resolutions.append(res)

# Count the occurrences of each resolution
counter = Counter(resolutions)

# Calculate total successfully processed images
total = sum(counter.values())

# Sort resolutions by width then height
sorted_res = sorted(counter.keys(), key=lambda x: (x[0], x[1]))

# Generate HTML table
html_content = """
<html>
<body>
<table border="1">
<caption>Total images processed: {}</caption>
<thead>
<tr>
<th>Resolution (WxH)</th>	
<th>Count</th>
</tr>
</thead>
<tbody>
""".format(total)

for res in sorted_res:
    w, h = res
    count = counter[res]
    html_content += f"<tr><td>{w}x{h}</td><td>{count}</td></tr>\n"

html_content += """
</tbody>
</table>
</body>
</html>
"""

# Write to file
output_file = "image_resolutions.html"
with open(output_file, "w") as f:
    f.write(html_content)

print(f"HTML table written to {output_file}")