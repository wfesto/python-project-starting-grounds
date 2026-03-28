import importlib
import logging
import os
import sys
from pathlib import PurePath
from typing import Any

import yaml

from ihb_common.utils.gen_utils import _run_simple_cli_command
from ihb_encode.data import *
from ihb_ext.video.encode import ffmpeg
from ihb_ext.video.info import ffprobe, pymediainfo
from ihb_video.types.stream_models import StreamType
from ihb_video.types.video_data import VideoDataDTO
from ihb_video.types.video_models import (
    FrameTimeData,
    PsnrComparison,
    ValidationResultDTO,
)
from ihb_video.utils.video_utils import AV_EXTENSIONS, VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)

VLC_BINARY = r"f:\Program Files\VideoLAN\VLC\vlc.exe"

try:
    with open(r"f:\dev\python\scripts\ihb_ext\video\video_conf.yaml", "r") as file:
        video_manager_config = yaml.safe_load(file)
        print(f"Configuration loaded: {video_manager_config}")
except Exception as e:
    print(f"Exception loading video manager configuration: {e}")
    sys.exit(1)


def _validate_config():
    supported_ext = str.split(video_manager_config["extensions"], ",")
    for ext in supported_ext:
        ext_config = video_manager_config.get(ext, "")
        if not ext_config:
            raise Exception

        module_s = ext_config.get("module", "")
        if not module_s:
            print()


def play_video_file(file_path: str) -> None:
    logger.verbose(f"Playing {file_path}")
    command = [VLC_BINARY, PurePath(file_path), "--gain", ".25"]
    _run_simple_cli_command(command)


def get_py_video_metadata(file_path: str) -> dict[str, Any]:
    return pymediainfo.get_video_metadata(file_path)


def get_video_metadata(file_path: str) -> dict[str, Any] | None:
    return ffprobe._get_video_metadata(file_path)


def get_video_data(file_path: str) -> VideoDataDTO:
    py_video_data = pymediainfo.get_video_metadata(file_path)
    video_dto = VideoDataDTO.from_pymediainfo_data(py_video_data)
    return video_dto


def get_video_timecode_data(file_path: str) -> list[FrameTimeData] | None:
    return ffprobe._get_timecode_data(file_path)


def concat_videos_simple(input_dir: str, output_dir: str, file_data_list: list) -> tuple[bool, str, ValidationResultDTO]:
    return ffmpeg._build_run_simple_concat_command(input_dir, output_dir, file_data_list)


def generate_encode_command(encode_params: Encoding_Job_DTO, file_metadata: dict[str, Any], config: dict[str, Any]) -> tuple[Encoding_Job_DTO, list]:
    return ffmpeg._generate_encode_command(encode_params, file_metadata, config)


def encode_video(
    encode_params: Encoding_Job_DTO, file_metadata: dict[str, Any], config: dict[str, Any], is_skip_prompt: bool = False
) -> tuple[Encoding_Job_DTO, dict[str, Any]]:
    return ffmpeg._encode_video(encode_params, file_metadata, config, is_skip_prompt)


def rerun_validation(job_dto: Encoding_Job_DTO, config: dict[str, Any]) -> bool:
    return ffmpeg._rerun_encoding_validation(job_dto, config)


def get_psnr_comparison(input_file_1: str, input_file_2: str) -> PsnrComparison:
    return ffmpeg._build_run_psnr_comparison(input_file_1, input_file_2)


def set_chapters(file_path: str, probe_data_list: list, auto_chapter: bool) -> bool:
    if not is_supported_file(file_path):
        logger.info(f"Unsupported file - {file_path}")
        return False

    return _delegate_action(
        file_path=file_path,
        action_name="set_chapters",
        probe_data_list=probe_data_list,
        auto_chapter=auto_chapter,
    )


def disable_default_subtitles(file_path: str, probe_data: dict[str, Any] = None) -> int:
    default_idx, out_probe_data = ffprobe._get_default_subtitles(file_path, probe_data)
    if default_idx >= 0:
        update_default_stream(
            file_path=file_path, probe_data=(probe_data or out_probe_data), selected_index=default_idx, is_default=False, stream_type=StreamType.SUBTITLE
        )
    return default_idx


def update_default_stream(
    file_path: str, probe_data: dict[str, Any] = None, selected_index: int = -1, is_default: bool = False, stream_type: StreamType = StreamType.SUBTITLE
) -> bool:
    if not is_supported_file(file_path):
        logger.info(f"Unsupported file - {file_path}")
        return False

    in_probe_data = probe_data or get_video_metadata(file_path)

    return _delegate_action(
        file_path=file_path,
        action_name="update_default_stream",
        probe_data=in_probe_data,
        selected_index=selected_index,
        is_default=is_default,
        stream_type=stream_type,
    )


def embed_subtitles(file_path: str, sub_path: str, sub_title: str = "English Subtitles", sub_lang: str = "eng", is_default: bool = True):
    return _delegate_action(
        file_path=file_path,
        action_name="embed_subtitles",
        sub_path=sub_path,
        sub_title=sub_title,
        sub_lang=sub_lang,
        is_default=is_default,
    )


def concat_videos_simple(probe_data_list: list, target_dir: str, auto_exec: bool = False) -> str | None:
    return ffmpeg._build_run_simple_concat_command(probe_data_list, target_dir, auto_exec)


def is_video_file(file_path: str) -> bool:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in AV_EXTENSIONS:
        return pymediainfo.is_video_file(file_path)
    else:
        return ext in VIDEO_EXTENSIONS


def is_supported_file(file_path: str) -> bool:
    ext = os.path.splitext(file_path)[1].lower()
    return is_video_file(file_path) and is_supported_extension(ext)


def is_supported_extension(ext: str) -> bool:
    supported_exts = str.split(video_manager_config["extensions"].lower(), ",")
    mod_ext = ext.replace(".", "").lower()
    return mod_ext in supported_exts


def is_supported_action(action: str) -> bool:
    supported_actions = str.split(video_manager_config["actions"].lower(), ",")
    return action.lower() in supported_actions


def _delegate_action(file_path: str, action_name: str, *args, **kwargs) -> bool:
    ext = os.path.splitext(file_path)[1].replace(".", "").lower()

    if not is_supported_extension(ext) or not is_supported_action(action_name):
        print()

    try:
        module_name = f'ihb_ext.video.tools.{video_manager_config[ext]["module"]}'
        function_name = video_manager_config[ext].get("function_map", {}).get(action_name) or action_name

        imp_module = importlib.import_module(module_name)
        imp_function = getattr(imp_module, f"_{function_name}")

        return imp_function(file_path, *args, **kwargs)

    except ImportError as e:
        logger.error(f"Error importing module {module_name}: {e}")
    except AttributeError as e:
        logger.error(f"Error importing method {function_name}: {e}")
    except Exception as e:
        logger.error(f"Error delegating {action_name} on {file_path}")
        logger.error(f"Error: {e}")
    return None


if __name__ == "__main__":
    print()
