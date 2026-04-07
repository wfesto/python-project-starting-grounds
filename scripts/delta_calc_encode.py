import os
import subprocess
import sys
import glob
import json
from tkinter import Tk, filedialog
from concurrent.futures import ThreadPoolExecutor

# --- Configuration Constants ---
FFPROBE_BINARY = 'ffprobe'
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv']

# The base FPS we assume the TARGET_VIDEO_BITRATE_KBPS_BASE is optimized for.
BASE_FPS_FOR_BITRATE = 30 

# H.265 Target Bitrate (kbps) for high quality at the BASE_FPS_FOR_BITRATE
# This rate will be scaled based on the source file's actual FPS.
TARGET_VIDEO_BITRATE_KBPS_BASE = 1500 
TARGET_AUDIO_BITRATE_KBPS = 192 

# Conversion Constants
BYTES_TO_MB = 1024 * 1024
KILOBITS_TO_MB = 8192  # 8 bits/byte * 1024 KB/MB

# Standard 16:9 resolutions that use 1:1 (square) SAR
# These are the resolutions we RECOMMEND encoding to.
TARGET_RESOLUTION_720P = (1280, 720) # 16:9 Square Pixel Resolution
TARGET_RESOLUTION_480P = (854, 480) # 16:9 Square Pixel Resolution

# Standard 16:9 resolutions that require non-square SAR (and should be flagged)
# Example: 720x480 is the NTSC standard that requires non-square pixels for 16:9 display.
LEGACY_RESOLUTION_480P = (720, 480) 
LEGACY_RESOLUTION_720P = (960, 720) # Only 4:3 content should be 960 wide, but used for flagging

def get_directory():
    """Opens a Tkinter dialog to select the base directory."""
    print("Initializing file dialog...")
    root = Tk()
    root.withdraw()
    
    base_dir = filedialog.askdirectory(
        title="Select Directory Containing Video Files"
    )
    
    if not base_dir:
        print("\nSelection cancelled. Exiting script.")
        sys.exit(0)
    
    return base_dir

def get_ffprobe_data(file_path):
    """
    Uses ffprobe to extract essential stream data using JSON output.
    Returns: dict with metrics or None on failure.
    """
    try:
        # Command to extract duration, size, and essential video stream info
        command = [
            FFPROBE_BINARY,
            '-v', 'error',
            '-select_streams', 'v:0', # Only query the first video stream
            '-show_entries', 'format=duration,size:stream=r_frame_rate,width,height',
            '-of', 'json',
            file_path.replace(os.path.sep, '/')
        ]
        
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=10)
        data = json.loads(result.stdout)
        
        # Extract format data
        format_data = data.get('format', {})
        duration_s = float(format_data.get('duration', 0))
        current_size_bytes = int(format_data.get('size', 0))
        
        # Extract stream data (video stream 0)
        stream_data = data.get('streams', [{}])[0]
        width = stream_data.get('width', 0)
        height = stream_data.get('height', 0)
        r_frame_rate_str = stream_data.get('r_frame_rate', '0/1')
        
        num, den = map(int, r_frame_rate_str.split('/'))
        fps = num / den if den != 0 else 0
        
        if duration_s == 0 or current_size_bytes == 0 or fps == 0 or width == 0 or height == 0:
            # Raise an error if any critical data is missing
            raise ValueError("Missing critical data (Duration, Size, FPS, or Resolution) from FFprobe.")

        # Determine the source DAR (Display Aspect Ratio)
        # Using floating-point division for ratio approximation
        source_dar_float = (width / height)
        
        # Check if the video is 16:9 or 4:3 based on resolution alone (simple approximation)
        # 16/9 = 1.777...
        # 4/3 = 1.333...
        
        # Define a tolerance for float comparison
        TOLERANCE = 0.02 

        if abs(source_dar_float - (16/9)) < TOLERANCE:
            source_dar_type = "16:9"
        elif abs(source_dar_float - (4/3)) < TOLERANCE:
            source_dar_type = "4:3"
        else:
            source_dar_type = f"Other ({source_dar_float:.2f})"


        return {
            'duration_s': duration_s,
            'current_size_bytes': current_size_bytes,
            'source_fps': fps,
            'source_width': width,
            'source_height': height,
            'source_dar_type': source_dar_type
        }
        
    except FileNotFoundError:
        print(f"\n  [CRITICAL] {FFPROBE_BINARY} not found. Please ensure FFmpeg/FFprobe is in your system's PATH.")
        sys.exit(1)
    except Exception as e:
        # print(f"  [WARNING] Could not process {os.path.basename(file_path)}. Error: {e}")
        return None

