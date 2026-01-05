import argparse
import logging
import os
import time

import ihb_utils.db_utils as db_utils
import ihb_video_tools.core.duplicates as duplicate_handler
import ihb_video_tools.core.processor as directory_processor
from ihb_utils.gen_utils import LOGGING_LEVELS, configure_logging, format_time
from ihb_video_tools.conf.config import get_config
from ihb_video_tools.core.duplicates import Duplicate_Mode
from ihb_video_tools.data.db_manager import execute_action, get_actions

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--level", type=str, default="INFO", choices=LOGGING_LEVELS, help="Override the logging level")

    subparsers = parser.add_subparsers(dest="command")

    db_parser = subparsers.add_parser("db-maint")
    db_parser.add_argument("-a", "--db_action", type=str, choices=sorted(get_actions()), help=f"Available DB Maintenance Options: {sorted(get_actions())}")

    proc_parser = subparsers.add_parser("process")
    proc_parser.add_argument("-i", "--input", type=str, help="The input path")

    dupe_parser = subparsers.add_parser("find-dupes")
    dupe_parser.add_argument(
        "-m",
        "--mode",
        type=str,
        choices=sorted(list(Duplicate_Mode)),
        help=f"Find duplicates by chosen method: {sorted([mode.value for mode in Duplicate_Mode])}",
    )

    args = parser.parse_args()
    configure_logging(level=args.level)

    logger.debug("Starting up")
    logger.debug(f"Config loaded: {get_config()}")

    start_time = time.perf_counter()
    if args.command == "db-maint":
        logger.info(db_utils.execute_action(args.db_action, get_config()["db_conn"]))

    elif args.command == "process":
        if not os.path.isdir(args.input):
            logger.critical(f"{args.input} is not a valid directory. Exiting.")
            return -1

        proc_count = directory_processor.process(args.input)
        if proc_count == -1:
            logger.info("Process directory failed with error.")

    elif args.command == "find-dupes":
        duplicate_handler.handle_duplicates(Duplicate_Mode[args.mode.upper()])

    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    logger.info(f"Time elapsed: {format_time(elapsed_time)}")


if __name__ == "__main__":
    main()
