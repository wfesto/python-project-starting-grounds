import argparse
import logging
import os

from ihb_common.utils.dir_utils import choose_directory, get_file_list
from ihb_common.utils.gen_utils import configure_logging
from ihb_video.manager.video_manager import get_video_timecode_data
from ihb_video.utils.video_utils import Frame_Time_Data

logger = logging.getLogger(__name__)


def process_timecode_data(file_name: str):
    timecode_data = get_video_timecode_data(file_name)

    num_freeze = 0

    for idx in range(1, len(timecode_data)):
        if timecode_data[idx - 1].pts_time > timecode_data[idx].pts_time:
            logger.error(
                f"ERROR with entry {idx}: {timecode_data[idx-1].pts_time} // {timecode_data[idx].pts_time}"
                f" // {timecode_data[idx - 1].pts_time - timecode_data[idx].pts_time}"
            )
            num_freeze += 1

    logger.info(f"{len(timecode_data)} data points yielded {num_freeze} error(s)")


def main():
    """Main execution function with argparse and input type checking."""
    parser = argparse.ArgumentParser(description="Automatically selects and sets the best subtitle/CC stream as 'default' for supported files.")
    parser.add_argument("-i", "--input", type=str, help="The input path")
    parser.add_argument("-o", "--output", type=str, help="Output directory for report")
    parser.add_argument("-n", "--name", type=str, help="file name for report")
    parser.add_argument("-r", "--recurse", action="store_true", help="Recurse through sub-directories")
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")

    args = parser.parse_args()
    configure_logging(level=args.level)

    # input_dir = args.input if (args.input and os.path.isdir(args.input)) else choose_directory()
    # file_list = get_file_list(input_dir, False)
    process_timecode_data(args.input)


if __name__ == "__main__":
    main()
