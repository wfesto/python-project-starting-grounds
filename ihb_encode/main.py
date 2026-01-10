import argparse
import logging
from typing import Any, Protocol

from ihb_utils.cli_utils import Workflow_Manager
from ihb_utils.gen_utils import configure_logging

from .core import control_manager, db_tools, job_manager
from .data import verify_db

logger = logging.getLogger(__name__)


MANAGER_MAP: dict[str, Workflow_Manager] = {
    "db": db_tools,
    "control": control_manager,
    "jobs": job_manager,
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
    verify_db()

    MANAGER_MAP[args.manager].dispatch(**vars(args))

    return


if __name__ == "__main__":
    main()
