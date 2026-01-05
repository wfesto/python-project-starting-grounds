import argparse
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ihb_ext.video_manager import concat_videos_simple, get_video_metadata, set_chapters
from ihb_utils.file_utils import choose_directory
from ihb_utils.gen_utils import configure_logging
from ihb_utils.video_utils import get_video_extensions_with_dots

logger = logging.getLogger(__name__)

DURATION_TOLERANCE = 0.5
PARAM_TOLERANCE = 0.05


def check_video_compatibility(probe_data_list: List[Dict[str, Any]]) -> Tuple[bool, str]:
    if not probe_data_list:
        return False, "No valid video files found to check compatibility."

    probe_data_0 = probe_data_list[0]

    # Check for basic match: extension and codec
    for probe_data in probe_data_list:
        if os.path.splitext(probe_data["file_name"])[1] != os.path.splitext(probe_data_0["file_name"])[1]:
            return False, f"Extension mismatch: '{probe_data['file_name']}' vs baseline '{probe_data_0['file_name']}'"
        if probe_data["v_streams"][0]["codec_name"] != probe_data_0["v_streams"][0]["codec_name"]:
            return False, f"Codec mismatch: {probe_data['v_streams'][0]['codec_name']} vs {probe_data_0['v_streams'][0]['codec_name']}"

    # Check for close match: FPS and Bitrate
    num0, den0 = probe_data_0["v_streams"][0].get("r_frame_rate", "0/1").split("/")
    fps0 = num0 / den0 if den0 != 0 else 0.0

    bit_rate_str0 = probe_data_0["v_streams"][0].get("bit_rate", "0")
    bit_rate0 = int(bit_rate_str0) if bit_rate_str0.isdigit() else 0

    for probe_data in probe_data_list:
        num, den = probe_data["v_streams"][0].get("r_frame_rate", "0/1").split("/")
        fps = num / den if den != 0 else 0.0

        bit_rate_str = probe_data["v_streams"][0].get("bit_rate", "0")
        bit_rate = int(bit_rate_str) if bit_rate_str.isdigit() else 0

        if fps0 != 0 and abs(fps - fps0) / fps0 > PARAM_TOLERANCE:
            return False, f"FPS mismatch: {fps:.2f} in '{os.path.basename(probe_data['file_path'])}' vs baseline {fps0:.2f}"

        if bit_rate0 > 0 and abs(bit_rate - bit_rate0) / bit_rate0 > PARAM_TOLERANCE:
            return False, f"Bitrate mismatch: {bit_rate} in '{os.path.basename(probe_data['file_path'])}' vs baseline {bit_rate0}"

    return True, "All video files are compatible for concatenation."


def process_directory(dir_path_str: str, auto_exec: bool = False, auto_clean: bool = False, auto_chapter: bool = False) -> bool:
    """
    Collects, validates, concatenates, and cleans up video files in a single directory.
    """
    logger.info(f"--- Processing directory: {dir_path} ---")
    dir_path = Path(dir_path_str)

    all_files = [str(p) for p in dir_path.iterdir() if p.is_file()]

    if len(all_files) < len(os.listdir(dir_path_str)):
        logger.warning("Directory contains subdirectories. Skipping as requested.")
        return False

    video_paths = sorted([f for f in all_files if os.path.splitext(f.lower())[1] in get_video_extensions_with_dots()])

    if len(video_paths) < 2:
        logger.warning(f"Found {len(video_paths)} video file(s). Need at least two to concatenate. Skipping.")
        return False

    video_infos = []
    total_expected_duration = 0.0
    for path in video_paths:
        probe_data = get_video_metadata(path)
        if probe_data:
            video_infos.append(probe_data)
            total_expected_duration += float(probe_data["format"]["duration"])
        else:
            logger.warning(f"Could not get info for {os.path.basename(path)}. Skipping directory.")
            return False

    if not video_infos:
        logger.error("No valid video files found after ffprobe checks. Skipping directory.")
        return False

    is_compatible, message = check_video_compatibility(video_infos)
    if not is_compatible:
        logger.error(f"Compatibility check FAILED: {message}. Skipping directory.")
        return False

    target_dir = str(dir_path.parent())
    shared_ext = os.path.splitext(video_infos[0]["file_path"])[1]

    logger.info(f"Compatibility check PASSED. Codec: {video_infos[0]['codec_name']}, Ext: {shared_ext}")
    logger.info(f"Total expected duration: {total_expected_duration:.2f} seconds.")

    output_path = concat_videos_simple(video_infos, target_dir, auto_exec)

    if not output_path or not os.path.exists(output_path):
        logger.warning("No output found. Exiting diectory.")
        return False

    # Validate Duration
    output_info = get_video_metadata(output_path)
    if output_info:
        actual_duration = output_info["format"]["duration"]
        difference = abs(actual_duration - total_expected_duration)
        logger.info(f"Output video duration: {actual_duration:.2f} seconds. Expected: {total_expected_duration:.2f} seconds.")

        if difference <= DURATION_TOLERANCE:
            logger.info(f"Duration check PASSED. Difference ({difference:.2f}s) is within tolerance ({DURATION_TOLERANCE}s).")
            set_chapter_result = set_chapters(output_path, video_infos, auto_chapter)
            if set_chapter_result:
                logger.info("Set chapters - success.")
            else:
                logger.warning("Error setting chapters.")
        else:
            logger.error(f"Duration check FAILED. Difference ({difference:.2f}s) is too large. Investigate output file: {output_path}")
    else:
        logger.critical("Could not get duration of the output file. Skipping duration check.")

    clean = False
    if not auto_clean:
        clean = "y" == input(f"Do you want to delete the directory {dir_path_str} (y/n)? ").strip().lower()

    if auto_clean or clean:
        logger.info(f"Deleting all source video files and directory in {dir_path_str}.")
        try:
            shutil.rmtree(dir_path_str)
            logger.info(f"Successfully deleted source directory: {dir_path_str}")
        except Exception as e:
            logger.errror(f"An unexpected error occurred during directory deletion: {e}")
    else:
        logger.info("Source files and directory retained.")

    return True


def main():
    parser = argparse.ArgumentParser(description="Concatenate compatiable videos without recoding and set chapters.")
    parser.add_argument("-i", "--input", type=str, help="The input directory path containing video files or subdirectories to processs.")
    parser.add_argument("-e", "--auto_exec", action="store_false", help="Flag to skip prompt and automatically execute concatenate command.")
    parser.add_argument("-d", "--auto_delete", action="store_false", help="Flag to auto-delete directory after successful concatenation")
    parser.add_argument("-c", "--auto_chapter", action="store_false", help="Flag to skip the chapter file edit prompt and use the file names as chapter titles")
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")

    args = parser.parse_args()
    configure_logging(level=args.level)

    base_dir = args.input or choose_directory()

    if not os.path.isdir(base_dir):
        logger.critical(f"The selected path is not a valid directory: {base_dir}")
        return 1

    subdirectories = [os.path.join(base_dir, d) for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]

    if subdirectories:
        logger.info(f"Iterating through {len(subdirectories)} subdirectories.")

        for sub_dir in subdirectories:
            process_directory(sub_dir, auto_exec=args.auto_exec, auto_clean=args.auto_delete, auto_chapter=args.auto_chapter)
    else:
        logger.info("No subdirectories found. Processing the base directory directly.")
        process_directory(base_dir, auto_exec=args.auto_exec, auto_clean=args.auto_delete, auto_chapter=args.auto_chapter)

    logger.info("Script execution complete.")


if __name__ == "__main__":
    main()
