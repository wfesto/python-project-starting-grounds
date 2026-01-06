import logging
import os
import re
import shlex
import shutil
import sys
import time
from dataclasses import replace
from typing import Any, Dict, List, NamedTuple, Tuple

import ihb_ext.ffmpeg_utils as ffmpeg_utils
from ihb_encode.data import *
from ihb_utils.file_utils import check_disk_space
from ihb_utils.gen_utils import (
    CLI_Output_Mod,
    _run_checked_cli_command,
    _run_interruptable_cli_command,
)
from ihb_utils.video_models import PSNR_COMP_REGEX, PsnrComparison
from ihb_utils.video_utils import calc_target_resolution, remove_res_from_file_name

from .ffmpeg_validator import _run_validation
from .ffprobe import _get_video_metadata

logger = logging.getLogger(__name__)

FFMPEG_BINARY = "ffmpeg"
INDETERMINATE_VALUES = ["unknown", "unspecified", "default"]


if not shutil.which(FFMPEG_BINARY):
    logger.critical(f"No path available for {FFMPEG_BINARY}")
    logger.critical("Exiting.")
    sys.exit(1)


class CommandBuildResult(NamedTuple):
    """Structured result for the FFmpeg command build process."""

    command_list: List[str]
    output_path: str
    target_width: int
    target_height: int


def _build_run_psnr_comparison(input_file_1: str, input_file_2: str) -> PsnrComparison | None:
    logger.debug("Generating PSNR command for")
    logger.debug(f" -> {input_file_1}")
    logger.debug(f" -> {input_file_2}")

    command = [
        FFMPEG_BINARY,
        "-i",
        input_file_1,
        "-i",
        input_file_2,
        "-filter_complex",
        "psnr",
        "-f",
        "null",
        "NUL",
    ]

    logger.debug(command)
    result = _run_interruptable_cli_command(command)
    if result and result.returncode == 0 and result.stderr:
        for line in result.stderr.splitlines():
            if PSNR_COMP_REGEX.search(line):
                return PsnrComparison(line)

    return None


def _build_run_simple_concat_command(input_files_data: List, output_dir: str, auto_exec: bool = False) -> str | None:
    output_dir_name = os.path.basename(output_dir)
    temp_file_path = os.path.join(output_dir, f"concat_list_{output_dir_name}.txt")
    output_file_name = f"{output_dir_name}{os.path.splitext(input_files_data[0]["file_name"])[1]}"
    output_path = os.path.join(output_dir, output_file_name)

    output_size = sum(size for size in input_files_data["format"]["size"])
    if not check_disk_space(output_path, output_size):
        logger.error(f"Insufficient disk space for {output_path}")
        return None

    try:
        with open(temp_file_path, "w") as f:
            for probe_data in input_files_data:
                absolute_path = probe_data["format"]["filename"].replace("\\", "/")
                f.write(f"file '{absolute_path}'\n")
    except IOError as e:
        logger.error(f"Failed to create temporary concat file at {temp_file_path}. Error: {e}")
        return None

    ffmpeg_command = [FFMPEG_BINARY, "-f", "concat", "-safe", "0", "-i", temp_file_path, "-c", "copy", output_path]

    logger.info("Concatenation Order (Alphabetical, using absolute paths):")
    for probe_data in input_files_data:
        logger.info(f"  - {probe_data['format']['filename']}")

    logger.info(f"\nFFmpeg Command :\n{' '.join(ffmpeg_command)}\n")

    if not auto_exec:
        user_input = input("Continue with FFmpeg execution (y/n)? ").strip().lower()
        if user_input != "y":
            logger.warning("User skipped concatenation. Cleaning up temp file.")
            os.remove(temp_file_path)
            return None

    is_success = _run_checked_cli_command(ffmpeg_command, None, None)
    os.remove(temp_file_path)
    return output_path if is_success else None


def _get_output_file_name(encode_params: Encoding_Job_DTO, config: Dict[str, Any]) -> str:
    base_name = os.path.basename(encode_params.input)
    output_file_name = remove_res_from_file_name(base_name, encode_params.profile.name.lower(), config["general"]["extension"])
    output_file_path = os.path.join(encode_params.output, output_file_name)
    return output_file_path