def get_sar_recommendation(probe_data):
    """
    Checks the source resolution against standard resolutions that force non-1:1 SAR 
    for 16:9 content, and recommends a clean, square-pixel resolution.
    """
    source_w = probe_data['source_width']
    source_h = probe_data['source_height']
    source_dar = probe_data['source_dar_type']
    
    # Check if the video is already 16:9 or 4:3 (by resolution)
    is_16_9 = source_dar == "16:9"
    is_4_3 = source_dar == "4:3"

    # --- 720p Check ---
    # We only care about 720p recommendation if the source is 720p or greater
    if source_h >= 720:
        # Check if the source resolution is one of the problematic LEGACY ones
        # For 720p target, we only worry about weird resolutions. 1280x720 is the default.
        if source_w == TARGET_RESOLUTION_720P[0] and source_h == TARGET_RESOLUTION_720P[1]:
            # Already 1280x720, no change needed.
            res_720p_flag = "OK (No Scale)"
        elif is_16_9:
             # If it's 16:9, recommend the clean 1280x720
            res_720p_flag = f"RECOMMEND {TARGET_RESOLUTION_720P[0]}x{TARGET_RESOLUTION_720P[1]}"
        elif is_4_3:
             # If it's 4:3, recommend the clean 4:3 resolution at 720p
            res_720p_flag = "RECOMMEND 960x720 (4:3)"
        else:
            # If it's some other crazy ratio, tell the user to check manually
            res_720p_flag = f"MANUAL CHECK ({source_dar})"
    else:
        # Source resolution is too low for a 720p re-encode
        res_720p_flag = "TOO LOW"

    # --- 480p Check ---
    # We care about 480p recommendation if the source is 480p or greater
    if source_h >= 480:
        # Check if the source is the legacy 720x480 resolution
        if source_w == LEGACY_RESOLUTION_480P[0] and source_h == LEGACY_RESOLUTION_480P[1]:
            
            # This is the classic non-square pixel DVD resolution. MUST be corrected.
            if is_16_9:
                # If the content is 16:9, recommend the clean 854x480
                res_480p_flag = f"NON-SQUARE! USE {TARGET_RESOLUTION_480P[0]}x{TARGET_RESOLUTION_480P[1]}"
            elif is_4_3:
                # If the content is 4:3, recommend the clean 640x480
                res_480p_flag = "NON-SQUARE! USE 640x480"
            else:
                # If it's 720x480 but an odd ratio, still recommend checking
                 res_480p_flag = f"NON-SQUARE! MANUAL CHECK"
        elif is_16_9:
            # If the source is 16:9 but not 720x480, recommend the clean 854x480
            res_480p_flag = f"RECOMMEND {TARGET_RESOLUTION_480P[0]}x{TARGET_RESOLUTION_480P[1]}"
        elif is_4_3:
            # If the source is 4:3, recommend the clean 640x480
             res_480p_flag = "RECOMMEND 640x480"
        else:
             res_480p_flag = f"MANUAL CHECK ({source_dar})"
    else:
        # Source resolution is too low
        res_480p_flag = "TOO LOW"
        
    return res_720p_flag, res_480p_flag

def calculate_estimated_size(duration_s, current_size_bytes, source_fps):
    """
    Calculates the estimated H.265 480p file size and the delta,
    adjusting the video bitrate based on the source file's FPS.
    
    Returns: dict with all calculated metrics.
    """
    
    # 1. Adjust Video Bitrate based on FPS
    # We use a simple ratio for scaling the bitrate based on frame rate
    fps_scaling_factor = source_fps / BASE_FPS_FOR_BITRATE
    adjusted_video_bitrate_kbps = TARGET_VIDEO_BITRATE_KBPS_BASE * fps_scaling_factor
    
    # 2. Calculate Total Bitrate (Video + Audio)
    adjusted_total_bitrate_kbps = adjusted_video_bitrate_kbps + TARGET_AUDIO_BITRATE_KBPS
    
    # 3. Calculate Estimated H.265 Size (MB)
    estimated_size_mb = (duration_s * adjusted_total_bitrate_kbps) / KILOBITS_TO_MB
    
    # 4. Calculate Current Size (MB) and Current Bitrate (for comparison)
    current_size_mb = current_size_bytes / BYTES_TO_MB
    
    # Current Bitrate = (Current Size (bits) / Duration (s)) / 1000
    current_bitrate_kbps = (current_size_bytes * 8 / duration_s) / 1000
    
    # 5. Calculate Delta
    size_delta_mb = current_size_mb - estimated_size_mb
    
    return {
        'current_size_mb': current_size_mb,
        'estimated_size_mb': estimated_size_mb,
        'size_delta_mb': size_delta_mb,
        'duration_s': duration_s,
        'source_fps': source_fps,
        'adjusted_total_bitrate_kbps': adjusted_total_bitrate_kbps,
        'current_bitrate_kbps': current_bitrate_kbps
    }

