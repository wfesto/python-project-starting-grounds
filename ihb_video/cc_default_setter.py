import argparse
import logging
import os
import sys
from typing import Any, Dict, List

from ihb_ext.video_manager import (
    get_video_metadata,
    is_supported_file,
    update_default_subtitles,
)
from ihb_utils.gen_utils import configure_logging
from ihb_utils.subtitle_utils import (
    filter_streams_eng,
    filter_streams_unknown,
    get_stream_tag,
    get_subtitle_size_est,
    get_subtitle_stream_desc,
)

logger = logging.getLogger(__name__)


def _apply_stream_selection_logic(sub_streams: List, keyword: str) -> tuple[Dict[str, Any], str]:
    chosen_stream = None
    chosen_method = None

    if sub_streams:
        chosen_stream = next((stream for stream in sub_streams if stream.get("disposition", {}).get("hearing_impaired", 0) == 1), None)
        chosen_method = f"disposition.hearing_impaired + {keyword}"

        if not chosen_stream:
            chosen_stream = next((stream for stream in sub_streams if "sdh" in get_stream_tag(stream, "title").lower()), None)
            chosen_method = f"SDH + {keyword}"

        if not chosen_stream:
            potential_stream = max(sub_streams, key=get_subtitle_size_est)
            chosen_stream = potential_stream if get_subtitle_size_est(potential_stream) > 0 else None
            chosen_method = f"Largest-ish {keyword}"

        if not chosen_stream:
            chosen_stream = sub_streams[0]
            chosen_method = f"First {keyword}"

    return chosen_stream, chosen_method


def _select_default_subtitle_stream(sub_streams: List) -> tuple[int, str]:
    """
    Selects the best subtitle stream index based on priority:
    SDH + English > Largest-ish English > First English > First stream 1
    Returns the selected stream index and method of choosing, or None
    """

    if not sub_streams:
        logger.warning("No subtitles available")
        return

    chosen_stream = None
    chosen_method = None

    eng_subtitle_streams = filter_streams_eng(sub_streams)
    und_subtitle_streams = filter_streams_unknown(sub_streams)

    if eng_subtitle_streams:
        chosen_stream, chosen_method = _apply_stream_selection_logic(eng_subtitle_streams, "English")

    elif und_subtitle_streams:
        chosen_stream, chosen_method = _apply_stream_selection_logic(und_subtitle_streams, "Unknown")

    if not chosen_stream:
        chosen_stream = sub_streams[0]
        chosen_method = "First stream"

    index = chosen_stream["index"] if chosen_stream else None

    return index, chosen_method


def process_file(file_path: str) -> bool:
    """
    Handles the entire process for a single supported file: probing, selection, and editing.
    Returns True if successfully processed, False otherwise.
    """
    file_name = os.path.basename(file_path)
    logger.info(f"[Processing: {file_name}]")

    probe_data = get_video_metadata(file_path)

    if not probe_data:
        logger.warning(" -> SKIPPED - Could not retrieve stream data.")
        return False

    if probe_data["s_count"] == 0:
        logger.info(" -> SKIPPED - No subtitle streams found")
        return False

    sub_streams = probe_data["s_streams"]
    ff_idx, chosen_method = _select_default_subtitle_stream(sub_streams)

    if ff_idx is None:
        logger.warning(" -> SKIPPED - No suitable subtitle streams found.")
        return False

    chosen_stream = next(s for s in sub_streams if s.get("index") == ff_idx)

    logger.info(f" -> Chosen: {get_subtitle_stream_desc(chosen_stream)} | Method: {chosen_method}")
    if chosen_stream.get("disposition", {}).get("default") == 1:
        logger.info(" -> Chosen stream is ALREADY the default. Skipping edit.")
        return True

    old_default_stream = next((s for s in sub_streams if s.get("disposition", {}).get("default") == 1), None)
    if old_default_stream and old_default_stream["index"] != chosen_stream["index"]:
        logger.info(f" -> Removing default subtitles - {get_subtitle_stream_desc(old_default_stream)}")
        update_default_subtitles(file_path=file_path, probe_data=probe_data, selected_index=old_default_stream["index"], is_default=False)

    logger.info(f" -> Setting default subtitles - {get_subtitle_stream_desc(chosen_stream)}")
    update_default_subtitles(file_path=file_path, probe_data=probe_data, selected_index=ff_idx, is_default=True)

    return True


def process_directory(base_dir: str, proc_subs: bool = False, ignore_files: List[str] = None):
    """Iterates through all files in the directory and calls process_file() for each."""
    logger.info(f"--- Starting CC Default in Dir: {base_dir} ---")

    processed_count = 0

    for file_name in os.listdir(base_dir):
        file_path = os.path.join(base_dir, file_name)

        logger.info(file_path)
        if os.path.isdir(file_path) and proc_subs and not file_name == ".":
            processed_count += process_directory(base_dir=file_path, proc_subs=proc_subs, ignore_files=ignore_files)
        elif os.path.isfile(file_path):
            if is_supported_file(file_name):
                if process_file(file_path):
                    processed_count += 1
                else:
                    logger.warning(" -> File not processed / processing unsuccessful")
            else:
                logger.info(f" -> Skipping {file_name}, unsupported file type")

    logger.info(f"--- CC Default Processing Complete for {base_dir}. Total files updated: {processed_count} ---")
    return processed_count


def main():
    """Main execution function with argparse and input type checking."""
    parser = argparse.ArgumentParser(description="Automatically selects and sets the best subtitle/CC stream as 'default' for supported files.")
    parser.add_argument("-i", "--input", type=str, help="The input path. Can be a single file or a directory containing supported files.")
    parser.add_argument("-s", "--subs", action="store_true", help="Include subdirectories when processing an input directory")
    parser.add_argument("-r", "--recurse", action="store_true", help="Recurse through all subdirectories in input directory")
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")

    args = parser.parse_args()

    configure_logging(level=args.level)

    input_path = args.input
    if not input_path:
        logger.critical("No valid input path provided. Exiting.")
        return 1

    print(f"{args.subs} || {args.recurse}")

    if os.path.isdir(input_path):
        process_directory(input_path, args.subs, args.recurse)
    elif os.path.isfile(input_path):
        process_file(input_path)
    else:
        logger.critical(f"Error: Invalid file or directory path: {input_path}")
        return 1


if __name__ == "__main__":
    main()
