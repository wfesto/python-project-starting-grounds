import logging
import logging.config
import math
import os
import queue
import re
import subprocess
import threading
import time
import traceback
from typing import Any

logger = logging.getLogger(__name__)

LOGGING_LEVELS = ["DEBUG", "VERBOSE", "INFO", "WARNING", "ERROR", "CRITICAL"]
VERBOSE_LEVEL_NUM = 15
logging.addLevelName(VERBOSE_LEVEL_NUM, "VERBOSE")

IDLE_PRIORITY_CLASS = 0x00000040
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000


def verbose(self, message, *args, **kws):
    if self.isEnabledFor(VERBOSE_LEVEL_NUM):
        self._log(VERBOSE_LEVEL_NUM, message, args, **kws)


logging.Logger.verbose = verbose


class FunctionContainer:
    func: function
    args: tuple

    def __init__(self, func: function, args: tuple):
        self.func = func
        self.args = args


class CLI_Output_Mod:
    update_str_prefix: str = None
    str_mod_re: re.Pattern = None
    str_mod_func: function = None
    str_mod_args: tuple = None


def _input_listener(interrupt_queue: queue.Queue):
    try:
        input()
        interrupt_queue.put("INTERRUPT")
    except EOFError:
        pass


def configure_logging(file_path: str = None, file_name: str = "logging.ini", level: str = None) -> None:
    file_path = file_path or os.path.abspath(os.path.dirname(__file__))
    logging.config.fileConfig(os.path.join(file_path, file_name), disable_existing_loggers=False)
    if level and level.upper() in LOGGING_LEVELS:
        logging.root.setLevel(level.upper())


def format_time(seconds_s: str | float | int, is_include_all_fields: bool = False, is_include_ms: bool = False, sec_digits: int = 3) -> str:
    """Formats seconds into H:MM:SS string."""
    seconds = float(seconds_s)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms, _ = math.modf(seconds) if is_include_ms else (0, 0)
    int_ms = int((10**sec_digits) * ms)

    if is_include_all_fields:
        return f"{h:02d}:{m:02d}:{s:02d}.{str(int_ms).ljust(sec_digits, "0")}"

    if h > 0:
        return f"{h}h {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    else:
        return f"{s+1}s"


def _run_interruptable_cli_command(command: list, polling_gap: int = 2) -> subprocess.CompletedProcess | None:
    logger.debug(f"Executing {command}")

    interrupt_queue = queue.Queue(maxsize=1)
    input_thread = threading.Thread(target=_input_listener, args=(interrupt_queue,), daemon=True)
    input_thread.start()
    process = None

    try:
        start_time = time.perf_counter()
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
        while process.poll() is None:
            try:
                interrupt_queue.get_nowait()
                logger.info("Interrupt signal received from user")
                process.terminate()
                process.wait(timeout=2)
                break
            except queue.Empty:
                time.sleep(polling_gap)

        stdout, stderr = process.communicate()
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        logger.debug(f"{command[0]} finished, code {process.returncode} in {format_time(elapsed_time)}")

        if stdout:
            logger.debug(f"Output: {stdout}")
        if stderr:
            logger.debug(f"Error: {stderr}")

        return subprocess.CompletedProcess(command, process.returncode, stdout.strip(), stderr.strip())

    except subprocess.CalledProcessError as e:
        logger.debug(f"Output: {e.stdout.strip()}")
        logger.debug(f"Error: {e.stderr.strip()}")
    except Exception as e:
        logger.error(f"General error encountered: {e}")

    return None


def _run_simple_cli_command(command: list) -> subprocess.CompletedProcess | None:
    logger.debug(f"Executing {command}")
    try:
        start_time = time.perf_counter()
        result = subprocess.run(command, check=True, capture_output=True, encoding="utf-8")
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        logger.debug(f"{command[0]} finished, code {result.returncode} in {format_time(elapsed_time)}")

        if result.stdout:
            logger.debug(f"Output: {result.stdout}")
        if result.stderr:
            logger.debug(f"Error: {result.stderr}")

        return result

    except subprocess.CalledProcessError as e:
        if e.stdout:
            logger.debug(f"Output: {e.stdout}")
        if e.stderr:
            logger.debug(f"Error: {e.stderr}")
    except Exception as e:
        logger.error(f"General error encountered: {e}")

    return None


def _run_checked_cli_command(command: list, check_function: FunctionContainer = None, update_config: CLI_Output_Mod = None) -> int:
    logger.debug(f"Executing {command}")
    try:
        start_time = time.perf_counter()
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line-buffered
            universal_newlines=True,
            creationflags=BELOW_NORMAL_PRIORITY_CLASS,
        )

        last_line = None
        for output_line in process.stdout:
            mod_line = output_line
            if update_config and update_config.str_mod_re and update_config.str_mod_re.search(output_line):
                mod_line = update_config.str_mod_func(output_line, *update_config.str_mod_args)

            last_line = mod_line
            if (
                update_config
                and update_config.update_str_prefix
                and (last_line or "").startswith(update_config.update_str_prefix)
                and (mod_line or "").startswith(update_config.update_str_prefix)
            ):
                print(mod_line.rstrip(), end="\r", flush=True)
            else:
                logger.info(mod_line.rstrip())

            if check_function:
                kill = not check_function.func(*(check_function.args or ()))
                if kill:
                    print()
                    logger.critical(f"{str(check_function.func)} failed! Killing {command}")
                    process.kill()
                    return 1
        print()

        # Wait for the process to complete
        return_code = process.wait()
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        logger.info(f"{command[0]} finished, code {return_code} in {format_time(elapsed_time)}")

        return return_code == 0

    except subprocess.CalledProcessError as e:
        logger.error(f"Error processing {command}: {e}")
    except Exception as e:
        logger.error(f"Error processing {command}: {e}")
        logger.error(traceback.format_exc())
        process.kill()
    return 1


def generate_aligned_table(*columns: list[list[Any]], delimiter: str = "|", spacing: int = 1, rotate=False) -> list[str]:
    if len(columns) == 0 or len(columns[0]) == 0:
        return []

    if rotate:
        columns = [list(row[::-1]) for row in zip(*columns)]

    max_length: list[int] = [max([len(str(col_val)) for col_val in column]) for column in columns]
    splitter = f"{' ' * spacing}{delimiter}{' ' * spacing}"

    lines = []

    for row in zip(*columns):
        line_parts = []
        for col, width in zip(row, max_length):
            line_parts.append(f"{str(col):<{width}}")
        line = splitter.join(line_parts)
        lines.append(line)
    return lines
