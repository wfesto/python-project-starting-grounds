import argparse
import logging
import os
import sys
import tkinter as tk
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import filedialog

import xxhash
from humanfriendly import format_size

from ihb_common.utils.gen_utils import configure_logging

logger = logging.getLogger(__name__)


def get_xxh64_hash(file_path):
    try:
        hasher = xxhash.xxh64()
        with open(file_path, "rb") as f:
            while chunk := f.read(4096):
                hasher.update(chunk)
        return file_path, hasher.hexdigest(), None
    except Exception as e:
        return file_path, None, str(e)


def findDupes(base_dirs, prompt=False):
    # Group files by size across all directories
    size_groups = defaultdict(list)
    for base_dir in base_dirs:
        for dirpath, _, filenames in os.walk(base_dir):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                try:
                    size = os.path.getsize(file_path)
                    size_groups[size].append(file_path)
                except OSError as e:
                    print(f"Error getting size for {file_path}: {e}")

    del_size, del_files, del_groups = 0, 0, 0

    # Process each size group with more than one file
    for size, files in size_groups.items():
        if len(files) <= 1:
            continue

        # Compute hash multithreaded
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(get_xxh64_hash, file) for file in files]
            results = [future.result() for future in as_completed(futures)]

        # Handle results, print errors, and sub-group by hash
        sub_groups = defaultdict(list)
        for file_path, file_hash, error in results:
            if error:
                print(f"Error processing {file_path}: {error}")
            else:
                sub_groups[file_hash].append(file_path)

        # For each sub-group with more than one file, print and prompt for deletion
        for key, dup_files in sub_groups.items():
            if len(dup_files) <= 1:
                continue

            print(f"\nProcessing group of {len(dup_files)} files with size {format_size(size)}.")
            print(f"{len(dup_files)} Duplicate files found:")
            for file in dup_files:
                print(f" - {os.path.relpath(file, start=base_dirs[0])}")

            if prompt:
                response = input("Delete all but the one from the first directory with the longest name? (y/n): ").strip().lower()
            else:
                response = "y"

            if response == "y":
                # Find files in the first directory
                first_dir_files = [f for f in dup_files if f.startswith(os.path.abspath(base_dirs[0]))]

                if first_dir_files:
                    # Keep the file with the longest name from the first directory
                    keep = max(first_dir_files, key=lambda x: len(os.path.basename(x)))
                else:
                    # If no files from the first directory, keep the longest-named file overall
                    keep = max(dup_files, key=lambda x: len(os.path.basename(x)))

                num_del = len(dup_files) - 1
                for file_to_delete in dup_files:
                    if file_to_delete != keep:
                        try:
                            os.remove(file_to_delete)
                            print(f"Deleted {file_to_delete}")
                        except OSError as e:
                            print(f"Error deleting {file_to_delete}: {e}")

                print(f"Kept {keep}")
                del_groups += 1
                del_size += num_del * size
                del_files += num_del
            else:
                print("Skipping deletion.")

    print(f"\n\nDeleted {del_groups} groups of duplicates, totalling {del_files} files and freeing {format_size(del_size)}")

    return del_groups, del_files, del_size


def main():
    """Main execution function with argparse and input type checking."""
    parser = argparse.ArgumentParser(description="Automatically selects and sets the best subtitle/CC stream as 'default' for supported files.")
    parser.add_argument("-i", "--input", nargs="*", type=str, help="The input path(s) to compare")
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")

    args = parser.parse_args()
    configure_logging(level=args.level)

    base_dirs = []

    for dir in args.input:
        if os.path.isdir(dir):
            base_dirs.append(dir)
        else:
            logger.warning(f"Discarding {dir}, invalid")

    if not base_dirs:
        print("No directories selected. Exiting.")
        return

    print("Comparing:")
    for dir in base_dirs:
        print(f"{dir}")
    findDupes(base_dirs)


if __name__ == "__main__":
    main()
