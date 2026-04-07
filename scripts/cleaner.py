import argparse
import logging
import os

logger = logging.getLogger(__name__)

from ihb_common.utils.dir_utils import choose_directory
from ihb_common.utils.gen_utils import configure_logging


def is_directory_empty_or_single_part(path):
    try:
        entries = os.listdir(path)
        if not entries:  # Directory is empty
            return True
        if len(entries) == 1 and entries[0].endswith(".part"):  # Only one .part file
            return True
        # Check if there are any subdirectories
        has_subdirs = any(os.path.isdir(os.path.join(path, entry)) for entry in entries)
        return not has_subdirs and len(entries) == 1 and entries[0].endswith(".part")
    except Exception as e:
        print(f"Error checking directory {path}: {e}")
        return False


def main():
    """Main execution function with argparse and input type checking."""
    parser = argparse.ArgumentParser(description="Initiates gallery-dl bulk downloading against selected site")
    parser.add_argument("-s", "--site", type=str, help="Site name / identifier")
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")

    args = parser.parse_args()

    configure_logging(level=args.level)

    base_dir = choose_directory()
    if not base_dir:
        print("No directory selected. Exiting.")
        return

    print(f"Scanning subdirectories in {base_dir}")
    try:
        for entry in os.listdir(base_dir):
            full_path = os.path.join(base_dir, entry)
            if os.path.isdir(full_path):
                if is_directory_empty_or_single_part(full_path):
                    try:
                        print(f"Deleting directory: {full_path}")
                        os.rmdir(full_path) if not os.listdir(full_path) else os.remove(os.path.join(full_path, os.listdir(full_path)[0]))
                        print(f"Successfully deleted {full_path}")
                    except Exception as e:
                        print(f"Error deleting directory {full_path}: {e}")
                else:
                    print(f"Skipping {full_path} - not empty or doesn't meet deletion criteria")
    except Exception as e:
        print(f"Error scanning directory {base_dir}: {e}")


if __name__ == "__main__":
    main()