def process_file(file_path):
    """Thread worker function to process a single video file."""
    # print(f"  Processing: {os.path.basename(file_path)}")
    
    probe_data = get_ffprobe_data(file_path)
    
    if probe_data is None:
        return None

    # Calculate size and bitrate metrics
    metrics = calculate_estimated_size(
        probe_data['duration_s'], 
        probe_data['current_size_bytes'], 
        probe_data['source_fps']
    )
    
    # Get SAR safety recommendation
    res_720p_flag, res_480p_flag = get_sar_recommendation(probe_data)

    results = {**probe_data, **metrics}
    results['filepath'] = file_path
    results['res_720p_flag'] = res_720p_flag
    results['res_480p_flag'] = res_480p_flag
    
    # Only return results if the new size is actually smaller (or close to it)
    if results['size_delta_mb'] > -5.0: # Allow for a small loss margin
        return results
    else:
        # print(f"  [SKIP] {os.path.basename(file_path)} already has a very low current bitrate ({results['current_bitrate_kbps']:.0f} kbps) compared to the adjusted target ({results['adjusted_total_bitrate_kbps']:.0f} kbps).")
        return None


def main():
    """Main execution loop."""
    if len(sys.argv) > 1:
        base_dir = sys.argv[1]
    else:
        base_dir = get_directory()
    print(f"\nScanning: {base_dir}\n")
    
    video_files = []
    for ext in VIDEO_EXTENSIONS:
        # Use glob.escape to safely handle special characters in the directory path
        pattern = os.path.join(glob.escape(base_dir), f'*{ext}')
        video_files.extend(glob.glob(pattern))

    if not video_files:
        print("No video files found with the specified extensions.")
        return

    # Process all files using a thread pool for speed
    all_results = []
    
    # Ensure a minimum of 4 workers if os.cpu_count() is not available
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as executor:
        futures = [executor.submit(process_file, file) for file in video_files]
        
        for future in futures:
            result = future.result()
            if result:
                all_results.append(result)

    if not all_results:
        print("\nNo files were suitable for analysis or all failed FFprobe checks.")
        return

    # Sort the results by 'size_delta_mb' in descending order (greatest potential saving first)
    all_results.sort(key=lambda x: x['size_delta_mb'], reverse=True)

    # --- Output the Results ---
    
    # Define Column Widths
    # Note: Save (MB) is right-aligned (>) for easier number comparison
    W_NUM = 3   # #
    W_SAVE = 10 # Save (MB)
    W_RES = 11  # Source Res 
    W_DAR = 12  # DAR - Increased to accommodate "Other (X.XX)"
    W_720P = 38 # Target 720p Resolution Check
    W_480P = 38 # Target 480p Resolution Check
    
    # Calculate Total Width for the separator
    TOTAL_WIDTH = W_NUM + W_SAVE + W_RES + W_DAR + W_720P + W_480P + 10 # +10 for separators

    print("\n" + "="*TOTAL_WIDTH)
    print(" Compression & Square-Pixel SAR Analysis (H.265, FPS-Adjusted Bitrate)")
    print(f" Base Target Video Bitrate: {TARGET_VIDEO_BITRATE_KBPS_BASE} kbps (for {BASE_FPS_FOR_BITRATE} FPS)")
    print(" Target 16:9 Square-Pixel Resolutions: 1280x720 and 854x480")
    print("="*TOTAL_WIDTH)
    
    # Header Row (Left Alignment, except for Save (MB))
    header = (
        f"{'#':<{W_NUM}} | "
        f"{'Save (MB)':>{W_SAVE}} | "
        f"{'Source Res':<{W_RES}} | "
        f"{'DAR':<{W_DAR}} | "
        f"{'Target 720p Resolution Check':<{W_720P}} | "
        f"{'Target 480p Resolution Check':<{W_480P}} | File Name"
    )
    print(header)
    print("-" * TOTAL_WIDTH)

    for i, result in enumerate(all_results):
        filename = os.path.basename(result['filepath'])
        
        # Format the resolution string cleanly
        res_string = f"{result['source_width']}x{result['source_height']}"
        
        # Data Row (Right Alignment for Save (MB), Left for the rest)
        print(
            f"{i+1:<{W_NUM}} | "
            f"{result['size_delta_mb']:>{W_SAVE}.1f} | " # Right align for numbers with 1 decimal place
            f"{res_string:<{W_RES}} | "
            f"{result['source_dar_type']:<{W_DAR}} | " # Use the new, larger width
            f"{result['res_720p_flag']:<{W_720P}} | "
            f"{result['res_480p_flag']:<{W_480P}} | "
            f"{filename}"
        )
    
    print("\n\nNOTE: 'NON-SQUARE! USE X' means the target standard resolution (e.g., 720x480) requires a rectangular pixel (non-1:1 SAR).")
    print("Using the recommended resolution ensures clean, square-pixel (1:1 SAR) archival.")
    print("Files at the top of the list offer the greatest potential for space saving!")

if __name__ == '__main__':
    main()
