import argparse
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from humanfriendly import format_size
from send2trash import send2trash
from win32gui import EnumWindows, GetWindowText, IsWindowVisible, PostMessage

from ihb_common.utils.dir_utils import choose_directory
from ihb_common.utils.file_utils import open_explorer_highlight_file
from ihb_common.utils.gen_utils import configure_logging, format_time
from ihb_video.manager.video_manager import (
    get_psnr_comparison,
    get_video_metadata,
    play_video_file,
)
from ihb_video.utils.video_utils import (
    VIDEO_EXTENSIONS,
    PSNR_Comparison,
    calc_bppf,
    get_aspect_ratio_str,
)

logger = logging.getLogger(__name__)

PROMPT_COMMANDS = {"v": play_video_file, "e": open_explorer_highlight_file, "d": send2trash}


def get_video_output_string(video_data: Dict[str, Any], max_epps: float) -> str:
    format_data = video_data["format_data"]
    v_data = video_data["v_streams"][0]

    width = v_data["width"]
    height = v_data["height"]

    frame_rate = eval(v_data.get("avg_frame_rate", "0"))

    eff_epps = calc_bppf(video_data)
    delta_epps = 100 * (max_epps - eff_epps) / max_epps

    data_str = (
        f"{format_size(int(format_data["size"]))} "
        f" || {frame_rate:.2f}"
        f" || {eff_epps:.4f} || -{delta_epps:.2f}"
        f" || {width}x{height} ({get_aspect_ratio_str(width, height)}) "
        f" || {format_data['filename']}"
    )

    return data_str


def get_output_file_path(output_target: str) -> str | None:
    default_file_name = f"{__name__}_report.txt"
    if os.path.exists(output_target) and os.path.isdir(output_target):
        output_file_path = os.path.join(output_target, default_file_name)
        return output_file_path

    if os.path.exists(os.path.dirname(output_target)):
        return output_target

    output_file_path = os.join(choose_directory(), default_file_name)
    return output_file_path


def close_exp_window(file_name):
    folder_name = str(Path(file_name).parent)[0:95]

    def enum_handler(hwnd, ctx):
        if IsWindowVisible and folder_name == GetWindowText(hwnd):
            PostMessage(hwnd, 0x0010, 0, 0)
            time.sleep(0.01)
            return False

        return True

    EnumWindows(enum_handler, None)


def _get_prompt_string(duration: int, file_list: List, psnr_comp: PSNR_Comparison) -> str:
    prompt_parts = []

    prompt_parts.append(f"{format_time(duration)} || {psnr_comp.get_display_string() if psnr_comp else ''}")
    eff_epps_list = [calc_bppf(file) for file in file_list]
    max_eff_epps = max(eff_epps_list)

    for idx, file in enumerate(file_list, 1):
        prompt_parts.append(f" -> [{idx}] {get_video_output_string(file_list[idx-1], max_eff_epps)}")
    prompt_parts.append(f"[v]x || Play Video file x in [V]LC")
    prompt_parts.append(f"[e]x || Show Video file in [E]xplorer")
    prompt_parts.append(f"[d]x || [D]elete Video file")
    prompt_parts.append(f"[s]kip")
    prompt_parts.append(f"[q]uit")

    return "\n".join(prompt_parts)


def prompt_deletions(data_list: List, is_skip_psnr: bool = False) -> None:
    logger.info("Starting deletion prompt section.")
    for duration, file_list in data_list:
        file1 = file_list[0]["format_data"]["filename"]
        file2 = file_list[1]["format_data"]["filename"]
        psnr_comp = None
        if (
            file_list[0]["v_streams"][0]["width"] == file_list[1]["v_streams"][0]["width"]
            and file_list[0]["v_streams"][0]["height"] == file_list[1]["v_streams"][0]["height"]
            and not is_skip_psnr
        ):
            logger.info(f"Generating psnr for\n -> {file1}\n -> {file2}")
            psnr_comp = get_psnr_comparison(file1, file2)

        while True and len(file_list) > 1:
            prompt_string = _get_prompt_string(duration, file_list, psnr_comp)
            print(prompt_string)
            input_val = input("Enter choice:")

            if input_val == "q":
                logger.info("[q] - Quitting.")
                for file in file_list:
                    close_exp_window(file["format_data"]["filename"])
                return

            elif input_val == "s":
                logger.info("[s] - Proceeding to next match")
                for file in file_list:
                    close_exp_window(file["format_data"]["filename"])
                break

            elif len(input_val) == 2 and input_val[0] in PROMPT_COMMANDS.keys() and str.isdigit(input_val[1]) and 1 <= int(input_val[1]) <= len(file_list):
                command = PROMPT_COMMANDS[input_val[0]]
                list_idx = int(input_val[1]) - 1
                chosen_file = os.path.normpath(file_list[list_idx]["format_data"]["filename"])
                command(chosen_file)
                if input_val[0] == "d":
                    file_list.pop(list_idx)

            else:
                logger.warning("Invalid choice.")


