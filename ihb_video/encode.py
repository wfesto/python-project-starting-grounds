import argparse
import logging
import os
import time
from typing import Any, Dict, Tuple

from humanfriendly import format_size
from send2trash import send2trash

from ihb_ext.video_manager import encode_video_depr, get_video_metadata, play_video_file
from ihb_utils.file_utils import choose_directory, choose_file
from ihb_utils.gen_utils import configure_logging, format_time, generate_aligned_table
from ihb_utils.Resolution import Resolution
from ihb_utils.video_utils import (
    ENCODING_SCHEMES,
    EncodingScheme,
    calc_target_resolution,
    eval_recommendation,
    get_tk_video_file_filter,
)

logger = logging.getLogger(__name__)


def _get_prompt_string(v_stream: Dict[str, Any]) -> str:
    prompt_string = []

    width = v_stream["width"]
    height = v_stream["height"]

    prompt_string.append("\n--- Choose Encoding Scheme ---")
    for i, scheme in enumerate(ENCODING_SCHEMES, 1):
        calc_resolution = calc_target_resolution(scheme, width, height)
        scheme_resolution_str = f"{calc_resolution.width}w x {calc_resolution.height}h"
        perc_reduction = 100 * (1 - (calc_resolution.width * calc_resolution.height) / (width * height))
        recommendation_tag = eval_recommendation(v_stream, calc_resolution, scheme.is_source)

        prompt_string.append(f"[{i}] {scheme.name}\t{scheme_resolution_str}\t{perc_reduction:.2f}\t{recommendation_tag}")
    prompt_string.append("[q] Quit")

    return "\n".join(prompt_string)


def _prompt_encoding_scheme_selection(v_stream: Dict[str, Any]) -> EncodingScheme:
    chosen_scheme = None
    prompt_str = _get_prompt_string(v_stream)

    while True:
        print(prompt_str)
        max_choice = len(ENCODING_SCHEMES)
        user_input = input(f"\nEnter the scheme number (1-{max_choice}, q): ").strip()

        if user_input == "q":
            logger.info(f"Quitting immediately.")
            return None

        else:
            if user_input.isdigit():
                input_idx = int(user_input) - 1
                if 0 <= input_idx < len(ENCODING_SCHEMES):
                    chosen_scheme = ENCODING_SCHEMES[input_idx]
                    return chosen_scheme

        logger.warning(f"Invalid choice '{user_input}'. Please enter a number from 1 to {max_choice} or q.")


def encode_file(input_file: str, output_dir: str, selected_scheme: EncodingScheme) -> Tuple[bool, str]:
    probe_data = get_video_metadata(input_file)

    if selected_scheme:
        return encode_video_depr(input_file, output_dir, selected_scheme, probe_data, limit_threads=False)

    format_data = probe_data["format_data"]
    v_stream = probe_data["v_streams"][0]
    a_stream = probe_data["a_streams"][0]

    source_width = v_stream.get("width")
    source_height = v_stream.get("height")

    if not source_width or not source_height:
        logger.critical("Unable to read video dimensions. Cannot proceed.")
        return False, None

    source_resolution = Resolution(source_width, source_height)
    is_landscape = source_width >= source_height

    labels = [
        "Name",
        "Resolution",
        "Codec",
        "Size",
        "Duration",
    ]

    data = [
        probe_data.get("file_name"),
        f"{source_resolution.get_resolution_str(True)} || {source_resolution.get_aspect_ratio_str()} || {'Landscape' if is_landscape else 'Portrait'}",
        f"{v_stream.get('codec_name')} x {a_stream.get('codec_name', 'NO AUDIO')} @ {int(a_stream.get('bit_rate', 0))//1000}k",
        format_size(os.path.getsize(input_file)),
        format_time(format_data.get("duration")),
    ]

    print("Video data:")
    print("\n".join(generate_aligned_table(labels, data)))

    if chosen_scheme := _prompt_encoding_scheme_selection(v_stream):
        result, output_file = encode_video_depr(input_file, output_dir, chosen_scheme, probe_data, limit_threads=False)
        return result, output_file

    return False, None


def main():
    """Main execution function to get file, prompt scheme, build, and execute command."""
    parser = argparse.ArgumentParser(description="Reencode a video file based on the user-selected encoding scheme")
    parser.add_argument("-i", "--input", type=str, help="The input file to be reencoded.")
    parser.add_argument("-o", "--output", type=str, help="The output directory for the reencoded file.")
    parser.add_argument("-s", "--scheme_id", type=str, help="Numerical ID or Name of encoding scheme")
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")

    args = parser.parse_args()
    configure_logging(level=args.level)

    file_path = args.input if (args.input and os.path.isfile(args.input)) else choose_file(get_tk_video_file_filter())
    output_dir = args.output if (args.output and os.path.isdir(args.output)) else choose_directory()

    logger.info(f"Selected file: {file_path}")
    logger.info(f"Output directory: {output_dir}")

    if not (file_path and output_dir):
        logger.info("User cancelled or invalid option. Exiting.")
        return 0

    selected_scheme = None
    if args.scheme_id:
        if str.isdigit(args.scheme_id) and 1 <= int(args.scheme_id) <= len(ENCODING_SCHEMES):
            selected_scheme = ENCODING_SCHEMES[int(args.scheme_id) - 1]
        else:
            selected_scheme = next(scheme for scheme in ENCODING_SCHEMES if scheme.name.lower() == args.scheme_id.lower())
        if not selected_scheme:
            logger.critical(f"Invalid scheme option given: {args.scheme_id}")
            return 1

    start_time = time.perf_counter()
    result, output_file = encode_file(file_path, output_dir, selected_scheme)
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    logger.info(f"Recode script {'succeeded' if result else 'failed'} in {format_time(elapsed_time)}")

    if result and output_file and os.path.isfile(output_file):
        play_file = input("Play new file?")
        if play_file == "y":
            play_video_file(output_file)

        del_file = input(f"Delete original file?")
        if del_file == "y":
            logger.info(f"Deleting {file_path}")
            send2trash(file_path)


if __name__ == "__main__":
    main()
