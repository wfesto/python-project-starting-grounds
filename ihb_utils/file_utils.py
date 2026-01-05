import logging
import os
import shutil
import time
from pathlib import Path
from tkinter import Tk, filedialog
from typing import Any, Dict, List

import xxhash
import yaml
from humanfriendly import format_size
from send2trash import send2trash
from win32gui import (
    EnumWindows,
    GetForegroundWindow,
    GetWindowText,
    IsWindowVisible,
    PostMessage,
    SetForegroundWindow,
)

from ihb_utils.gen_utils import _run_simple_cli_command

logger = logging.getLogger("__name__")
EXPLORER_EXE = "explorer"
HASHER = xxhash.xxh64()


def recycle_file(file_path: str, do_check_dir=False) -> bool:
    file_path = Path(file_path).absolute()

    try:
        send2trash(file_path)
        logger.verbose(f"{file_path} recycled successfully.")
        return True
    except Exception as e:
        logger.verbose(f"Error recycling {file_path} - {e}")
        return False


def get_xxh64_hash(file_path, is_use_partial: bool = False, block_size_mb: int = 5) -> str | None:
    logger.debug(f"Calculating xx64 hash for {file_path}")
    hasher = HASHER.copy()
    block_size = block_size_mb * 1024**2
    file_size = os.stat(file_path).st_size

    try:
        with open(file_path, "rb") as f:
            if is_use_partial and (2 * block_size) <= file_size:
                hasher.update(f.read(block_size))
                f.seek(file_size - block_size, 0)
                hasher.update(f.read(block_size))

            else:
                while chunk := f.read(4096):
                    hasher.update(chunk)

            hash = hasher.hexdigest()
            logger.debug(f"Hash calculated: {hash}")
            return hash
    except Exception as e:
        logger.error(f"Unable to calculate xx64 hash: {e}")

    return None


def open_explorer_highlight_file(file_path: str) -> bool:
    if os.path.exists(file_path) and os.path.isfile(file_path):
        upd_path = Path(file_path)
        command = [EXPLORER_EXE, "/select,", str(upd_path)]
        _run_simple_cli_command(command=command)
        return True

    return False


def close_exp_window(file_name):
    folder_name = str(Path(file_name).parent)[0:95]

    def enum_handler(hwnd, ctx):
        if IsWindowVisible and folder_name == GetWindowText(hwnd):
            PostMessage(hwnd, 0x0010, 0, 0)
            time.sleep(0.01)
            return False

        return True

    EnumWindows(enum_handler, None)


def choose_file(window_title: str = "Select file", file_types: List = None, file_type: str = None, file_description: str = None) -> str | None:
    """Uses a Tkinter file dialog to choose a single file"""
    file_path = None
    tk_filetypes = file_types if file_types else [file_description, f"*.{file_type}"]

    if not tk_filetypes:
        logger.error(f"No file information provided.")

    try:
        console_handle = GetForegroundWindow()

        root = Tk()
        root.withdraw()

        file_path = filedialog.askopenfilename(parent=root, title=window_title, filetypes=tk_filetypes)

        if console_handle:
            root.update()
            time.sleep(0.01)
            SetForegroundWindow(console_handle)

    except Exception as e:
        print(f"Error opening file dialog: {e}")
        return None

    return os.path.abspath(file_path) if file_path else None


def choose_directory() -> str | None:
    base_dir = None
    try:
        console_handle = GetForegroundWindow()

        root = Tk()
        root.withdraw()
        base_dir = filedialog.askdirectory(parent=root, title="Select a Directory to Process")

        if console_handle:
            root.update()
            time.sleep(0.01)
            SetForegroundWindow(console_handle)
    except Exception as e:
        logger.warning(f"Could not set console window foreground. Error: {e}")

    return os.path.abspath(base_dir) if base_dir else None


def load_config(file_name: str = "config.yaml", file_path: str = None) -> Dict[str, Any] | None:
    """Loads and returns the configuration from the yaml file."""
    final_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_name)
    if file_path:
        final_path = os.path.join(file_path, file_name)
    logger.debug(f"Loading config file: {final_path}")
    try:
        with open(final_path, "r") as f:
            config = yaml.safe_load(f)
            logger.debug(f"Config loaded: {config}")
            return config
    except FileNotFoundError:
        logger.critical(f"Configuration file not found at {file_path} / {file_name}.")
    except Exception as e:
        logger.critical(f"Error loading {final_path}: {e}")


def check_disk_space(path: str, threshold: float) -> bool:
    """Checks if the disk hosting 'path' has space above the threshold."""
    try:
        total, used, free = shutil.disk_usage(path)
        if free < threshold:
            logger.critical(f"Insufficient disk space on drive containing {path}.")
            logger.critical(f"Required: {format_size(threshold)}. Available: {format_size(free)}.")
            return False
        return True
    except FileNotFoundError:
        logger.error(f"Cannot check disk usage: Path not found {path}")
        return False
    except Exception as e:
        logger.error(f"Error checking disk space: {e}")
        return False


def sanitise_filename(name: str) -> str:
    """Removes extension and sanitizes a string for use in a filename."""
    name, _ = os.path.splitext(os.path.basename(name))
    name = name.strip()
    name = "".join(c if (c.isalnum() or c in (".", "-")) else "_" for c in name)
    return name[:60]  # Limit filename length
