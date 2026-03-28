import argparse
import logging
import os
from pathlib import Path
from typing import Any

from ihb_common.utils.gen_utils import configure_logging, format_time
from ihb_video.manager import video_manager

logger = logging.getLogger(__name__)

DURATION_TOLERANCE = 0.5
PARAM_TOLERANCE = 0.05


def check_video_compatibility(probe_data_list: list[dict[str, Any]]) -> tuple[bool, str]:
    if not probe_data_list:
        return False, "No valid video files found to check compatibility."

    probe_data_0 = probe_data_list[0]
    format0 = probe_data_0["format_data"]
    video0 = probe_data_0["v_streams"][0]

    # Check for basic match: ext, codec, and resolution
    # Check for close match: FPS and Bitrate
    num0, den0 = video0.get("r_frame_rate", "0/1").split("/")
    fps0 = float(num0) / float(den0) if float(den0) != 0 else 0.0

    bit_rate_str0 = video0.get("bit_rate", "0")
    bit_rate0 = int(bit_rate_str0) if bit_rate_str0.isdigit() else 0

    success = True

    for probe_data in probe_data_list:
        formatX = probe_data["format_data"]
        videoX = probe_data["v_streams"][0]
        if os.path.splitext(formatX["filename"])[1] != os.path.splitext(format0["filename"])[1]:
            print(f"Extension mismatch: {formatX['filename']}' vs baseline '{format0['filename']}")
            success = False
        if videoX["codec_name"] != video0["codec_name"]:
            print(f"Codec mismatch: {videoX['codec_name']} vs {video0['codec_name']}")
            success = False
        if videoX["width"] != video0["width"] or videoX["height"] != video0["height"]:
            print(f"Resolution mismatch: {videoX['width']}x{videoX['height']} v {video0['width']}x{video0['height']}")
            success = False

        num, den = videoX.get("r_frame_rate", "0/1").split("/")
        fps = float(num) / float(den) if float(den) != 0 else 0.0

        bit_rate_str = videoX.get("bit_rate", "0")
        bit_rate = int(bit_rate_str) if bit_rate_str.isdigit() else 0

        if fps0 != 0 and abs(fps - fps0) / fps0 > PARAM_TOLERANCE:
            print(f"FPS mismatch: {fps:.2f} in '{os.path.basename(formatX['filename'])}' vs baseline {fps0:.2f}")
            success = False

        if bit_rate0 > 0 and abs(bit_rate - bit_rate0) / bit_rate0 > PARAM_TOLERANCE:
            print(f"Bitrate mismatch: {bit_rate} in '{os.path.basename(formatX['filename'])}' vs baseline {bit_rate0}")
            success = False

    return success


def process_directory(input_dir: str, auto_chapter: bool = False, force_concat: bool = False) -> bool:
    video_list = sorted(
        [file_path for file_path in [os.path.join(input_dir, file_name) for file_name in os.listdir(input_dir)] if video_manager.is_video_file(file_path)]
    )

    data_list = [video_manager.get_video_metadata(file) for file in video_list]

    is_compatible = check_video_compatibility(data_list)
    if not is_compatible:
        logger.error(f"Compatibility check FAILED.")
        if force_concat:
            logger.info("Continuing based on settings.")
        else:
            logger.info("Terminating script")
            return False

    output_dir = str(Path(input_dir).parent)
    is_success, output_path, validation_results = video_manager.concat_videos_simple(input_dir, output_dir, data_list)
    logger.info(f"Output expected at {output_path}")

    logger.info(f"concat is{'' if is_success else ' NOT '}successful")
    for validation in validation_results:
        print(str(validation))

    if not output_path or not os.path.exists(output_path):
        logger.warning("No output found. Exiting diectory.")
        return False

    # Validate Duration

    exp_duration = sum((float(video_data["format_data"]["duration"]) for video_data in data_list))
    output_info = video_manager.get_video_metadata(output_path)
    actual_duration = float(output_info["format_data"]["duration"])
    difference = abs(actual_duration - exp_duration)
    logger.info(f"Output video duration: {format_time(actual_duration)}. Expected: {format_time(exp_duration)}. Delta {difference:.04f}")
    logger.info(f"Duration check {'PASSED' if is_compatible else 'FAILED'}")

    if difference > DURATION_TOLERANCE:
        return False

    set_result = video_manager.set_chapters(output_path, data_list, auto_chapter)
    logger.info(f"Set chapters - {'SUCCESS' if set_result else 'FAILURE'}.")

    return True


def main():
    parser = argparse.ArgumentParser(description="Concatenate compatiable videos without recoding and set chapters.")
    parser.add_argument("-i", "--input", type=str, help="The input directory path containing video files or subdirectories to processs.")
    parser.add_argument("-c", "--auto_chapter", action="store_false", help="Flag to skip the chapter file edit prompt and use the file names as chapter titles")
    parser.add_argument("-f", "--force_concat", action="store_true", help="Force conctenation regardless of pre-test results")
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")

    args = parser.parse_args()
    configure_logging(level=args.level)

    base_dir = args.input

    if not os.path.isdir(base_dir):
        logger.error(f"The selected path is not a valid directory: {base_dir}")
        return 1

    process_directory(base_dir, args.auto_chapter, args.force_concat)


if __name__ == "__main__":
    main()