def generate_report(data_list: List, output_str: str) -> tuple[bool, str]:
    output_file = get_output_file_path(output_str)
    if not output_file:
        logger.error(f"No valid output file provided.")
        return False, None

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            for duration, files in data_list:
                f.write(f"{format_time(duration)}\n")
                for file in files:
                    f.write(f" -> {get_video_output_string(file)}\n")
    except Exception as e:
        logger.error(f"Error writing {output_file}: {e}")
        return False, output_file

    return True, output_file


def process_directories(input_dirs: List) -> Dict[float, List]:
    file_length_dict = {}

    for dir in input_dirs:
        for dirpath, _, file_list in os.walk(dir):
            logger.info(f"Processing {len(file_list)} potential files in {dirpath}")
            for file in file_list:
                if os.path.splitext(file)[1] in VIDEO_EXTENSIONS:
                    file_path = os.path.join(dirpath, file)
                    video_data = get_video_metadata(file_path)
                    if video_data:
                        rounded_duration = round(float(video_data.get("format_data", {}).get("duration", 0)), 1)
                        if rounded_duration > 0:
                            file_length_dict.setdefault(rounded_duration, []).append(video_data)
                        else:
                            logger.error(f"Duration 0 reported for {file_path}")
                    else:
                        logger.error(f"Error getting data for {file_path}")

    logger.info(f"{len(file_length_dict.keys())} unique durations found")
    return file_length_dict


def main():
    """Main execution function with argparse and input type checking."""
    parser = argparse.ArgumentParser(description="Automatically selects and sets the best subtitle/CC stream as 'default' for supported files.")
    parser.add_argument("-i", "--input", nargs="*", type=str, help="The input path(s) to compare")
    parser.add_argument("-v", "--interactive", action="store_true", help="Use interactive mode and delete files.")
    parser.add_argument("-s", "--skip_psnr", action="store_true", help="Skip PSNR generation")
    parser.add_argument("-o", "--output", type=str, help="Output dir/file for report.")
    parser.add_argument("-r", "--reverse", action="store_true", help="Reverse ordering of list")
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")

    args = parser.parse_args()
    configure_logging(level=args.level)
    logger.debug(args)

    input_dirs = args.input or choose_directory()
    if not input_dirs:
        logger.error("No input directories provided. Exiting.")
        return 1

    good_dirs = []
    for dir in input_dirs:
        if os.path.exists(dir) and os.path.isdir(dir):
            good_dirs.append(dir)
        else:
            logger.warning(f"{dir} does not exist or is not a directory. Ignoring.")

    if not good_dirs:  # or len(good_dirs) < 2:
        logger.error("All input is invalid or only 1 directory provided. Exiting.")
        return 1

    start_time = time.perf_counter()
    file_length_dict = process_directories(good_dirs)
    filtered_dict = {duration: file_list for duration, file_list in file_length_dict.items() if len(file_list) >= 2}
    data_list = list(filtered_dict.items())
    list.sort(data_list, key=lambda x: x[0], reverse=args.reverse)

    if args.interactive:
        prompt_deletions(data_list, args.skip_psnr)
    else:
        is_report_gen, report_path = generate_report(data_list, args.output)
        logger.info(f"Report {report_path} generated {'' if is_report_gen else 'un'}successfully.")
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    logger.info(f"{__name__} finished in {format_time(elapsed_time)}")


if __name__ == "__main__":
    main()
