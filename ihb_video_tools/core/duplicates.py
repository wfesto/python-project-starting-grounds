import logging
import os
from enum import StrEnum, auto
from typing import Any, Dict, List

from humanfriendly import format_size
from send2trash import send2trash

from ihb_ext.video_manager import (
    get_psnr_comparison,
    get_video_metadata,
    play_video_file,
)
from ihb_utils.file_utils import open_explorer_highlight_file
from ihb_utils.gen_utils import close_exp_window, format_time, generate_aligned_table
from ihb_utils.video_utils import calc_bppf, get_aspect_ratio_str
from ihb_video_tools.conf.config import get_config
from ihb_video_tools.data.db_manager import find_duplicates_by_hash, read_all_records
from ihb_video_tools.data.dto import File_DTO

logger = logging.getLogger(__name__)


class Duplicate_Mode(StrEnum):
    HASH = auto()
    DURATION = auto()


_PROMPT_COMMANDS = {"v": play_video_file, "e": open_explorer_highlight_file}
_METHOD_MAP = {}


def register_command(command):
    def decorator(func):
        _METHOD_MAP[command] = func
        return func

    return decorator


def handle_duplicates(mode: Duplicate_Mode):
    _METHOD_MAP[mode]()


@register_command(Duplicate_Mode.HASH)
def process_duplicates_by_hash():
    dupe_dict = find_duplicates_by_hash()
    print(len(dupe_dict.keys()))


@register_command(Duplicate_Mode.DURATION)
def process_duplicates_by_duration():
    dto_list = read_all_records(True)
    radius = get_config()["general"]["radius"]

    cluster = []
    dto_count = len(dto_list)

    for idx, dto in enumerate(dto_list):
        cluster.clear()
        cluster.append(dto)

        seed_duration = dto.duration
        min_duration = seed_duration - radius

        dur_idx = idx + 1
        while dur_idx < dto_count and dto_list[dur_idx].duration >= min_duration:
            cluster.append(dto_list[dur_idx])
            dur_idx += 1

        if len(cluster) > 1:
            _process_cluster(cluster)
            return


def _process_cluster(dto_list: List[File_DTO]):
    while True and len(dto_list) > 1:
        print(_get_prompt_string(dto_list))
        input_val = input("Enter choice:")

        if input_val == "q":
            logger.info("[q] - Quitting.")
            close_all_windows(dto_list)
            return

        elif input_val == "s":
            logger.info("[s] - Proceeding to next match")
            close_all_windows(dto_list)
            break

        elif len(input_val) == 2 and str.isdigit(input_val[1]) and 1 <= int(input_val[1]) <= len(dto_list):
            list_idx = int(input_val[1]) - 1
            chosen_file = dto_list[list_idx].path

            if input_val[0] in _PROMPT_COMMANDS.keys():
                command = _PROMPT_COMMANDS[input_val[0]]
                command(chosen_file)
            elif input_val[0] == "d":
                delete_file(chosen_file)
            else:
                logger.warning("Invalid choice.")
        else:
            logger.warning("Invalid choice.")
    return


def delete_file(file_path: str):
    pass


def close_all_windows(dto_list: List[File_DTO]):
    for path in [os.path.normpath(dto.path.replace("/", os.path.sep).replace("\\", os.path.sep)) for dto in dto_list]:
        close_exp_window(path)


def _get_prompt_string(dto_list: List[File_DTO]) -> str:
    prompt_parts = []

    duration_list = ["duration"]
    duration_list.extend([format_time(dto.duration) for dto in dto_list])
    size_list = ["size"]
    size_list.extend([format_size(int(dto.size)) for dto in dto_list])
    fps_list = ["fps"]
    fps_list.extend([f"{eval(dto.metadata.get("frame_rate", "0")):.2f}" for dto in dto_list])
    epps_list = ["epps"]
    epps_list.extend(["" for dto in dto_list])
    #    delta_epps = 100 * (max_epps - eff_epps) / max_epps
    res_list = ["resolution"]
    res_list.extend([dto.metadata["resolution"] for dto in dto_list])
    path_list = ["file"]
    path_list.extend([dto.path for dto in dto_list])

    rows = generate_aligned_table(duration_list, size_list, fps_list, epps_list, res_list, path_list)
    for idx, row in enumerate(rows):
        prompt_parts.append((f"{idx if idx > 0 else " "}|" + row))

    prompt_parts.append(f"[v]x || Play Video file x in [V]LC")
    prompt_parts.append(f"[e]x || Show Video file in [E]xplorer")
    prompt_parts.append(f"[d]x || [D]elete Video file")
    prompt_parts.append(f"i[g]nore")
    prompt_parts.append(f"[s]kip")
    prompt_parts.append(f"[q]uit")

    return "\n".join(prompt_parts)


def test():
    pass


if __name__ == "__main__":
    test()
