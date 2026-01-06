import logging
import os
from pathlib import PurePath
from typing import Any, Dict

from ihb_ext import video_manager
from ihb_utils import video_utils
from ihb_utils.color_codes import TerminalColorCodes
from ihb_utils.file_utils import open_explorer_highlight_file, recycle_file
from ihb_utils.gen_utils import generate_aligned_table
from ihb_utils.video_models import VideoMetrics

from ..data.types import *

PROMPT_COMMANDS = {"v": video_manager.play_video_file, "e": open_explorer_highlight_file, "d": recycle_file}

logger = logging.getLogger(__name__)


def _get_prompt_video_data(file_metadata) -> str:
    data = VideoMetrics.from_ffprobe_data(file_metadata, None, False)

    prompt_data = ["--- Video data ---"]
    prompt_data.extend(generate_aligned_table(VideoMetrics.get_data_labels(), data.to_pretty_list()))
    return "\n".join(prompt_data)


def _get_prompt_string(v_stream: Dict[str, Any]) -> str:
    prompt_string = []

    width = v_stream["width"]
    height = v_stream["height"]

    prompt_string.append("\n--- Choose Encoding Profile ---")
    for i, profile in enumerate(PROFILES.values(), 1):
        calc_resolution, _ = video_utils.calc_target_resolution(profile, width, height, force_profile=True)
        scheme_resolution_str = f"{calc_resolution.width}w x {calc_resolution.height}h"
        perc_reduction = 100 * (1 - (calc_resolution.width * calc_resolution.height) / (width * height))
        recommendation_tag = video_utils.eval_recommendation(v_stream, calc_resolution, profile.is_source)

        prompt_string.append(f"[{i}] {profile.name}\t{scheme_resolution_str}\t{perc_reduction:.2f}\t{recommendation_tag}")
    return "\n".join(prompt_string)


def _get_prompt_adv_opts(adv_opts: Advanced_Options_DTO):
    adv_opts_prompt = []

    adv_opts_prompt.append("--- Toggle Advanced Options ---")
    idx = 1

    adv_opts_prompt.append(f"[a{idx}] Enable Thread Limit: {adv_opts.use_limit_threads}")
    idx += 1

    adv_opts_prompt.append(f"[a{idx}] Enable Noise Reduction: {adv_opts.use_noise_reduction}")
    idx += 1

    return "\n".join(adv_opts_prompt)


def prompt_encoding_profile(input_metadata: Dict[str, Any], adv_opts: Advanced_Options_DTO) -> Profile:
    chosen_profile = None
    video_data_str = _get_prompt_video_data(input_metadata)
    prompt_str = _get_prompt_string(input_metadata["v_streams"][0])

    max_choice = len(PROFILES)
    input_text_str = f"Enter the profile number to select (1 - {max_choice}), the advanced option number to toggle (a1-2), or select another option: "

    while True:
        print()
        print(video_data_str)
        print(prompt_str)
        print()
        print(_get_prompt_adv_opts(adv_opts))
        print()
        print("[v] Play file in [V]lc")
        print("[d] [D]elete file and skip encoding")
        print("[q] [Q]uit\n")
        user_input = input(input_text_str).strip().lower()

        if user_input == "q":
            logger.info(f"Quitting immediately.")
            return None

        elif user_input == "v":
            video_manager.play_video_file(input_metadata["format_data"]["filename"])

        elif user_input == "d":
            recycle_file(input_metadata["format_data"]["filename"])
            return None

        elif user_input[0] == "a":
            if user_input[1] == "1":
                adv_opts.use_limit_threads = not adv_opts.use_limit_threads
            elif user_input[1] == "2":
                adv_opts.use_noise_reduction = not adv_opts.use_noise_reduction

        elif user_input.isdigit():
            input_idx = int(user_input) - 1
            if 0 <= input_idx < max_choice:
                chosen_profile = list(PROFILES.values())[input_idx]
                break

        else:
            logger.warning(f"Invalid choice '{user_input}'.")

    return chosen_profile


