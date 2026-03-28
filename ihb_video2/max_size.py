import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List

from humanfriendly import format_size

from ihb_common.utils.dir_utils import choose_directory
from ihb_common.utils.gen_utils import configure_logging

logger = logging.getLogger(__name__)


def get_file_info(file_path: str) -> str:
    path_obj = Path(file_path)
    stats = path_obj.stat()
    size = stats.st_size
    size_str = format_size(size)
    t_str = "\t" if len(size_str) < 8 else ""
    return f"{size_str}{t_str}\t{file_path}"


def output_list(file_list: List, max_count: int = 1) -> None:
    file_list.sort(key=lambda file: Path(file).stat().st_size, reverse=True)
    for file in file_list[:max_count]:
        print(get_file_info(file))


def process_directory(input_dir: str) -> List:
    logger.info(f"Processing {input_dir}")
    full_list = []

    for dir_name, _, file_list in os.walk(input_dir):
        full_list.extend([os.path.join(dir_name, file) for file in file_list])

    return full_list


def main():
    """Main execution function with argparse and input type checking."""
    parser = argparse.ArgumentParser(description="Automatically selects and sets the best subtitle/CC stream as 'default' for supported files.")
    parser.add_argument("-i", "--input", type=str, help="The input path")
    parser.add_argument("-c", "--count", type=int, help="Number of files to show")
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")

    args = parser.parse_args()
    configure_logging(level=args.level)

    input_dir = args.input if os.path.isdir(args.input) else choose_directory()
    file_list = process_directory(input_dir)
    output_list(file_list, args.count)


if __name__ == "__main__":
    main()
