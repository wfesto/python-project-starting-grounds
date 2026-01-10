import argparse
import logging
import time

import ihb_video_tools.core.processor as directory_processor
from ihb_utils.cli_utils import WorkflowManager
from ihb_utils.gen_utils import configure_logging, format_time

from .core import duplicate_manager

logger = logging.getLogger(__name__)


MANAGER_MAP: dict[str, WorkflowManager] = {
    "duplicates": duplicate_manager.DuplicateManager(),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")
    manager_parsers = parser.add_subparsers(dest="manager")

    for key, workfow_manager in MANAGER_MAP.items():
        manager_parser = manager_parsers.add_parser(key, help=workfow_manager.CLI_HELP)
        manager_action_parser = manager_parser.add_subparsers(dest="action")

        for action in workfow_manager.get_actions():
            action_parser = manager_action_parser.add_parser(action)
            if cli_args := workfow_manager.FLAG_MAP.get(action, None):
                for cli_arg in cli_args:
                    action_parser.add_argument(*cli_arg.get_args(), **cli_arg.get_kwargs())

    args = parser.parse_args()
    configure_logging(level=args.level)

    start_time = time.perf_counter()
    if result := MANAGER_MAP[args.manager].dispatch(**vars(args)):
        logger.info(result)

    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    logger.info(f"Command {args.manager}.{args.action} executed in {format_time(elapsed_time)}")


if __name__ == "__main__":
    main()
