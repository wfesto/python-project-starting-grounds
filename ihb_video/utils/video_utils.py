import logging
import os
import re
from math import gcd, log10
from typing import Any

from ihb_common.utils.gen_utils import format_time
from ihb_encode.data.types import PROFILES, EncodingProfile
from ihb_ext.video.encode.ffmpeg_validator import ValidationResultDTO
from ihb_ext.video.info.ffprobe import _get_stream_size
from ihb_video.types.stream_models import StreamType

from ..types.video_models import Resolution

logger = logging.getLogger("__name__")

VIDEO_EXTENSIONS = (".avi", ".flv", ".f4v", ".mkv", ".mov", ".mpeg", ".mpg", ".mp4", ".m4v", ".webm", ".wmv")
AV_EXTENSIONS = (".mpeg", ".mpg", ".mp4", ".webm")


RES_REGEX = re.compile(r"(?i)[ \{\-_\[\(\.]*(?:480|720|1080|1920|2160|2k|4k)p?[ \}\-_\]\)\.]*")
REPLACE_REGEX = re.compile(r"[ _\-\!\?\,\;\"\\]")
REMOVE_REGEX = re.compile(r"[\'\']")
AMP_REGEX = re.compile(r"\&")
CLEAN_REGEX = re.compile(r"[\.]{2,}")


VIDEO_DATA_LABELS = ["", "Size", "Duration", "Resolution", "Aspect Ratio", "Bitrate", "EPPS"]


def remove_res_from_file_name(file_name: str, new_res: str = "", new_ext: str = None) -> str:
    file_root, ext = os.path.splitext(file_name)

    file_root = re.sub(RES_REGEX, repl=".", string=file_root)
    file_root = re.sub(REMOVE_REGEX, repl="", string=file_root)
    file_root = re.sub(REPLACE_REGEX, repl=".", string=file_root)
    file_root = re.sub(AMP_REGEX, repl=".and.", string=file_root)
    final_ext = new_ext or ext
    file_root = re.sub(CLEAN_REGEX, repl=".", string=f"{file_root}.{new_res}{final_ext}")

    return file_root.strip(".")


def get_tk_video_file_filter():
    tk_video_string = " ".join(VIDEO_EXTENSIONS)
    return [("Video Files", tk_video_string)]


def calc_bppf(probe_data: dict[str, Any]) -> float:
    format_data = probe_data["format_data"]
    v_data = probe_data["v_streams"][0]

    bitrate = float(format_data["bit_rate"])

    fps = eval(v_data.get("avg_frame_rate", "1"))
    width = int(v_data["width"])
    height = int(v_data["height"])

    bppf = 100 * bitrate / (fps * width * height)
    return bppf


def calc_bitrate(probe_data: dict[str, Any], stream_type: StreamType) -> float:
    format_data = probe_data["format_data"]
    stream_data = probe_data[f"{stream_type.get_stream_key()}_streams"][0]

    if bitrate := float(stream_data.get("bitrate", 0)):
        return bitrate

    stream_size = int(stream_data.get("size", 0))
    if not stream_size:
        stream_size = _get_stream_size(format_data["filename"], stream_type, 0)
    stream_size_bytes = stream_size * 8
    duration = float(stream_data.get("duration", format_data.get("duration")))
    bitrate = stream_size_bytes / duration
    return bitrate


def calc_target_resolution(
    enc_profile: EncodingProfile, source_width: int, source_height: int, force_even: bool = True, force_profile=True, sars_mult: float = 1
) -> tuple[Resolution, EncodingProfile]:

    while True:
        if enc_profile.fixed_dim == 0 or enc_profile.is_source:
            target_width = source_width
            target_height = source_height
        else:
            if source_width >= source_height:  # Landscape
                target_width = sars_mult * enc_profile.fixed_dim * (source_width / source_height)
                target_height = enc_profile.fixed_dim
            else:  # Portrait
                target_height = sars_mult * enc_profile.fixed_dim * (source_height / source_width)
                target_width = enc_profile.fixed_dim

        if enc_profile.is_source:
            final_target_width = int(round(target_width / 2.0) * 2)
            final_target_height = int(round(target_height / 2.0) * 2)

        elif force_even:
            final_target_width = int(round(target_width / 16.0) * 16)
            final_target_height = int(round(target_height / 16.0) * 16)

        if force_profile or (final_target_height <= source_height and final_target_width <= source_width):
            return Resolution(width=final_target_width, height=final_target_height), enc_profile
        else:
            profiles = list(PROFILES.values())
            enc_profile = profiles[profiles.index(enc_profile) + 1]


def eval_recommendation(video_metadata, calc_resolution, is_source):
    if is_source:
        if video_metadata["codec_name"] == "hevc":
            return "Video already in hevc/h.265"
        elif video_metadata["codec_name"] == "h264":
            return "h.264 -> h.265 conversion"

    # Logic for "Not Recommended": Target fixed width is greater than or equal to source width
    elif calc_resolution.width > video_metadata["width"]:
        return "Forced Upscaling"
    elif calc_resolution.width == video_metadata["width"]:
        return "Resolution Matches"


def get_aspect_ratio_str(width: int, height: int):
    calc_gcd = gcd(width, height)
    ar_width = width // calc_gcd
    ar_height = height // calc_gcd

    return f"{ar_width}:{ar_height}"


def _build_chapter_file(file_path: str, probe_datas: list) -> str:
    base_dir = os.path.dirname(file_path)
    target_file = os.path.basename(file_path)
    chapter_file_name = f"chapters_{os.path.splitext(target_file)[0]}.txt"
    chapter_file_path = os.path.join(base_dir, chapter_file_name)

    logger.info(f"Building chapter file {chapter_file_path} for {file_path}")

    cumulative_duration = 0.0
    with open(chapter_file_path, "w", encoding="utf-8") as f:
        for idx, probe_data in enumerate(probe_datas, 1):
            f.write(f"CHAPTER{idx:02d}={format_time(seconds_s=cumulative_duration, is_include_all_fields=True, is_include_ms=True)}")
            f.write("\n")
            f.write(f"CHAPTER{idx:02d}NAME={os.path.splitext(os.path.basename(probe_data["format_data"]["filename"]))[0]}")
            f.write("\n")
            cumulative_duration += float(probe_data["format_data"]["duration"])

    return chapter_file_path


def format_bitrate(bitrate: float) -> str:
    if not bitrate or abs(bitrate) < 1:
        return "N/A"

    sign = "-" if bitrate < 0 else ""
    prefixes = ["", "K", "M", "G", "T"]
    bitrate = abs(bitrate)
    prefix_idx = min(int((log10(bitrate) + 1e-9) // 3), len(prefixes) - 1)

    scaled = bitrate / (1000**prefix_idx)
    return f"{sign}{scaled:.2f}".rstrip("0").rstrip(".") + f" {prefixes[prefix_idx]}bps"
