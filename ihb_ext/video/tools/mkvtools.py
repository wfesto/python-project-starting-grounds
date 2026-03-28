import logging
import os
import shutil
import sys
from typing import Any

from ihb_common.utils.gen_utils import _run_simple_cli_command
from ihb_video.types.stream_models import StreamType
from ihb_video.utils.video_utils import _build_chapter_file

logger = logging.getLogger("__name__")

MKV_PROPEDIT_BINARY = "mkvpropedit"
MKV_MERGE_BINARY = "mkvmerge"

if not shutil.which(MKV_PROPEDIT_BINARY):
    logger.critical(f"No path available for {MKV_PROPEDIT_BINARY}")
    logger.critical("Exiting.")
    sys.exit(1)


if not shutil.which(MKV_MERGE_BINARY):
    logger.critical(f"No path available for {MKV_MERGE_BINARY}")
    logger.critical("Exiting.")
    sys.exit(1)


def _embed_subtitles(file_path: str, sub_path: str, sub_title: str = "English (Full)", sub_lang: str = "eng", is_default: bool = True) -> str | None:
    file_parts = os.path.splitext(file_path)
    output_file = file_parts[0] + "_subbed" + file_parts[1]

    command = [
        MKV_MERGE_BINARY,
        "-o",
        output_file,
        file_path,
        "--language",
        f"0:{sub_lang}",
        "--default-track",
        f"0:{1 if is_default else 0}",
        "--track-name",
        f"0:{sub_title}",
        sub_path,
    ]

    result = _run_simple_cli_command(command)
    if not result or result.returncode != 0:
        logger.error(f"No results, or {MKV_MERGE_BINARY} call failed.")
        if os.path.exists(output_file):
            os.remove(output_file)
        return None

    return output_file


def _update_default_stream(file_path: str, probe_data: dict[str, Any], selected_index: int, is_default: bool, stream_type: StreamType) -> bool:
    logger.info(f" -> Updating default {stream_type.name} stream {selected_index} to default={is_default} in {file_path}")
    offset = _get_stream_index_offset(probe_data, selected_index, stream_type.name.lower())
    logger.debug(f" -> mkvtools offset calculated: {offset}")
    cmd_idx = selected_index - offset + 1
    stream_type_flag = stream_type.name[0].lower()
    command = [
        MKV_PROPEDIT_BINARY,
        file_path,
        "--edit",
        f"track:{stream_type_flag}{cmd_idx}",
        "--set",
        f"flag-default={int(is_default)}",
    ]

    result = _run_simple_cli_command(command)

    if not result or result.returncode != 0:
        logger.error(f"No results, or {MKV_PROPEDIT_BINARY} call failed.")
        return False
    return True


def _get_stream_index_offset(probe_data: dict[str, Any], selected_index: int, stream_type: str) -> int:
    offset = sum(1 for stream in probe_data["full_data"]["streams"] if stream["index"] < selected_index and stream["codec_type"] != stream_type)
    return offset


def _set_chapters(file_path, probe_data_list: list, auto_chapter: bool) -> bool:
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
        MKV_PROPEDIT_BINARY,
        file_path,
        "--chapters",
        chapter_file,
    ]

    result = _run_simple_cli_command(command)
    os.remove(chapter_file)

    if not result or result.returncode != 0:
        logger.error(f" -> {MKV_PROPEDIT_BINARY} call failed.")
        return False

    return True
