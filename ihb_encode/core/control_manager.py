import logging
import os

from ..core import db_tools, encoder
from ..data import *

logger = logging.getLogger(__name__)

CLI_HELP = "Operations to control services"
COMMAND_MAP = {}
FLAG_MAP: dict[str, tuple[CliArgument, ...]] = {}

CLI_STOP_COMMAND = CliArgument("s", "stop", action="store_true", help="Immediately enable the stop signal, and the encoding will stop after 1 job.")

STOP_FILE = r".\ihb_encode\db\STOP"


def register_command(keyword: str, *cli_args: CliArgument):
    def decorator(func):
        COMMAND_MAP[keyword] = func
        if cli_args:
            FLAG_MAP[keyword] = cli_args
        return func

    return decorator


@register_command("start-jobs", CLI_STOP_COMMAND)
def _start_jobs(*args, **kwargs):
    is_stop = kwargs[CLI_STOP_COMMAND.name]
    db_tools.reset_stopped_working_jobs()

    while True:
        job_list = db_manager.get_next_job_by_status(Job_Status.PENDING, limit=1)
        if job_list:
            job_dto = job_list[0]
            job_dto.status = Job_Status.WORKING
            db_manager.upsert_job(job_dto)
            job_results, output_metadata = encoder.encode_file(job_dto, None, is_skip_prompt=True)
            if job_results:
                db_manager.upsert_job(job_results)
        else:
            logger.info("No jobs pending.")
            break

        if _check_stop_signal() or is_stop:
            logger.info("STOP signal detected. Halting.")
            _disable_stop_signal()
            break


@register_command("enable-stop")
def _enable_stop_signal(*args, **kwargs):
    if not os.path.exists(STOP_FILE):
        with open(STOP_FILE, "x") as f:
            logger.info("STOP signal enabled")
    else:
        logger.info("STOP signal already enabled")


@register_command("disable-stop")
def _disable_stop_signal(*args, **kwargs):
    if _check_stop_signal():
        os.remove(STOP_FILE)
        logger.info("STOP signal disabled")


@register_command("check-stop")
def _check_stop_signal(*args, **kwargs) -> bool:
    is_stop_enabled = os.path.exists(STOP_FILE)
    logger.verbose(f"STOP signal enabled: {is_stop_enabled}")
    return is_stop_enabled


def get_actions() -> list[str]:
    return list(COMMAND_MAP.keys())


def dispatch(*args, **kwargs):
    action = kwargs.pop("action")
    if method := COMMAND_MAP.get(action):
        try:
            logger.info(f"Executing {action}")
            args_dict = {k: v for k, v in kwargs.items() if v is not None}
            return method(*args, **args_dict)
        except Exception as e:
            logger.error(f"Error executing {action}: {str(e)}", exc_info=True)
    else:
        logger.error(f"Undefined action: {action}")
