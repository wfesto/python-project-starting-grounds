import os
import sys
import subprocess
import json
import argparse
import hashlib
import tempfile
import time
from tkinter import Tk, filedialog
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Tuple

# --- Configuration Constants ---
FFPROBE_BINARY = 'ffprobe'
FFMPEG_BINARY = 'ffmpeg'
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv']

# --- Tunable Detection Parameters (The Thresholds you can tweak!) ---
# 1. Duration Tolerance: Files must be within this many seconds duration to be considered a group match.
DURATION_TOLERANCE_S = 0.05 

# 2. Audio Hash Tolerance: How many initial hexadecimal characters (4 bits per char) 
#    of the 64-char SHA256 hash must match. Lowering this makes it more tolerant
#    of re-encodes, but increases false positives. (e.g., 8 chars = 32 bits)
AUDIO_HASH_BITS_TO_COMPARE = 16 

# 3. Size Tolerance: The smaller file's size must be at least this percentage of the 
#    larger file's size to be considered a *content* match. This prevents flagging
#    a 10MB file and a 10GB file as duplicates, even if they share the same hash.
MIN_SIZE_RATIO_FOR_MATCH = 0.70 # 70% minimum size ratio

# --- Internal Constants ---
# Audio Hashing: Extract 30 seconds of raw, uncompressed audio for hashing.
AUDIO_SAMPLE_TIME = 30 
TEMP_AUDIO_FILE = 'audio_sample.raw'
TEMP_IMAGE_FILE = 'keyframe_sample.jpg'

# --- Utility Functions ---

def format_duration(seconds: float) -> str:
    """Converts seconds float to HH:MM:SS format."""
    if seconds is None:
        return "00:00:00"
    # Round and convert to integer seconds
    seconds = int(round(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

# --- FFprobe Metadata Extraction ---

def get_video_metadata(file_path: str) -> Dict[str, Any] | None:
    """
    Uses ffprobe to extract duration (seconds) and size (bytes).
    Returns: dict with metadata or None on failure.
    """
    try:
        # Command to extract duration and size using JSON output
        command = [
            FFPROBE_BINARY,
            '-v', 'error',
            '-show_entries', 'format=duration,size',
            '-of', 'json',
            file_path.replace(os.path.sep, '/') 
        ]
        
        # We allow a small timeout just in case ffprobe hangs on a corrupted file
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=10)
        data = json.loads(result.stdout)
        
        duration_s = float(data.get('format', {}).get('duration', 0))
        current_size_bytes = int(data.get('format', {}).get('size', 0))
        
        if duration_s == 0 or current_size_bytes == 0:
            raise ValueError("Missing critical data (Duration or Size) from FFprobe.")

        return {
            'filepath': file_path,
            'duration_s': duration_s,
            'size_bytes': current_size_bytes,
        }
        
    except FileNotFoundError:
        print(f"\n[CRITICAL] {FFPROBE_BINARY} not found. Ensure FFmpeg/FFprobe is in your system's PATH.")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"[ERROR] FFprobe timed out for {os.path.basename(file_path)}")
        return None
    except Exception:
        # Silent failure for individual files is acceptable
        return None

# --- Input Handling (Step 1) ---

def get_input_directories() -> List[str]:
    """
    Gets input directories from CLI or Tkinter loop.
    Returns a list of unique, absolute directory paths.
    """
    parser = argparse.ArgumentParser(
        description="Duplicate Video Finder using Duration and Hashing."
    )
    # Define argument to accept multiple directories
    parser.add_argument('directories', nargs='*', default=[], help='List of directories to scan.')
    args = parser.parse_args()
    
    input_dirs = [os.path.abspath(d) for d in args.directories if os.path.isdir(d)]
    
    # Initialize Tkinter once, but hide the main window
    root = Tk()
    root.withdraw()

    # Loop for interactive selection if no valid directories were provided via CLI
    if not input_dirs:
        print("No valid directories provided via command line. Starting GUI selection loop.")
        while True:
            dir_path = filedialog.askdirectory(
                title="Select a directory to scan (Click Cancel to finish selection)"
            )
            if not dir_path:
                break
            
            # Use abspath to ensure paths are absolute, as requested
            input_dirs.append(os.path.abspath(dir_path))
            print(f"  -> Added directory: {os.path.basename(dir_path)}")

    # Final cleanup and check
    if not input_dirs:
        print("\nNo directories selected. Exiting script.")
        sys.exit(0)
        
    # Remove duplicates and ensure paths exist
    unique_dirs = sorted(list(set(input_dirs)))
    final_dirs = [d for d in unique_dirs if os.path.isdir(d)]

    if not final_dirs:
        print("\nNone of the provided or selected paths are valid directories. Exiting.")
        sys.exit(1)
        
    return final_dirs

