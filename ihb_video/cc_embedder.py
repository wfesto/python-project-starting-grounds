import argparse
import logging
import os
import re
import shutil

from ihb_ext.video_manager import embed_subtitles, is_supported_file
from ihb_utils.dir_utils import choose_directory
from ihb_utils.gen_utils import configure_logging

logger = logging.getLogger(__name__)
SEASON_EPISODE_REGEX = re.compile(r"[Ss]\d{1,2}\.{0,1}[Ee]\d{1,2}")


def embed_subtitle_file(input_file: str, sub_file: str, is_preview: bool = False) -> str:
    if is_preview:
        logger.info(f"Match found:")
        logger.info(f" --> {input_file}")
        logger.info(f" --> {sub_file}")
    else:
        return embed_subtitles(input_file, sub_file)


def process_directory(input_dir: str, is_preview: bool = False) -> bool:
    logger.info(f"Processing {input_dir}")

    orig_dir = os.path.join(input_dir, "_orig")
    sub_dir = os.path.join(input_dir, "_sub_files")

    os.makedirs(orig_dir, exist_ok=True)
    os.makedirs(sub_dir, exist_ok=True)

    vid_map = {}
    sub_map = {}

    for dir_path, _, file_list in os.walk(input_dir):
        for file in file_list:
            ep_num = SEASON_EPISODE_REGEX.search(file)
            if ep_num:
                ep_num_str = ep_num[0].upper()
                if is_supported_file(file):
                    vid_map[ep_num_str] = os.path.join(dir_path, file)
                elif file.endswith(".srt"):
                    sub_map[ep_num_str] = os.path.join(dir_path, file)

    for ep_num, video_file in vid_map.items():
        sub_file = sub_map.get(ep_num, None)
        if sub_file and video_file:
            logger.info(f" -> Embedding {video_file} with {sub_file}")
            if result := embed_subtitle_file(video_file, sub_file, is_preview):
                logger.info(f" -> Success: {result} genereted.")
                shutil.move(video_file, orig_dir)
                shutil.move(sub_file, sub_dir)
            else:
                logger.error(" -> ERROR: Embedding failed.")


def main():
    """Main execution function with argparse and input type checking."""
    parser = argparse.ArgumentParser(description="Automatically selects and sets the best subtitle/CC stream as 'default' for supported files.")
    parser.add_argument("-i", "--input", type=str, help="The input path")
    parser.add_argument("-s", "--subtitle_file", type=str, help="Force specific subtitle file to provided movie file")
    parser.add_argument("-p", "--preview", action="store_true", help="Preview matches but don't do anything.")
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")

    args = parser.parse_args()

    configure_logging(level=args.level)

    if args.input and os.path.isfile(args.input) and args.subtitle_file and os.path.isfile(args.subtitle_file):
        embed_subtitle_file(args.input, args.subtitle_file)

    else:
        input_dir = args.input if (args.input and os.path.isdir(args.input)) else choose_directory()
        if input_dir:
            process_directory(input_dir, args.preview)
        else:
            logger.info("No valid input directory. Exiting.")


if __name__ == "__main__":
    main()
