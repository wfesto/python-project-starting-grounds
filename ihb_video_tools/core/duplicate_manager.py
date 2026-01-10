import logging
import os
from collections.abc import Callable
from enum import StrEnum, auto

from humanfriendly import format_size

from ihb_ext import video_manager
from ihb_utils.cli_utils import BaseWorkflowManager, CliArgument
from ihb_utils.file_utils import get_xxh64_hash, recycle_file
from ihb_utils.gen_utils import format_time, generate_aligned_table

from ..conf.config import get_config
from ..data.db_manager import find_duplicates_by_hash, read_all_records
from ..data.dto import File_DTO
from . import user_prompts

logger = logging.getLogger(__name__)


CLI_INPUT_LIST = CliArgument("i", "input_list", type=str, nargs="*", help="List of input directories")
CLI_DETECTION_MODE = CliArgument("m", "check_mode", type=str, nargs="*", help="List of detection modes to use")


class Duplicate_Mode(StrEnum):
    HASH = auto()
    DURATION = auto()


class DuplicateManager(BaseWorkflowManager):
    CLI_HELP = "Duplicate Operations"
    COMMAND_MAP: dict[str, Callable] = {}
    FLAG_MAP: dict[str, tuple[CliArgument, ...]] = {}


@DuplicateManager.register_command("check-dirs", CLI_INPUT_LIST, CLI_DETECTION_MODE)
def _process_directories(*args, **kwargs) -> None:
    dir_list: list[str] = kwargs[CLI_INPUT_LIST.name]
    mode_list: list[Duplicate_Mode] = [Duplicate_Mode(str.lower(mode)) for mode in kwargs.get(CLI_DETECTION_MODE.name, Duplicate_Mode.HASH.value)]

    is_hash = Duplicate_Mode.HASH in mode_list
    is_dur = Duplicate_Mode.DURATION in mode_list

    hash_map: dict[str, list[str]] = {}
    dur_map: dict[float, list[str]] = {}

    for dir in dir_list:
        for dir_name, _, file_list in os.walk(dir):
            logger.info(f"Processing {dir_name}, {len(file_list)} files")
            for file_name in [file for file in file_list if video_manager.is_video_file(file)]:
                file_path = os.path.join(dir_name, file_name)
                if is_hash:
                    file_hash = get_xxh64_hash(file_path, True)
                    hash_map.setdefault(file_hash, []).append(file_path)
                if is_dur:
                    duration = video_manager.get_video_metadata(file_path)["format_data"]["duration"]
                    dur_map.setdefault(duration, []).append(file_path)

    if is_hash:
        for key, value in hash_map.items():
            if len(value) > 1:
                if is_quit := not user_prompts.prompt_duplicate_action(value):
                    return

    if is_dur:
        pass


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


def _process_cluster(dto_list: list[File_DTO]):
    while True and len(dto_list) > 1:
        print(_get_prompt_string(dto_list))
        input_val = input("Enter choice:")

        if input_val == "q":
            logger.info("[q] - Quitting.")
            return

        else:
            logger.warning("Invalid choice.")
    return


def _get_prompt_string(dto_list: list[File_DTO]) -> str:
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
