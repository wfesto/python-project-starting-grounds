import argparse
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List

from humanfriendly import format_size

from ihb_ext.video_manager import get_video_metadata

from .file_utils import choose_directory
from .gen_utils import configure_logging, generate_aligned_table
from .video_utils import remove_res_from_file_name

logger = logging.getLogger(__name__)


def get_file_list(base_dir: str, is_recurse: bool) -> List | None:
    if not os.path.exists(base_dir):
        logger.error(f"{base_dir} not found")
        return None

    ret_file_list = []

    for sub_dir, _, file_list in os.walk(base_dir):
        for file_name in file_list:
            ret_file_list.append(os.path.join(sub_dir, file_name))

    return ret_file_list


def sub_size(base_dir: str, sort_key: str = None, sort_desc: bool = False) -> None:
    logger.info(f"--- Calculating top-level sub cumulative sizes for {base_dir} ---")
    logger.info(f" -> Sorting by {"name" if not sort_key else sort_key}, {"desc" if sort_desc else "asc"}")
    dir_path = Path(base_dir)

    sub_data_list = []
    sub_dir_list = [str(p) for p in dir_path.iterdir() if p.is_dir()]
    for sub_dir in sub_dir_list:
        sub_size = 0.0
        for sub_name, _, file_list in os.walk(sub_dir):
            sub_size += sum(os.path.getsize(os.path.join(base_dir, sub_name, f)) for f in file_list)
        sub_data_list.append((sub_dir, sub_size))

    if sort_key == "size":
        list.sort(sub_data_list, key=lambda f: f[1], reverse=sort_desc)

    sub_name = [sub[0] for sub in sub_data_list]
    sub_size = [format_size(sub[1]) for sub in sub_data_list]

    for row in generate_aligned_table(sub_name, sub_size):
        print(row)


def reorg(input_dir: str):
    EXTENSIONS = {
        "IMAGES": [".jpeg", ".jpg", ".png", ".gif"],
        "VIDEO": [".avi", ".flv", ".mkv", ".mov", ".mpg", ".mp4", ".m4v", ".wmv"],
        "AUDIO": [".mp3", ".aac"],
        "ARCHIVE": [".zip", ".7z", ".rar"],
        "AV": [".asf", ".mpeg", ".mov", ".ogg", ".webm"],
    }

    NEW_HOMES: Dict = {}
    OLD_DIRS = set()

    if not os.path.isdir(input_dir):
        return

    for dir_name, _, file_list in os.walk(input_dir):
        if os.path.basename(dir_name).upper() in EXTENSIONS.keys() and str(Path(dir_name).parent) == input_dir:
            continue
        OLD_DIRS.add(dir_name)
        for file_name in file_list:
            ext = os.path.splitext(file_name)[1].lower()
            target_dir = next((item[0] for item in EXTENSIONS.items() if ext in item[1]), "UNKNOWN")
            NEW_HOMES.setdefault(target_dir, []).append(os.path.join(dir_name, file_name))

    av_list = NEW_HOMES.pop("AV", [])
    for av_file in av_list:
        file_av_data = get_video_metadata(av_file)
        new_home = "VIDEO" if file_av_data["v_count"] > 0 else "AUDIO"
        NEW_HOMES.setdefault(new_home, []).append(av_file)

    for key in NEW_HOMES.keys():
        new_dir = os.path.join(input_dir, key.lower())
        if not os.path.exists(new_dir):
            os.mkdir(new_dir)

        print(f"{len(NEW_HOMES[key])} {key} files")

        for file in NEW_HOMES[key]:
            try:
                shutil.move(file, new_dir)
            except Exception as e:
                print(f"Error {file} || {str(e)}")

    del_dirs = list(OLD_DIRS)
    del_dirs.sort(key=lambda dir: len(dir), reverse=True)

    for dir in del_dirs:
        if not os.listdir(dir):
            os.rmdir(dir)


def strip_res(input_dir: str):

    for dir_name, _, file_name_list in os.walk(input_dir):
        for file_name in file_name_list:
            old_file_path = os.path.join(dir_name, file_name)
            new_file_name = remove_res_from_file_name(file_name)
            new_file_path = os.path.join(dir_name, new_file_name)

            os.rename(old_file_path, new_file_path)


def main():
    """Main execution function with argparse and input type checking."""
    parser = argparse.ArgumentParser(description="Call various directory-based utility functions")
    parser.add_argument("-a", "--action", choices=["reorg", "sub_size", "strip-res"], help="Action to take")
    # sub_size - calculate and print the size of each top-level subdirectory within the targeted directory
    parser.add_argument("-i", "--input", type=str, help="Input directory to act upon")
    parser.add_argument("-s", "--sort", choices=["size"], help="Override default (alpha) sort method for output when appropriate.")
    parser.add_argument("-sd", "--sort_descending", action="store_true", help="Sort descending")
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")

    args = parser.parse_args()
    configure_logging(level=args.level)

    base_dir = args.input if args.input and os.path.isdir(args.input) else choose_directory()
    if not base_dir:
        logger.error(f"Invalid or no directory path provided: {base_dir}")
        return 1

    if args.action == "sub_size":
        sub_size(base_dir, sort_key=args.sort, sort_desc=args.sort_descending)

    elif args.action == "reorg":
        reorg(base_dir)

    elif args.action == "strip-res":
        strip_res(base_dir)


if __name__ == "__main__":
    main()