def prompt_review_job(
    job_dto: Encoding_Job_DTO,
    input_metadata: Dict[str, Any] = None,
    output_metadata: Dict[str, Any] = None,
    old_metrics: VideoMetrics = None,
    new_metrics: VideoMetrics = None,
) -> bool:

    input_file = job_dto.input
    output_file = job_dto.output

    q_exit = False

    if not os.path.exists(input_file):
        logger.error(f"Job {job_dto.job_id} missing input file {input_file}")
        q_exit = True
    if not os.path.exists(output_file):
        logger.error(f"Job {job_dto.job_id} missing input file {output_file}")
        q_exit = True
    if q_exit:
        return False

    input_metadata = input_metadata or video_manager.get_video_metadata(input_file)
    output_metadata = output_metadata or video_manager.get_video_metadata(output_file)
    os.system("")

    logger.info("*" * 25)
    logger.info(f"Job ID {job_dto.job_id}")

    logger.info(f"[1] OLD FILE: {input_file}")
    logger.info(f"[2] NEW FILE: {output_file}")

    row_labels = VideoMetrics.get_data_labels()
    old_metrics = old_metrics or VideoMetrics.from_ffprobe_data(input_metadata, job_dto.profile, True)
    new_metrics = new_metrics or VideoMetrics.from_ffprobe_data(output_metadata, job_dto.profile, True)
    delta_data = old_metrics.compare_to(new_metrics)

    old_data_pr = old_metrics.to_pretty_list()
    new_data_pr = new_metrics.to_pretty_list()

    row_labels.pop(0)
    old_data_pr.pop(0)
    new_data_pr.pop(0)
    delta_data.pop(0)

    table_data = generate_aligned_table(row_labels, old_data_pr, new_data_pr, delta_data)
    for row in table_data:
        logger.info(f" -> {row}")

    if validation_list := job_dto.notes.get("validation", None):
        validation_results = [Validation_Results_DTO(**validation) for validation in validation_list]
        print("-" * 20)
        for result in validation_results:
            color_code = TerminalColorCodes.BRIGHT_GREEN if result.result else TerminalColorCodes.BRIGHT_RED
            line = f"{color_code}{str(result)}{TerminalColorCodes.RESET}"
            print(line)
        print("-" * 20)

    print(f"[v]x || Play Video file x in [V]LC")
    print(f"[e]x || Show Video file in [E]xplorer")
    print(f"[d]x || [D]elete Video file")
    print(f"[a]pprove job")
    print(f"[x] Delete both files and mark job deleted")
    print(f"[r]eset job")
    print(f"[q]uit")

    try:
        while True:
            user_choice = list(input("Enter selection and option: ").lower())
            logger.verbose(f"Choice: {user_choice}")

            while user_choice:
                is_update = False
                command = user_choice.pop(0)
                if command == "q" and not user_choice:
                    print("Qutting immediately")
                    return False

                elif command == "r":
                    is_update = True
                    job_dto.status = Job_Status.PENDING
                    job_dto.size_out = None
                    job_dto.output = os.path.dirname(output_file)
                    if os.path.exists(output_file):
                        os.remove(output_file)

                elif command == "a":
                    is_update = True
                    job_dto.status = Job_Status.COMPLETE

                elif command == "x":
                    is_update = True
                    recycle_file(input_file)
                    recycle_file(output_file)
                    job_dto.status = Job_Status.DELETED

                elif command in PROMPT_COMMANDS.keys():
                    file_choice = None
                    if user_choice and user_choice[0].isnumeric() and int(user_choice[0]) > 0 and int(user_choice[0]) <= 2:
                        file_idx = int(user_choice.pop(0)) - 1
                        file_choice = input_file if file_idx == 0 else output_file
                    elif command == "v":
                        file_choice = output_file
                    elif command == "d":
                        file_choice = input_file if os.path.exists(input_file) else output_file
                    else:
                        print("Invalid choice")

                    if file_choice:
                        try:
                            PROMPT_COMMANDS[command](PurePath(file_choice))
                            logger.verbose(f"{PROMPT_COMMANDS[command]} executed on {file_choice}")
                        except Exception as e:
                            logger.error(f"{e}", stack_info=True)
                else:
                    print("Invalid choice.")

            if is_update:
                return True

    finally:
        # close_exp_window(input_file)
        # close_exp_window(output_file)
        pass


def test():
    pass


if __name__ == "__main__":
    test()
