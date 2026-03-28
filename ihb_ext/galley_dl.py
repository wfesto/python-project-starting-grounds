import logging
import shutil
import sys

from ihb_common.utils.file_utils import check_disk_space
from ihb_common.utils.gen_utils import (
    VERBOSE_LEVEL_NUM,
    FunctionContainer,
    _run_checked_cli_command,
)

logger = logging.getLogger(__name__)

GALLERY_DL_BINARY = "gallery-dl"

if not shutil.which(GALLERY_DL_BINARY):
    logger.critical(f"No path available for {GALLERY_DL_BINARY}")
    logger.critical("Exiting.")
    sys.exit(1)


def inject_duration(original_str: str, duration: str) -> str:
    print()


def run_gallery_dl(config, url, date_str=None, location=None, filter_string=None) -> bool:
    """Run gallery-dl subprocess with optional date filter and destination."""
    success = False

    # Build gallery-dl command
    cmd = ["gallery-dl", url]

    final_filter = "" if filter_string is None else filter_string

    if date_str:
        try:
            year, month, day = map(int, date_str.split("-")[0].split("."))
            final_filter = f"(date >= datetime({year}, {month}, {day}) or abort()) and " + final_filter
        except ValueError:
            logger.error(f"Invalid date format in line: {date_str}. Skipping filter.")

    if final_filter:
        cmd.extend(["--filter", final_filter])

    if location:
        cmd.extend(["-d", location])

    logger.log(VERBOSE_LEVEL_NUM, cmd)

    space_check = FunctionContainer(check_disk_space, (config["base_dir"], config["minimum_space_init_gb"] * (1024**3)))

    try:
        return_code = _run_checked_cli_command(cmd, check_function=space_check)
        success = return_code == 0

    except Exception as e:
        logger.error(f"Error running gallery-dl for URL {url}: {e}")

    return success
