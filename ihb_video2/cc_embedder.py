import argparse
import logging
import os
import re
import shutil
from pathlib import Path

from ihb_common.utils.gen_utils import configure_logging
from ihb_video.manager import video_manager

logger = logging.getLogger(__name__)
SEASON_EPISODE_REGEX = re.compile(r"[Ss]\d{1,2}\.{0,1}[Ee]\d{1,2}")


def process_directory(input_dir: str, subs_dir: str, is_preview_mode: bool = False) -> bool:
    if not os.path.isdir(input_dir):
        logger.error(f"Invalid input directory: {input_dir}")
        return False

    logger.info(f"Processing {input_dir}")
    subs_dir = subs_dir if subs_dir and os.path.isdir(subs_dir) else input_dir
    logger.info(f"Subtitle Source: {subs_dir}")

    orig_dir = os.path.join(input_dir, "_orig")
    sub_dir = os.path.join(input_dir, "_sub_files")

    os.makedirs(orig_dir, exist_ok=True)
    os.makedirs(sub_dir, exist_ok=True)

    vid_map = {}
    sub_map = {}

    for dir_path, _, file_list in os.walk(input_dir):
        for file in file_list:
            file_path = os.path.join(dir_path, file)
            ep_id_rgx = SEASON_EPISODE_REGEX.search(file_path)
            if ep_id_rgx:
                ep_id = ep_id_rgx[0].upper()
                if video_manager.is_supported_file(file_path):
                    vid_map[ep_id] = file_path
                elif file.endswith(".srt"):
                    if ep_id in sub_map.keys():
                        if Path(file_path).stat().st_size > Path(sub_map[ep_id]).stat().st_size:
                            sub_map[ep_id] = file_path
                    else:
                        sub_map[ep_id] = file_path
                else:
                    logger.warning(f"Unsupported file: {file_path}")

    for ep_id, video_file in vid_map.items():
        sub_file = sub_map.get(ep_id, None)
        if sub_file and video_file:
            logger.info(f" -> Embedding {video_file} with {sub_file}")
            if is_preview_mode:
                continue
            else:
                if result := video_manager.embed_subtitles(video_file, sub_file):
                    logger.info(f" -> Success: {result} genereted.")
                    shutil.move(video_file, orig_dir)
                    shutil.move(sub_file, sub_dir + "/" + ep_id + ".srt")
                else:
                    logger.error(" -> ERROR: Embedding failed.")


def main():
    """Main execution function with argparse and input type checking."""
    parser = argparse.ArgumentParser(description="Automatically selects and sets the best subtitle/CC stream as 'default' for supported files.")
    parser.add_argument("-i", "--input", type=str, help="The input path")
    parser.add_argument("-s", "--subs-folder", type=str, help="Subtitle directory input (if different)")
    parser.add_argument("-f", "--sub-file", type=str, help="Force specific subtitle file to provided movie file")
    parser.add_argument("-p", "--preview", action="store_true", help="Preview matches but don't do anything.")
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")

    args = parser.parse_args()

    configure_logging(level=args.level)

    if args.input and os.path.isfile(args.input) and args.sub_file and os.path.isfile(args.sub_file):
        video_manager.embed_subtitle_file(args.input, args.subtitle_file)

    else:
        process_directory(args.input, args.subs_folder, args.preview)


if __name__ == "__main__":
    main()
