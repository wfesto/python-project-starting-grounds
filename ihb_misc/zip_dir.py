import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
import time

from ihb_ext.video_manager import disable_default_subtitles, update_default_subtitles
from ihb_ext.zip7 import archive_files_to_7z
from ihb_utils.file_utils import choose_directory, choose_file
from ihb_utils.gen_utils import configure_logging, format_time
from ihb_utils.video_utils import get_tk_video_file_filter

logger = logging.getLogger(__name__)

SEASON_EPISODE_REGEX = re.compile(r".*?([Ss]\d{1,2}[\.x]{0,1}[Ee]\d{1,2}).*")


def get_password():
    password = input("Enter the password: ")
    password2 = input("Confirm the password: ")

    if password != password2:
        logger.critical("Error: Passwords do not match!")
        sys.exit(1)


def compress_files_with_7zip(file_list, password: str, is_short_mode: bool = False):
    file_count = 0
    for file_name in file_list:
        if os.path.isfile(file_name):
            logger.info(f"Processing {file_name}")

            default_subt_idx = disable_default_subtitles(file_name)
            if default_subt_idx == -1:
                logger.info(" -> No default subtitles found.")
            else:
                logger.info(f" -> Removed default subtitles at index {default_subt_idx}")

            short_file_name = os.path.basename(file_name)

            archive_name = os.path.splitext(short_file_name)[0]

            episode_tag = SEASON_EPISODE_REGEX.search(archive_name)
            logger.debug(episode_tag)
            if episode_tag and is_short_mode:
                archive_name = f"s{episode_tag.group(1)}"

            logger.info(" -> Generating archive file.")
            archived_file = archive_files_to_7z([file_name], archive_name=archive_name, password=password)

            if not archived_file:
                logger.error(f"Error archiving {file_name} into {archive_name}")
            else:
                file_count += 1

            if default_subt_idx >= 0:
                logger.info(f" -> Restoring default subtitle stream {default_subt_idx}")
                subs_restored = update_default_subtitles(file_path=file_name, selected_index=default_subt_idx, is_default=True)

    logger.info(f"Successfully compressed {file_count} files.")


def main():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("-i", "--input", type=str, help="The directory path containing the video files to compress.")
    parser.add_argument("-p", "--password", type=str, help="Password to protect 7z archive(s)")
    parser.add_argument("-f", "--file_mode", action="store_true", help="Enable single-file mode")
    parser.add_argument("-s", "--short_mode", action="store_true", help="Enable short-name mode")
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")
    args = parser.parse_args()

    configure_logging(level=args.level)

    input_path = args.input
    password = args.password or get_password()

    file_list = []

    if args.file_mode:
        file_list.append(input_path if input_path and os.path.isfile(input_path) else choose_file(file_types=get_tk_video_file_filter()))
    else:
        input_dir = input_path if input_path and os.path.isdir(input_path) else choose_directory()
        if not input_dir or not os.path.isdir(input_dir):
            logger.critical(f"Invalid input {input_path}. Exiting.")
            sys.exit(1)
        file_list = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]

    if file_list:
        compress_files_with_7zip(file_list, password, args.short_mode)
    else:
        logger.info("No input selected. Exiting.")


if __name__ == "__main__":
    main()
