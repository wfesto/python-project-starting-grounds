import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

from humanfriendly import format_size

from ihb_ext.ffprobe import get_all_video_metadata
from ihb_utils.file_utils import choose_directory
from ihb_utils.gen_utils import format_time, timestamp_log
from ihb_utils.Resolution import Resolution
from ihb_utils.video_utils import (
    ENCODING_SCHEMES,
    PREF_EXT,
    VIDEO_EXTENSIONS,
    EncodingScheme,
    build_chapter_file,
    calc_target_resolution,
    eval_recommendation,
    get_aspect_ratio_str,
)

# --- Configuration Constants ---
DURATION_TOLERANCE = 0.5  # Tolerance for duration comparison (in seconds)


def get_video_info(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Uses ffprobe to get essential video stream information, including orientation
    by checking width, height, and the rotation tag/side data.
    """
    absolute_path = os.path.abspath(file_path)

    probe_data = get_all_video_metadata(file_path)

    if not probe_data.get("v_streams"):
        timestamp_log(f"No video stream found for {os.path.basename(file_path)}", level="ERROR")
        return None

    v_stream = probe_data["v_streams"][0]
    format = probe_data["format_data"]

    raw_width = v_stream.get("width")
    raw_height = v_stream.get("height")

    rotate = 0
    # 1. Check for rotation flag in standard 'tags' dictionary (common for older MOV/MP4)
    rotate_tag = v_stream.get("tags", {}).get("rotate")
    if rotate_tag is not None:
        try:
            rotate = int(rotate_tag)
        except ValueError:
            pass

    # 2. If still no rotation, check 'side_data_list' (common for modern .mov files)
    if rotate == 0:
        side_data = v_stream.get("side_data_list", [])
        for entry in side_data:
            if entry.get("side_data_type") == "displaymatrix":
                # Rotation here is the angle (usually -90, 90, 180)
                rotation_angle = entry.get("rotation", 0)
                try:
                    rotate = int(rotation_angle)
                except (ValueError, TypeError):
                    pass
                break

    # Normalize rotation angle (e.g., -90 becomes 270)
    rotate = rotate % 360
    if rotate < 0:
        rotate += 360

    # FFmpeg/FFprobe logic: if rotate is 90 or 270, width and height are swapped for effective display
    if rotate in (90, 270):
        display_width = raw_height
        display_height = raw_width
    else:
        # FALLBACK: If rotation metadata is missing (rotate remains 0),
        # assume the raw width/height is the correct display width/height.
        # This is standard for older video files (like VHS captures)
        display_width = raw_width
        display_height = raw_height

    # r_frame_rate parsing (same as before)
    r_frame_rate_str = v_stream.get("r_frame_rate", "0/1")
    if "/" in r_frame_rate_str:
        num, den = map(int, r_frame_rate_str.split("/"))
        fps = num / den if den != 0 else 0.0
    else:
        fps = float(r_frame_rate_str)

    return {
        "width": raw_width,
        "height": raw_height,
        "duration": float(v_stream.get("duration", None) or format.get("duration", None) or "0"),
        "r_frame_rate": fps,
        "bit_rate": int(v_stream.get("bit_rate", 0)),
        "filepath": absolute_path,
        "is_landscape": display_width >= display_height,
        "display_width": display_width,
        "display_height": display_height,
        "file_size": os.path.getsize(absolute_path),
    }


def get_encoding_scheme_choice(
    files_info: List[Dict[str, Any]], max_res_width: int, max_res_height: int, min_res_width: int, min_res_height: int
) -> EncodingScheme:
    """
    Prompts the user to select an encoding scheme, displaying max source resolution
    and individual file resolutions first.
    """
    # Display the maximum effective resolution from all sources
    timestamp_log("")

    print(" --- Individual Files to be Processed ---")
    for i, info in enumerate(files_info):
        filename = os.path.basename(info["filepath"])
        orientation = "L" if info["is_landscape"] else "P"
        resolution_str = str(info["display_width"]) + "x" + str(info["display_height"])
        aspect_ratio_str = get_aspect_ratio_str(info["display_width"], info["display_height"])
        print(f"[{i+1}] ({orientation}) {resolution_str}\t{aspect_ratio_str}\t{filename}")

    print(f"--- Maximum Source Resolution: {max_res_width}x{max_res_height} {get_aspect_ratio_str(max_res_width, max_res_height)}---")
    print(f"--- Minimum Source Resolution: {min_res_width}x{min_res_height} {get_aspect_ratio_str(min_res_width, min_res_height)}---")
    print("--- Available Encoding Schemes for Recode ---")

    scheme_map = {}

    # Include all schemes now that we are forcing a full recode/scale/concat
    for i, scheme in enumerate(scheme for scheme in ENCODING_SCHEMES if not scheme.is_source):
        key = str(i + 1)
        recommendation_str = eval_recommendation(
            {"codec_name": "", "width": min_res_width, "height": min_res_height},
            Resolution(height=scheme.fixed_dim, width=scheme.scaled_dim),
            False,
        )
        scheme_map[key] = scheme
        display_name = f"{scheme.name}\t{recommendation_str}"
        print(f"[{key}] {display_name}")

    print("[q] Quit")

    while True:
        choice = input("Enter the number of the encoding scheme to use: ").strip()
        if choice == "q":
            timestamp_log("Quit selected. Exiting now.")
            sys.exit(0)
        elif choice in scheme_map:
            return scheme_map[choice]
        timestamp_log("Invalid choice. Please enter a number from the list above.", level="ERROR")


def execute_command(command_list: List[str]) -> bool:
    """
    Prompts the user to run the command, executes it, times it, and handles errors.
    Returns True on success, False otherwise.
    """
    # Print the command without timestamp prefix for easy copy/paste
    quoted_cmd_parts = [
        f'"{part}"' if (" " in part or any(c in part for c in ["(", ")", "!", "&"])) and not (part.startswith("-") or "=" in part or part.isnumeric()) else part
        for part in command_list
    ]

    command_string = " ".join(quoted_cmd_parts)

    timestamp_log("FFMPEG COMMAND: To perform the recode and concatenation:")
    timestamp_log(command_string)

    run_prompt = input("Do you want to run this FFmpeg encode command now? (y/n): ").strip().lower()

    if run_prompt != "y":
        timestamp_log("Encode command execution skipped by user.")
        return False

    timestamp_log("Starting FFmpeg encode...")
    start_time = time.perf_counter()

    try:
        # Using sys.stdout/sys.stderr allows FFmpeg's progress output to be visible
        subprocess.run(command_list, check=True, stdout=sys.stdout, stderr=sys.stderr)

        end_time = time.perf_counter()
        duration_seconds = end_time - start_time

        timestamp_log(f"FFmpeg encode successful! Total time taken: {format_time(duration_seconds)}.")
        return True

    except subprocess.CalledProcessError as e:
        timestamp_log(f"FFmpeg encode failed with return code {e.returncode}.", level="ERROR")
        return False
    except FileNotFoundError:
        timestamp_log(f"FFmpeg binary not found. Ensure it is in your system PATH.", level="FATAL")
        return False
    except Exception as e:
        timestamp_log(f"An unexpected execution error occurred: {e}", level="ERROR")
        return False


def check_output_duration(files_info: List[Dict[str, Any]], output_filepath: str):
    """
    Checks the final output file's duration against the sum of source file durations
    and logs a warning if it exceeds the tolerance.
    """
    if not files_info:
        return

    expected_duration = sum(info["duration"] for info in files_info)
    total_source_size = sum(info["file_size"] for info in files_info)

    timestamp_log("\n--- Post-Encode Duration Validation ---")

    output_info = get_video_info(output_filepath)

    if output_info is None:
        timestamp_log(f"Could not retrieve metadata for the final output file: {os.path.basename(output_filepath)}.", level="ERROR")
        return

    output_size = output_info["file_size"]
    if output_size == 0:
        timestamp_log(f"Unable to read file size of output file: {output_filepath}", level="ERROR")
    else:
        perc_reduction = 100 * (1 - output_size / total_source_size)
        timestamp_log(f"Reduction: {perc_reduction:.2f}% -- Source: {format_size(total_source_size)} -- Output: {format_size(output_size)}")

    actual_duration = output_info["duration"]
    duration_difference = abs(actual_duration - expected_duration)

    if duration_difference > DURATION_TOLERANCE:
        timestamp_log(
            f"FATAL DURATION MISMATCH: Expected total duration of sources: {expected_duration:.2f}s, "
            f"Actual output duration: {actual_duration:.2f}s (Difference: {duration_difference:.2f}s). "
            f"This indicates a significant error in the concatenation/re-encode process.",
            level="FATAL",
        )
    else:
        timestamp_log(f"Duration check passed: Expected {expected_duration:.2f}s, Actual {actual_duration:.2f}s. (Difference: {duration_difference:.2f}s).")

    timestamp_log("Duration validation complete.")


def process_directory(dir_path: str):
    """
    Scans a directory, performs validation, generates the recode-concat command,
    executes it if prompted, and then performs final checks.
    """
    timestamp_log(f"Processing directory: {dir_path}")

    # 1. Find and sort video files
    video_files = sorted(
        [os.path.join(dir_path, f) for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f)) and f.lower().endswith(VIDEO_EXTENSIONS)]
    )

    if len(video_files) < 2:
        timestamp_log("Skipping: Less than two video files found. Requires at least two videos for concatenation.", level="WARNING")
        return

    timestamp_log(f"Found {len(video_files)} video files.")

    # 2. Collect metadata and identify biggest resolution
    files_info = []
    max_res_width = 0
    max_res_height = 0
    min_res_width = 9999
    min_res_height = 9999

    for f_path in video_files:
        info = get_video_info(f_path)
        if info:
            files_info.append(info)

            max_res_width = max(max_res_width, info["display_width"])
            max_res_height = max(max_res_height, info["display_height"])
            min_res_width = min(min_res_width, info["display_width"])
            min_res_height = min(min_res_height, info["display_height"])
        else:
            timestamp_log(f"Could not get info for {os.path.basename(f_path)}. Cannot proceed with concatenation.", level="FATAL")
            return

    # 3. Orientation Validation
    if not files_info:
        timestamp_log("No valid video files to process.", level="WARNING")
        return

    first_orientation = files_info[0]["is_landscape"]

    # Check if all files match the first file's orientation
    if not all(info["is_landscape"] == first_orientation for info in files_info):
        orientation_type = "Landscape" if first_orientation else "Portrait"

        # Find the first offending file for the error message
        offender = next(info for info in files_info if info["is_landscape"] != first_orientation)
        offender_orientation = "Portrait" if offender["is_landscape"] else "Landscape"

        timestamp_log(
            f"Expected {orientation_type} ({video_files[0]}), but file "
            f"'{os.path.basename(offender['filepath'])}' is {offender_orientation} ({offender['display_width']}x{offender['display_height']}).",
            level="FATAL",
        )
        # We must exit the directory processing here if validation fails
        sys.exit(1)

    timestamp_log(f"Orientation check passed. All files are: {'Landscape' if first_orientation else 'Portrait'}.")
    timestamp_log("-" * 50)

    # 4. Get Encoding Scheme Choice (Now enhanced to display resolutions)
    selected_scheme = get_encoding_scheme_choice(files_info, max_res_width, max_res_height, min_res_width, min_res_height)

    # 5. Calculate Final Resolution
    if max_res_width == 0 or max_res_height == 0:
        timestamp_log("Could not determine maximum resolution. Aborting.", level="FATAL")
        return

    target_res = calc_target_resolution(selected_scheme, max_res_width, max_res_height, force_even=True)

    timestamp_log(f"Max Source Resolution: {max_res_width}x{max_res_height} -- {get_aspect_ratio_str(max_res_width, max_res_height)}")
    timestamp_log(f"Selected Target Scheme: {selected_scheme.name} (CRF {selected_scheme.crf}, Preset {selected_scheme.encoder_preset})")
    timestamp_log(f"Calculated Final Resolution: {target_res.width}x{target_res.height} -- {get_aspect_ratio_str(target_res.width, target_res.height)}")

    # 6. Build the Main FFmpeg Command

    input_flags = []
    filter_complex_inputs = []

    for i, file_info in enumerate(files_info):
        input_flags.extend(["-i", file_info["filepath"]])
        filter_complex_inputs.extend([f"[{i}:v:0]", f"[{i}:a:0]"])

    concat_filter = "".join(filter_complex_inputs) + f"concat=n={len(files_info)}:v=1:a=1 [v] [a]"

    output_filename = f"{os.path.basename(dir_path)}_CONCAT_{selected_scheme.name}_H265.{PREF_EXT}"
    output_filepath = os.path.join(dir_path, output_filename)
    # ----------------------------------------------------------------------------

    # Note: We do *not* include rotation metadata in the final output since we are forcing
    # a new resolution via -s, which handles the rotation implicitly by setting the new WxH.
    ffmpeg_command_list = [
        "ffmpeg",
        *input_flags,
        "-filter_complex",
        concat_filter,
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-c:v",
        "libx265",
        "-crf",
        str(selected_scheme.crf),
        "-preset",
        selected_scheme.encoder_preset,
        "-s",
        f"{target_res.width}x{target_res.height}",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-y",  # Add -y to allow overwrite in case of re-run
        output_filepath,
    ]

    # 7. Execute the command
    exec_cmd_results = execute_command(ffmpeg_command_list)
    if exec_cmd_results:
        # 8. Perform source duration validation (after command succeeds)
        check_output_duration(files_info, output_filepath)

        timestamp_log("--- Chapter Generation ---", blank_lines=1)

        # 9. Generate chapter file and print final metadata injection command
        chapter_file_path = build_chapter_file(files_info, dir_path)

        if chapter_file_path:
            output_with_chapters_filename = f"{os.path.basename(dir_path)}_FINAL_H265.{PREF_EXT}"
            output_with_chapters_filepath = os.path.join(dir_path, output_with_chapters_filename)


def main():
    """Main execution function with argparse."""

    parser = argparse.ArgumentParser(
        description="Recode and concatenate video files in a single directory to H.265, " "using the largest video's resolution as the basis for scaling."
    )
    parser.add_argument("-i", "--input", type=str, help="The single input directory path containing the video files to be concatenated.")
    args = parser.parse_args()

    base_dir = args.input or choose_directory()

    if not base_dir or not os.path.isdir(base_dir):
        timestamp_log(f"The path is not a valid directory: {base_dir}", level="FATAL")
        sys.exit(1)

    timestamp_log("-" * 50)
    process_directory(base_dir)
    timestamp_log("-" * 50)


if __name__ == "__main__":
    main()
