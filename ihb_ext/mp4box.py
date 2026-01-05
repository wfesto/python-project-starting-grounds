import logging
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List

from ihb_utils.gen_utils import _run_simple_cli_command
from ihb_utils.video_utils import _build_chapter_file

logger = logging.getLogger("__name__")
MP4BOX_BINARY = "mp4box"
FLAG_FORCED_DEFAULT = "0xC0000000"

if not shutil.which(MP4BOX_BINARY):
    logger.critical(f"No path available for {MP4BOX_BINARY}")
    logger.critical("Exiting.")
    sys.exit(1)


def _embed_subtitles(file_path: str, sub_path: str, sub_title: str = "English Subtitles", sub_lang: str = "eng", is_default: bool = True):
    file_parts = os.path.splitext(file_path)
    output_file = file_parts[0] + "_subbed" + file_parts[1]

    command = [
        MP4BOX_BINARY,
        "-add",
        file_path,
        "-add",
        f"{sub_path}:lang={sub_lang}:txtflags={FLAG_FORCED_DEFAULT}",
        "-new",
        output_file,
    ]

    result = _run_simple_cli_command(command)
    if not result or result.returncode != 0:
        logger.error(f"No results, or {MP4BOX_BINARY} call failed.")
        if os.path.exists(output_file):
            os.remove(output_file)
        return None

    return output_file


def _update_default_subtitles(file_path: str, probe_data: Dict[str, Any], selected_index: int, is_default: bool) -> bool:
    update_command = "enable" if is_default else "disable"
    ffprobe_stream = next(stream for stream in probe_data["s_streams"] if stream["index"] == selected_index)

    calc_stream_idx = selected_index + 1

    stream_id = str.split(ffprobe_stream.get("id"), "x")
    if len(stream_id) == 2:
        calc_stream_idx = stream_id[1]

    command = [
        MP4BOX_BINARY,
        f"-{update_command}",
        calc_stream_idx,
        file_path,
    ]

    result = _run_simple_cli_command(command)

    if not result or result.returncode != 0:
        logger.error(f"No results, or {MP4BOX_BINARY} call failed.")
        return False
    return True


def _set_chapters(file_path, probe_data_list: List, auto_chapter: bool) -> bool:
    if not os.path.exists(file_path) or not probe_data_list:
        logger.warning(" -> No chapter data provided. No update performed")
        return
    logger.info("Building chapter file.")

    chapter_file = _build_chapter_file(probe_data_list)

    if not auto_chapter:
        logger.info(f"Chapter file created at {chapter_file}. Press enter once it is correct.")
        input()

    logger.info(f" -> Updating {file_path} chapters with {len(chapter_file)} chapters")
    command = [
        MP4BOX_BINARY,
        "-chap",
        chapter_file,
        file_path,
    ]

    result = _run_simple_cli_command(command)
    os.remove(chapter_file)

    if not result or result.returncode != 0:
        logger.error(f" -> {MP4BOX_BINARY} call failed.")
        return False

    return True


if __name__ == "__main__":
    print()
