import argparse
import logging
import os
from typing import List

from humanfriendly import format_size

from ihb_utils.file_utils import get_xxh64_hash
from ihb_utils.gen_utils import configure_logging

logger = logging.getLogger(__name__)


def find_duplicates(ref_dir_list: List, input_dir_list: List) -> None:
    file_size_dict = {}
    ref_sub_dir = []
    for ref_dir in ref_dir_list:
        for dir_name, _, file_list in os.walk(ref_dir):
            ref_sub_dir.append(dir_name)
            for file in file_list:
                file_size = os.path.getsize(os.path.join(dir_name, file))
                file_size_dict.setdefault(file_size, []).append(os.path.join(dir_name, file))

    for input_dir in input_dir_list:
        for dir_name, _, file_list in os.walk(input_dir):
            for file in file_list:
                file_size = os.path.getsize(os.path.join(dir_name, file))
                file_size_dict.setdefault(file_size, []).append(os.path.join(dir_name, file))

    size_matches_dict = {key: value for key, value in file_size_dict.items() if len(value) > 1}

    size_list = sorted(size_matches_dict, reverse=True)
    for size in size_list:
        file_list = size_matches_dict[size]
        hash_dict = {}
        for file in file_list:
            xx64_hash = get_xxh64_hash(file)
            hash_dict.setdefault(xx64_hash, set()).add(file)

        hash_match_dict = {key: value for key, value in hash_dict.items() if len(value) > 1}

        for hash in hash_match_dict.keys():
            hash_file_list = list(hash_match_dict[hash])
            print(f"{hash} || {format_size(size)}")
            for idx, hash_file in enumerate(hash_file_list, 1):
                is_in_ref = os.path.dirname(hash_file) in ref_sub_dir
                print(f" [{idx}]{" ** " if is_in_ref else ""} {hash_file}")
            print(" [s] Skip")

            user_choice = input("Delete one?")
            if user_choice.isdigit() and (int(user_choice) - 1) in range(0, len(hash_file_list)):
                del_file = hash_file_list[int(user_choice) - 1]
                logger.info(f"Deleting {del_file}")
                os.remove(del_file)
            else:
                print("Skipping.")


def main():
    """Main execution function with argparse and input type checking."""
    parser = argparse.ArgumentParser(description="Automatically selects and sets the best subtitle/CC stream as 'default' for supported files.")
    parser.add_argument("-b", "--base", type=str, nargs="+", help="Base directory, will not delete from.")
    parser.add_argument("-i", "--input", type=str, nargs="+", help="The input paths")
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")

    args = parser.parse_args()

    configure_logging(level=args.level)
    base_dir = args.base
    input_dir_list = args.input

    find_duplicates(base_dir, input_dir_list)


if __name__ == "__main__":
    main()
