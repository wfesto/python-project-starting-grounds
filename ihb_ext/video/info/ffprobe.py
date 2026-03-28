import json
import logging
import os
import shutil
import sys
from typing import Any, Dict, List

from ihb_common.utils.gen_utils import _run_simple_cli_command
from ihb_video.types.video_models import FrameTimeData

logger = logging.getLogger("__name__")
FFPROBE_BINARY = "ffprobe"

if not shutil.which(FFPROBE_BINARY):
    logger.critical(f"No path available for {FFPROBE_BINARY}")
    logger.critical("Exiting.")
    sys.exit(1)


def _get_stream_size(file_name: str, stream_type: str, stream_index: int) -> int:
    command = [
        FFPROBE_BINARY,
        "-v",
        "error",
        "-select_streams",
        f"{stream_type[0]}:{stream_index}",
        "-show_entries",
        "packet=size",
        "-of",
        "compact=p=0:nk=1",
        file_name,
    ]

    packet_size_str = _run_simple_cli_command(command).stdout
    packet_sizes = [int(size) for size in packet_size_str.strip("\n").split("\n")]
    stream_size = sum(packet_sizes)
    return stream_size


def _get_timecode_data(file_path: str) -> List | None:
    if not os.path.exists(file_path):
        logger.error(f"{file_path} not found")
        return None

    command = [
        FFPROBE_BINARY,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "frame=pts_time",
        "-of",
        "json",
        file_path.replace(os.path.sep, "/"),
    ]

    result = _run_simple_cli_command(command=command)
    if not result or result.returncode != 0:
        logger.error(f"No results, or {FFPROBE_BINARY} call failed.")
        return None

    result_js = json.loads(result.stdout)

    packet_data_list = [FrameTimeData(entry) for entry in result_js["frames"]]
    logger.debug(f"{len(packet_data_list)} packets found in {file_path}")

    return packet_data_list


def _get_video_metadata(file_path: str) -> Dict[str, Any] | None:
    if not os.path.exists(file_path):
        logger.error(f"{file_path} not found")
        return None

    command = [
        FFPROBE_BINARY,
        "-v",
        "error",
        "-show_streams",
        "-show_entries",
        "stream",
        "-find_stream_info",
        "-show_format",
        "-show_entries",
        "format",
        "-of",
        "json",
        file_path.replace(os.path.sep, "/"),
    ]

    result = _run_simple_cli_command(command=command)

    if not result or result.returncode != 0:
        logger.error(f"No results, or {FFPROBE_BINARY} call failed.")
        return None

    result_js = json.loads(result.stdout)
    data = {}

    data["file_name"] = os.path.basename(file_path)
    data["full_data"] = result_js
    data["format_data"] = result_js["format"]

    streams = result_js["streams"]
    v_streams = list(filter(_get_stream_filter("video"), streams))
    a_streams = list(filter(_get_stream_filter("audio"), streams))
    s_streams = list(filter(_get_stream_filter("subtitle"), streams))

    data["v_streams"] = v_streams
    data["v_count"] = len(v_streams) if v_streams else 0
    data["a_streams"] = a_streams
    data["a_count"] = len(a_streams) if a_streams else 0
    data["s_streams"] = s_streams
    data["s_count"] = len(s_streams) if s_streams else 0

    return data if data is not None else None


def _get_default_subtitles(file_path: str, probe_data: Dict[str, Any] = None) -> tuple[int, Dict[str, Any]]:
    logger.debug(f"Removing default subtitle stream in {file_path}.")
    probe_data = probe_data or _get_video_metadata(file_path)

    default_idx = -1
    sub_streams = probe_data.get("s_streams", [])

    if default_sub := next((stream for stream in sub_streams if stream.get("disposition", {}).get("default", 0) == 1), None):
        default_idx = default_sub["index"]

    return default_idx, probe_data


def _get_stream_filter(codec_type: str):
    return lambda stream: stream["codec_type"] == codec_type