def _generate_encode_command(encode_params: Encoding_Job_DTO, file_metadata: Dict[str, Any], config: Dict[str, Any]) -> Tuple[Encoding_Job_DTO, List]:
    file_metadata = file_metadata or _get_video_metadata(encode_params.input)

    v_stream = file_metadata["v_streams"][0]
    a_stream = file_metadata["a_streams"][0] if file_metadata["a_count"] > 0 else {}
    has_subs = file_metadata["s_count"] > 0

    source_width = v_stream.get("width", 0)
    source_height = v_stream.get("height", 0)

    sar_multiplier = 1.0
    sar_str = v_stream.get("sample_aspect_ratio", "1:1")
    if sar_str and ":" in sar_str:
        num, den = map(int, sar_str.split(":"))
        if num and den:
            sar_multiplier = num / den

    if not source_width or not source_height:
        logger.error(f"Video dimensions are missing: {source_width} x {source_height}")
        return False, None

    calc_resolution, encode_params.profile = calc_target_resolution(
        encode_params.profile, source_width, source_height, force_profile=False, sars_mult=sar_multiplier
    )
    target_resolution = f"{calc_resolution.width}:{calc_resolution.height}"

    result_params = replace(encode_params)

    output_file_path = _get_output_file_name(encode_params, config)
    result_params.output = output_file_path

    is_good_pts = True
    tar_fps = 0
    if not is_good_pts:
        tar_fps = ffmpeg_utils.get_target_framerate(file_metadata)
    is_fix_pts = (not is_good_pts) and tar_fps > 0

    command_params = ffmpeg_utils.populate_encode_params(file_metadata, encode_params.profile, encode_params.adv_params)

    command_params["TARGET_RES"] = f"{target_resolution}"
    command_params["DAR_FRACTION"] = f"{calc_resolution.width}/{calc_resolution.height}"
    command_params["OUTPUT_FILE_PATH"] = f'"{output_file_path}"'

    final_265_params = []
    if encode_params.profile.params_x265:
        final_265_params.extend(encode_params.profile.params_x265)
    if not encode_params.profile.is_source:
        final_265_params.append("sar=1")

    if final_265_params:
        params_x265_str = ":".join(final_265_params)
        command_params["PARAMS_X265"] = f":{params_x265_str}"

    command_str = ffmpeg_utils.ENCODE_COMMAND.format(**(command_params))
    command = shlex.split(command_str)

    return result_params, command


def _encode_video(
    encode_params: Encoding_Job_DTO, file_metadata: Dict[str, Any], config: Dict[str, Any], is_skip_prompt: bool = False
) -> Tuple[Encoding_Job_DTO, Dict[str, Any]]:
    file_metadata = file_metadata or _get_video_metadata(encode_params.input)
    result_params, command = _generate_encode_command(encode_params, file_metadata, config)

    output_file_path = result_params.output

    logger.info(" --- FFmpeg Command Details --- ")
    logger.info(f" -> Input: {os.path.basename(encode_params.input)}")
    logger.info(f" -> Output: {output_file_path}")
    logger.info(f" -> Profile: {encode_params.profile.name.upper()} (CRF {encode_params.profile.crf}, Preset '{encode_params.profile.encoder_preset}')")

    # print_command(command, is_fix_pts)
    print_command(command)

    prompt = "Do you want to EXECUTE this FFmpeg command now? (y/n): "

    if is_skip_prompt or (input(prompt).strip().lower() == "y"):
        update_str = CLI_Output_Mod()
        update_str.update_str_prefix = "frame="
        update_str.str_mod_func = ffmpeg_utils.insert_time_progression
        update_str.str_mod_re = ffmpeg_utils.FFMPEG_UPDATE_STR_REGEX
        update_str.str_mod_args = tuple([float(file_metadata["format_data"]["duration"])])

        logger.info("--- Executing FFmpeg (This may take a while...) ---")

        start_time = time.perf_counter()
        result = _run_checked_cli_command(command, update_config=update_str)
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        new_probe_data = _get_video_metadata(output_file_path)

        result_params.size_out = new_probe_data["format_data"]["size"]
        result_params.notes["command"] = " ".join(command)
        result_params.notes["encode_time"] = f"{elapsed_time}"

        _validate_encoding_job(result_params, file_metadata, new_probe_data)

        return result_params, new_probe_data

    else:
        logger.info("Execution cancelled. Run the command manually when ready.")
        return None, None


def _rerun_encoding_validation(job_dto: Encoding_Job_DTO, config: Dict[str, Any]) -> bool:
    try:
        input_metadata = _get_video_metadata(job_dto.input)
        if os.path.isdir(job_dto.output):
            output_file_path = _get_output_file_name(job_dto, config)
            job_dto.output = output_file_path
        if os.path.exists(job_dto.output):
            output_metadata = _get_video_metadata(job_dto.output)
            job_dto.size_out = output_metadata["format_data"]["size"]

            _validate_encoding_job(job_dto, input_metadata, output_metadata)
            return True
        else:
            logger.warning(f"Output file {output_file_path} does not exist.")
            return False

    except Exception as e:
        logger.error(f"Unable to rerun validation: {str(e)}", exc_info=True)
        return False


def _validate_encoding_job(job_dto: Encoding_Job_DTO, input_metadata: Dict[str, Any], output_metadata: Dict[str, Any]):
    input_metadata = input_metadata or _get_video_metadata(job_dto.input)
    output_metadata = output_metadata or _get_video_metadata(job_dto.output)

    logger.info("Running validation.")
    validation_results = _run_validation(input_metadata, output_metadata)
    validaton_result_dict = [asdict(result) for result in validation_results]
    job_dto.notes["validation"] = validaton_result_dict


def print_command(command: Dict[str, Any]):
    quoted_command = command.copy()
    input_idx = 2
    output_idx = -1
    #    input_idx = 2 + (2 if is_fix_pts else 0)
    quoted_command[input_idx] = f'"{command[input_idx]}"'
    #   quoted_command[input_idx] = f'"{command[input_idx]}"'
    quoted_command[output_idx] = f'"{command[output_idx]}"'

    logger.info("--------------------------------")
    logger.info(" ".join(quoted_command))
    logger.info("--------------------------------")
