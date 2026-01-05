import logging
import os
import shutil
import sys
from typing import List

from ihb_utils.gen_utils import _run_simple_cli_command

logger = logging.getLogger(__name__)
EXT_7Z = "7z"


if not shutil.which(EXT_7Z):
    logger.critical(f"No path available for {EXT_7Z}")
    logger.critical("Exiting.")
    sys.exit(1)


def archive_files_to_7z(file_path_list: List, archive_name: str, password: str = None) -> bool:
    archive_path = os.path.join(os.path.dirname(file_path_list[0]), archive_name + "." + EXT_7Z)

    command = [
        EXT_7Z,
        "a",
        "-t7z",
    ]

    if password:
        command.append(f"-p{password}")
        command.append("-mhe")

    command.append(archive_path)
    command.extend(file_path_list)

    result = _run_simple_cli_command(command)
    if not result or result.returncode != 0:
        logger.error(f"Error compressing {file_path_list}, or {EXT_7Z} call failed.")
        return False

    return True