def find_all_video_files(directories: List[str]) -> List[str]:
    """Recursively finds all video files in the given directories."""
    all_files = []
    for directory in directories:
        for root, _, files in os.walk(directory):
            for file in files:
                if any(file.lower().endswith(ext) for ext in VIDEO_EXTENSIONS):
                    all_files.append(os.path.abspath(os.path.join(root, file)))
    return all_files

# --- Duration Grouping (Step 2) ---

def group_by_duration(file_list: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Multithreaded fetching of metadata and grouping of files by similar duration.
    Returns: A dictionary where keys are a 'duration group key' and values are 
             lists of file metadata dictionaries.
    """
    print("\n[Step 2] Scanning files and grouping by duration (Multithreaded)...")
    metadata_list = []
    
    # Use max_workers equal to the number of CPU cores
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as executor:
        # Submit all file paths to the metadata function
        futures = [executor.submit(get_video_metadata, file) for file in file_list]
        
        for future in futures:
            result = future.result()
            if result:
                metadata_list.append(result)

    # Grouping logic: Match files if their duration difference is less than tolerance
    duration_groups = {}
    
    for file_meta in metadata_list:
        found_group = False
        duration = file_meta['duration_s']
        
        # Iterate through existing groups to find a match
        for group_key, group in duration_groups.items():
            # Use the first file in the group as the duration reference
            ref_duration = group[0]['duration_s']
            
            if abs(duration - ref_duration) <= DURATION_TOLERANCE_S:
                group.append(file_meta)
                found_group = True
                break
        
        if not found_group:
            # Create a new group using a rounded duration as the key
            key = f"{round(duration, 2)}"
            duration_groups[key] = [file_meta]
            
    # Filter out groups with only one file (no potential duplicates)
    potential_duplicates = {k: v for k, v in duration_groups.items() if len(v) > 1}
    
    total_potential = sum(len(v) for v in potential_duplicates.values())
    print(f"  -> Found {total_potential} files in {len(potential_duplicates)} duration-matched groups.")
    
    return potential_duplicates

# --- Content Hashing (Step 3) ---

def hash_audio_segment(file_path: str, temp_dir: str) -> str | None:
    """
    Extracts a raw, uncompressed 30s audio segment (PCM 16-bit mono) and returns its SHA256 hash.
    The hash will be identical if the audio content is identical, regardless of bitrate or codec.
    """
    temp_audio_path = os.path.join(temp_dir, TEMP_AUDIO_FILE)
    
    # FFmpeg command: Extracts 30s of uncompressed audio
    command = [
        FFMPEG_BINARY,
        '-i', file_path.replace(os.path.sep, '/'),
        '-map', '0:a:0', # Select first audio stream
        '-t', str(AUDIO_SAMPLE_TIME),
        '-c:a', 'pcm_s16le', # Raw PCM 16-bit little endian
        '-ac', '1', # Mono
        '-f', 's16le', # Raw output format
        '-y', temp_audio_path.replace(os.path.sep, '/')
    ]
    
    try:
        # Suppress FFmpeg output for cleaner console
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Hash the raw audio data
        hasher = hashlib.sha256()
        with open(temp_audio_path, 'rb') as f:
            hasher.update(f.read())
        
        # Only return the start of the hash based on the bits to compare tolerance
        full_hash = hasher.hexdigest()
        chars_to_compare = AUDIO_HASH_BITS_TO_COMPARE // 4
        
        os.remove(temp_audio_path)
        return full_hash[:chars_to_compare]
    
    except FileNotFoundError:
        print(f"[CRITICAL] {FFMPEG_BINARY} not found. Cannot perform content hashing.")
        sys.exit(1)
    except subprocess.CalledProcessError:
        # Audio stream may be missing or unhashable. Return None.
        return None
    except Exception:
        return None

def hash_keyframe_perceptual(file_path: str, temp_dir: str, duration_s: float) -> str | None:
    """
    Extracts a keyframe from the middle of the video and returns a simple content hash.
    NOTE: This is a basic content hash. For true pHash (Hamming distance), a dedicated library is required.
    """
    temp_image_path = os.path.join(temp_dir, TEMP_IMAGE_FILE)
    
    # Calculate middle timestamp
    middle_time = int(duration_s / 2)
    
    # FFmpeg command: Extracts one frame at the middle time
    command = [
        FFMPEG_BINARY,
        '-i', file_path.replace(os.path.sep, '/'),
        '-ss', str(middle_time), 
        '-vframes', '1',
        '-q:v', '5', # Low quality JPEG for speed
        '-y', temp_image_path.replace(os.path.sep, '/')
    ]

    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Hash the image data
        hasher = hashlib.sha256()
        with open(temp_image_path, 'rb') as f:
            hasher.update(f.read())
        
        os.remove(temp_image_path)
        return hasher.hexdigest()
    
    except subprocess.CalledProcessError:
        return None
    except Exception:
        return None

def process_duplicates(potential_duplicates: Dict[str, List[Dict[str, Any]]]) -> List[Tuple[Dict, Dict]]:
    """
    Performs hashing, finds content matches, and collects confirmed duplicate pairs.
    """
    print("\n[Step 3] Hashing and Comparing Content...")
    confirmed_duplicates = []
    total_groups_processed = 0
    total_groups_with_matches = 0
    
    # Use a temporary directory for raw audio/image extraction
    with tempfile.TemporaryDirectory() as temp_dir:
        
        for group_key_str, group in potential_duplicates.items():
            total_groups_processed += 1
            group_matches_found = False # Flag for the new message requirement
            
            # Get the average duration for display
            avg_duration_s = group[0]['duration_s']
            formatted_duration = format_duration(avg_duration_s)

            print(f"\n--- Processing Group: {formatted_duration} ({len(group)} files) ---")
            
            # List files in the group with FULL PATH
            for i, file_meta in enumerate(group, 1):
                size_mb = file_meta['size_bytes'] / (1024 * 1024)
                # Print the full filepath
                print(f"    [{i}] {size_mb: >8.2f} MB - {file_meta['filepath']}")
            
            print("  -> Starting Audio Content Check (Primary Filter)...")
            audio_hashes = {}
            unmatched_audio_files = []

            # 3a. Audio Hashing
            for file_meta in group:
                # The hash returned is now a partial hash based on AUDIO_HASH_BITS_TO_COMPARE
                file_hash_partial = hash_audio_segment(file_meta['filepath'], temp_dir)
                
                if file_hash_partial:
                    # Append metadata to the partial hash key list
                    if file_hash_partial not in audio_hashes:
                        audio_hashes[file_hash_partial] = []
                    audio_hashes[file_hash_partial].append(file_meta)
                else:
                    unmatched_audio_files.append(file_meta) # Files that failed audio hashing

            # Check for matches based on Audio Hash
            files_to_remove = []
            for file_hash_partial, matched_files in audio_hashes.items():
                if len(matched_files) > 1:
                    
                    # Sort by size to identify the largest file
                    matched_files.sort(key=lambda x: x['size_bytes'])
                    
                    largest_file = matched_files[-1]
                    smaller_files = matched_files[:-1]
                    
                    for smaller_file in smaller_files:
                        # NEW CHECK: Apply the MIN_SIZE_RATIO_FOR_MATCH tolerance
                        ratio = smaller_file['size_bytes'] / largest_file['size_bytes']
                        
                        if ratio >= MIN_SIZE_RATIO_FOR_MATCH:
                            print(f"  -> AUDIO MATCH CONFIRMED (Partial Hash: {file_hash_partial}): {os.path.basename(smaller_file['filepath'])} ({ratio*100:.1f}% size of largest)")
                            
                            if smaller_file['filepath'] != largest_file['filepath']:
                                confirmed_duplicates.append((smaller_file, largest_file))
                                group_matches_found = True
                                files_to_remove.append(smaller_file)
                        else:
                             print(f"  -> AUDIO MATCH REJECTED (Ratio {ratio*100:.1f}% < {MIN_SIZE_RATIO_FOR_MATCH*100:.0f}%): {os.path.basename(smaller_file['filepath'])}")

            # Remove confirmed duplicates from the group before proceeding to keyframe check
            for file_meta in files_to_remove:
                if file_meta in group:
                    group.remove(file_meta)
            
            # 3b. Keyframe Hashing (Fallback Check)
            if group and len(group) > 1:
                print(f"  -> Audio check finished. Running Keyframe Check on {len(group)} remaining files...")
                keyframe_hashes = {}
                
                for file_meta in group:
                    # Duration is passed for the middle time calculation
                    file_hash = hash_keyframe_perceptual(file_meta['filepath'], temp_dir, file_meta['duration_s'])
                    
                    if file_hash:
                         if file_hash not in keyframe_hashes:
                            keyframe_hashes[file_hash] = []
                         keyframe_hashes[file_hash].append(file_meta)
                
                # Check for Keyframe Matches
                for file_hash, matched_files in keyframe_hashes.items():
                    if len(matched_files) > 1:
                        
                        matched_files.sort(key=lambda x: x['size_bytes'])
                        largest_file = matched_files[-1]
                        smaller_files = matched_files[:-1]
                        
                        for smaller_file in smaller_files:
                            # NEW CHECK: Apply the MIN_SIZE_RATIO_FOR_MATCH tolerance
                            ratio = smaller_file['size_bytes'] / largest_file['size_bytes']
                            
                            if ratio >= MIN_SIZE_RATIO_FOR_MATCH:
                                print(f"  -> KEYFRAME MATCH CONFIRMED (Hash: {file_hash[:8]}...): {os.path.basename(smaller_file['filepath'])} ({ratio*100:.1f}% size of largest)")
                                if smaller_file['filepath'] != largest_file['filepath']:
                                    confirmed_duplicates.append((smaller_file, largest_file))
                                    group_matches_found = True
                            else:
                                 print(f"  -> KEYFRAME MATCH REJECTED (Ratio {ratio*100:.1f}% < {MIN_SIZE_RATIO_FOR_MATCH*100:.0f}%): {os.path.basename(smaller_file['filepath'])}")
            
            # New Requirement: Explicit message if no matches were found in this group
            if group_matches_found:
                 total_groups_with_matches += 1
            else:
                 print(f"  -> Group finished. No content duplicates confirmed for duration {formatted_duration}.")


    print(f"\n[SUMMARY] Processed {total_groups_processed} duration groups. {total_groups_with_matches} contained confirmed duplicates.")
    return confirmed_duplicates

# --- Main Execution and Deletion ---

def confirm_and_delete(duplicates: List[Tuple[Dict, Dict]]):
    """
    Presents confirmed duplicates to the user and handles deletion of the smaller file.
    """
    if not duplicates:
        print("\nNo potential duplicate video files were found matching content hashes.")
        return

    print("\n" + "="*80)
    print(" DUPLICATE CLEANUP REQUIRED")
    print("="*80)
    
    files_deleted = 0
    
    for i, (smaller_file, larger_file) in enumerate(duplicates, 1):
        smaller_size = f"({smaller_file['size_bytes'] / (1024*1024):.2f} MB)"
        larger_size = f"({larger_file['size_bytes'] / (1024*1024):.2f} MB)"
        duration_fmt = format_duration(larger_file['duration_s'])

        print(f"\n--- DUPLICATE MATCH {i} of {len(duplicates)} ---")
        print(f"  Duration: {duration_fmt}")
        print(f"  KEEP (Largest): {os.path.basename(larger_file['filepath'])} {larger_size}")
        print(f"  DELETE (Smaller): {os.path.basename(smaller_file['filepath'])} {smaller_size}")
        print(f"  Path to Delete: {smaller_file['filepath']}")

        prompt = "  Confirm DELETION of the smaller file? (y/n): "
        user_input = input(prompt).strip().lower()

        if user_input == 'y':
            try:
                os.remove(smaller_file['filepath'])
                files_deleted += 1
                print(f"  --> DELETED: {os.path.basename(smaller_file['filepath'])}")
            except Exception as e:
                print(f"  --> ERROR: Failed to delete {os.path.basename(smaller_file['filepath'])}. Error: {e}")
        else:
            print("  --> Deletion skipped by user.")

    print("\n" + "="*80)
    print(f"Cleanup finished. Total files deleted: {files_deleted}")
    print("="*80)


def main():
    start_time = time.time()
    
    # Step 1: Get directories
    directories = get_input_directories()
    print("\nScanning the following directories:")
    for d in directories:
        print(f"  - {d}")

    # Find all files
    all_files = find_all_video_files(directories)
    if not all_files:
        print("\nNo video files found in the specified directories. Exiting.")
        sys.exit(0)
    print(f"\nFound {len(all_files)} total video files.")
    
    # Step 2: Group by duration
    potential_duplicates = group_by_duration(all_files)
    
    if not potential_duplicates:
        print("\nNo files found with matching durations within tolerance. Script finished.")
        end_time = time.time()
        print(f"Total time: {end_time - start_time:.2f} seconds.")
        return

    # Step 3: Hash and compare content
    confirmed_duplicates = process_duplicates(potential_duplicates)

    # Final: Confirm and delete
    confirm_and_delete(confirmed_duplicates)
    
    end_time = time.time()
    print(f"\nScript finished! Total runtime: {(end_time - start_time):.2f} seconds.")


if __name__ == '__main__':
    main()
