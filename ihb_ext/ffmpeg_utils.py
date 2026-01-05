import os
import re
from typing import Any, Dict

from ihb_encode.data import *
from ihb_utils.gen_utils import format_time
from ihb_utils.video_utils import EncodingProfile

FFMPEG_UPDATE_STR_REGEX = re.compile(r"(.*time=)(\d+:\d+:\d+\.\d+)(\s+.*elapsed=)(\d+:\d+:\d+\.\d+)")
FFMPEG_BINARY = "ffmpeg"
INDETERMINATE_VALUES = ["unknown", "unspecified", "default"]
LEGACY_COLOR_CODES = {
    "bt470m": "bt709",
    "smpte170m": "bt709",
}
NEW_EXT = ".mkv"


ENCODE_COMMAND = """
{COMMAND} -nostdin {PTS_VIDEO_FLAGS} -i {INPUT_FILE_PATH} -map 0:v:0 {TAR_FPS} {MAP_AUDIO} {MAP_SUBS}
-c:v libx265 -crf {CRF} -preset {PRESET} {THREAD_LIMIT} -vf {DEINTERLACING}{NOISE_REDUCTION}scale={TARGET_RES},setsar=1:1,setdar={DAR_FRACTION},format=yuv420p10le 
-profile:v main10 -x265-params "aq-mode=3:sao=0:strong-intra-smoothing=0:rc-lookahead=100{PARAMS_X265}" {COLOR_FLAGS}
{AUDIO_COMMANDS} {PTS_AUDIO_FLAGS} {SUBTITLE_COPY} -map_metadata -1
-y {OUTPUT_FILE_PATH}"""

ENCODE_DEFAULTS = {
    "COMMAND": FFMPEG_BINARY,
    "PTS_VIDEO_FLAGS": "",
    "INPUT_FILE_PATH": "",
    "TAR_FPS": "",
    "MAP_AUDIO": "",
    "MAP_SUBS": "",
    "CRF": "",
    "PRESET": "",
    "THREAD_LIMIT": "",
    "DEINTERLACING": "",
    "NOISE_REDUCTION": "",
    "TARGET_RES": "",
    "DAR_FRACTION": "",
    "PARAMS_X265": "",
    "COLOR_FLAGS": "",
    "AUDIO_COMMANDS": "",
    "PTS_AUDIO_FLAGS": "",
    "SUBTITLE_COPY": "",
    "OUTPUT_FILE_PATH": "",
}


def populate_encode_params(probe_data: Dict[str, Any], profile: EncodingProfile, adv_options: Advanced_Options_DTO) -> Dict[str, str]:
    encode_params = ENCODE_DEFAULTS.copy()

    format_data = probe_data["format_data"]
    v_stream = probe_data["v_streams"][0]
    a_stream = probe_data["a_streams"][0] if probe_data["a_count"] > 0 else None
    has_subs = probe_data["s_count"] > 0

    encode_params["INPUT_FILE_PATH"] = f'"{format_data["filename"]}"'
    if a_stream:
        encode_params["MAP_AUDIO"] = "-map 0:a"

    if has_subs:
        encode_params["MAP_SUBS"] = "-map 0:s"

    encode_params["CRF"] = profile.crf
    encode_params["PRESET"] = profile.encoder_preset

    # -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv
    RANGE_MAP = {"limited": "tv", "full": "pc"}

    color_parts = []

    val = v_stream.get("color_primaries")
    if val and val.lower() not in INDETERMINATE_VALUES:
        color_parts.extend(["-color_primaries", LEGACY_COLOR_CODES.get(val, val)])

    val = v_stream.get("color_transfer")
    if val and val.lower() not in INDETERMINATE_VALUES:
        color_parts.extend(["-color_trc", LEGACY_COLOR_CODES.get(val, val)])

    val = v_stream.get("color_space")
    if val and val.lower() not in INDETERMINATE_VALUES:
        color_parts.extend(["-colorspace", LEGACY_COLOR_CODES.get(val, val)])

    val = v_stream.get("color_range")
    if val and val.lower() not in INDETERMINATE_VALUES:
        color_parts.extend(["-color_range", RANGE_MAP.get(val, val)])

    if color_parts:
        encode_params["COLOR_FLAGS"] = " ".join(color_parts)

    if a_stream:
        encode_params["AUDIO_COMMANDS"] = "-c:a:0 copy" if a_stream.get("codec_name").lower() in ("aac", "ac3") else "-c:a:0 aac -ac 2 -b:a 128k"

    if has_subs:
        encode_params["SUBTITLE_COPY"] = "-c:s copy"

    if adv_options:
        encode_params["THREAD_LIMIT"] = "-threads 1" if adv_options.use_limit_threads else ""
        encode_params["DEINTERLACING"] = "bwdif=mode=send_frame:parity=auto:deint=all," if adv_options.use_deinterlacing else ""
        encode_params["NOISE_REDUCTION"] = "vaguedenoiser=threshold=3:method=soft:nsteps=6," if adv_options.use_noise_reduction else ""

    return encode_params


def calc_seconds(input_str: str) -> float:
    time_str = input_str.split(":")
    input_hrs = float(time_str[0])
    input_min = float(time_str[1])
    input_sec = float(time_str[2])

    tot_input_sec = ((input_hrs * 60 + input_min) * 60) + input_sec
    return tot_input_sec


def insert_time_progression(input_str: str, duration: float) -> str:
    input_match = FFMPEG_UPDATE_STR_REGEX.search(input_str)
    duration_progress = calc_seconds(input_match.group(2))
    perc = duration_progress / duration

    curr_time = calc_seconds(input_match.group(4))

    proj_time_str = "N/A"
    if curr_time and perc:
        proj_time = curr_time / perc
        proj_time_str = format_time(proj_time, True, True)

        rem_time = proj_time - curr_time
        rem_time_str = format_time(rem_time, True, True)

        reconstructed_string = f"{input_match.group(1)}{input_match.group(2)}{input_match.group(3)}{input_match.group(4)} proj={proj_time_str} rem={rem_time_str} ({(100 * perc):.2f}%)"
        return reconstructed_string

    return input_str


def get_target_framerate(probe_data: Dict[str, Any]) -> float:
    v_stream = probe_data["v_streams"][0]
    fps = eval(v_stream.get("avg_frame_rate", 0))

    if not fps:
        fps = eval(v_stream.get("r_frame_rate", 0))

    if not fps:
        frames = float(v_stream.get("nb_frames", 0))
        duration = float(v_stream.get("duration", 0))
        if frames and duration:
            fps = frames / duration

    return fps
