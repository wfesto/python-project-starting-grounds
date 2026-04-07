import logging
import os
import shlex
import shutil
import sys
import time
from dataclasses import replace
from subprocess import CompletedProcess
from typing import Any, NamedTuple

import ihb_ext.video.encode.ffmpeg_utils as ffmpeg_utils
from ihb_common.utils.file_utils import check_disk_space
from ihb_common.utils.gen_utils import (
    CLI_Output_Mod,
    _run_checked_cli_command,
    _run_interruptable_cli_command,
    _run_simple_cli_command,
)
from ihb_encode.data import *
from ihb_video.types.video_models import PSNR_COMP_REGEX, PsnrComparison
from ihb_video.utils.video_utils import (
    calc_target_resolution,
    remove_res_from_file_name,
)

from ..info.ffprobe import _get_video_metadata
from .ffmpeg_validator import VALIDATION_TYPE, ValidationResultDTO, _run_validation

logger = logging.getLogger(__name__)

FFMPEG_BINARY = "ffmpeg"
INDETERMINATE_VALUES = ["unknown", "unspecified", "default"]


if not shutil.which(FFMPEG_BINARY):
    logger.critical(f"No path available for {FFMPEG_BINARY}")
    logger.critical("Exiting.")
    sys.exit(1)


class CommandBuildResult(NamedTuple):
    """Structured result for the FFmpeg command build process."""

    command_list: list[str]
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


def _build_run_simple_concat_command(input_dir: str, output_dir: str, file_data_list: list, auto_exec: bool = False) -> tuple[bool, str, ValidationResultDTO]:
    input_dir_base = os.path.basename(input_dir)
    temp_file_path = os.path.join(output_dir, f"concat_list_{input_dir_base}.txt")
    output_file_name = f"{input_dir_base}{os.path.splitext(file_data_list[0]["file_name"])[1]}"
    output_path = os.path.join(output_dir, output_file_name)

    output_size = sum(int(data["format_data"]["size"]) for data in file_data_list)
    if not check_disk_space(output_dir, output_size):
        logger.error(f"Insufficient disk space for {output_path}")
        return None

    try:
        with open(temp_file_path, "w") as f:
            for probe_data in file_data_list:
                absolute_path = probe_data["format_data"]["filename"].replace("\\", "/")
                f.write(f"file '{absolute_path}'\n")
    except IOError as e:
        logger.error(f"Failed to create temporary concat file at {temp_file_path}. Error: {e}")
        return None

    ffmpeg_command = [FFMPEG_BINARY, "-f", "concat", "-safe", "0", "-i", temp_file_path, "-c", "copy", output_path]

    logger.info("Concatenation Order (Alphabetical, using absolute paths):")
    for probe_data in file_data_list:
        logger.info(f"  - {probe_data['format_data']['filename']}")

    logger.info(f"\nFFmpeg Command :\n{' '.join(ffmpeg_command)}\n")

    if not auto_exec:
        user_input = input("Continue with FFmpeg execution (y/n)? ").strip().lower()
        if user_input != "y":
            logger.warning("User skipped concatenation. Cleaning up temp file.")
            os.remove(temp_file_path)
            return None

    is_success = _run_checked_cli_command(ffmpeg_command, None, None)
    os.remove(temp_file_path)
    validation = _run_validation(None, _get_video_metadata(output_path), VALIDATION_TYPE.ANALYSIS)
    return is_success, output_path, validation


def _get_output_file_name(encode_params: Encoding_Job_DTO, config: dict[str, Any]) -> str:
    base_name = os.path.basename(encode_params.input)
    output_file_name = remove_res_from_file_name(base_name, encode_params.profile.name.lower(), config["encode"]["extension"])
    output_file_path = os.path.join(encode_params.output, output_file_name)
    return output_file_path


def _generate_encode_command(encode_params: Encoding_Job_DTO, file_metadata: dict[str, Any], config: dict[str, Any]) -> tuple[Encoding_Job_DTO, list]:
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

    command_params = ffmpeg_utils.populate_encode_params(file_metadata, encode_params.profile, encode_params.adv_params, config=config["encode"])

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
    encode_params: Encoding_Job_DTO, file_metadata: dict[str, Any], config: dict[str, Any], is_skip_prompt: bool = False
) -> tuple[Encoding_Job_DTO, dict[str, Any]]:
    file_metadata = file_metadata or _get_video_metadata(encode_params.input)
    result_params, command = _generate_encode_command(encode_params, file_metadata, config)

    output_file_path = result_params.output

    logger.info(" --- FFmpeg Command Details --- ")
    logger.info(f" -> Input: {os.path.basename(encode_params.input)}")
    logger.info(f" -> Output: {output_file_path}")
    logger.info(f" -> Profile: {encode_params.profile.name.upper()} (CRF {encode_params.profile.crf}, Preset '{encode_params.profile.encoder_preset}')")

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
        result_params.notes = {}
        result_params.notes["command"] = " ".join(command)
        result_params.notes["encode_time"] = f"{elapsed_time}"

        _validate_encoding_job(result_params, file_metadata, new_probe_data)

        return result_params, new_probe_data

    else:
        logger.info("Execution cancelled. Run the command manually when ready.")
        return None, None


def _rerun_encoding_validation(job_dto: Encoding_Job_DTO, config: dict[str, Any]) -> bool:
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


def _validate_encoding_job(job_dto: Encoding_Job_DTO, input_metadata: dict[str, Any], output_metadata: dict[str, Any]):
    input_metadata = input_metadata or _get_video_metadata(job_dto.input)
    output_metadata = output_metadata or _get_video_metadata(job_dto.output)

    logger.info("Running validation.")
    validation_results = _run_validation(input_metadata, output_metadata)
    validaton_result_dict = [asdict(result) for result in validation_results]
    job_dto.notes["validation"] = validaton_result_dict


def _run_stream_integrity_analysis(input_file: str) -> CompletedProcess:
    command = ["ffmpeg", "-v", "error", "-i", input_file, "-f", "null", "-", "-xerror"]
    result = _run_simple_cli_command(command)
    return result


def print_command(command: dict[str, Any]):
    quoted_command = command.copy()
    input_idx = 3
    output_idx = -1
    #    input_idx = 2 + (2 if is_fix_pts else 0)
    quoted_command[input_idx] = f'"{command[input_idx]}"'
    #   quoted_command[input_idx] = f'"{command[input_idx]}"'
    quoted_command[output_idx] = f'"{command[output_idx]}"'

    logger.info("--------------------------------")
    logger.info(" ".join(quoted_command))
    logger.info("--------------------------------")
