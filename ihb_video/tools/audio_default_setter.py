import argparse
import logging
import os

from ihb_common.utils.gen_utils import VERBOSE_LEVEL_NUM, configure_logging
from ihb_video.manager import video_manager
from ihb_video.types.stream_models import StreamType
from ihb_video.utils.stream_utils import *

logger = logging.getLogger(__name__)


def process_file(input_file: str) -> bool:
    file_name = os.path.basename(input_file)
    logger.info(f"Processing: {file_name}")

    probe_data = video_manager.get_video_metadata(input_file)
    if probe_data["a_count"] > 1:
        chosen_str_idx = -1
        eng_streams = filter_streams_eng(probe_data["a_streams"])
        if len(eng_streams) == 1:
            chosen_str_idx = eng_streams[0]["index"]
            logger.info(f" --> Stream {chosen_str_idx} chosen")
            if eng_streams[0].get("dispositon", {}).get("default", 0) == 1:
                logger.info(" --> Stream is already default, skipping.")
                return True
            else:
                old_default_stream = next((s for s in probe_data["a_streams"] if s.get("disposition", {}).get("default") == 1), None)
                video_manager.update_default_stream(
                    file_path=input_file, probe_data=probe_data, selected_index=old_default_stream["index"], is_default=False, stream_type=StreamType.AUDIO
                )

                video_manager.update_default_stream(
                    file_path=input_file, probe_data=probe_data, selected_index=chosen_str_idx, is_default=True, stream_type=StreamType.AUDIO
                )

    else:
        logger.log(VERBOSE_LEVEL_NUM, f"{input_file} doesn't have multiple audio streams, processing unnecessary")


def process_directory(input_dir: str) -> int:
    logger.info(f"--- Starting Audio Default in Dir: {input_dir}")

    processed_count = 0

    for dir_name, _, file_list in os.walk(input_dir):
        for file_name in file_list:
            file_path = os.path.join(dir_name, file_name)
            logger.info(file_path)

            if video_manager.is_supported_file(file_name):
                if process_file(file_path):
                    processed_count += 1
                else:
                    logger.warning(" -> File not processed / processing unsuccessful")
            else:
                logger.log(VERBOSE_LEVEL_NUM, f" -> Skipping {file_name}, unsupported file type")

    logger.info(f"--- Audio Default Processing Complete for {input_dir}. Total files updated: {processed_count} ---")
    return processed_count


def process_path(input_path: str) -> int:
    if not input_path and not os.path.exists(input_path):
        logger.error(f"{input_path} does not exist. Exiting.")
        return -1

    if os.path.isdir(input_path):
        return process_directory(input_path)
    elif os.path.isfile(input_path):
        return process_file(input_path)
    else:
        logger.error(f"Invalid file or directory path: {input_path}")
        return -1


def main():
    parser = argparse.ArgumentParser(description="Automatically selects and sets the best subtitle/CC stream as 'default' for supported files.")
    parser.add_argument("-i", "--input", type=str, help="The input path. Can be a single file or a directory")
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")

    args = parser.parse_args()

    configure_logging(level=args.level)

    input_path = args.input
    if not input_path:
        logger.error("No valid input path provided. Exiting.")
        return 1

    processed_files = process_path(args.input)
    if processed_files < 0:
        logger.error("Error encountered during processing.")
    else:
        logger.info(f"{processed_files} files successfully processed.")


if __name__ == "__main__":
    main()
