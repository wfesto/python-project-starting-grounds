import argparse
import logging
import time

from ihb_common.utils.gen_utils import configure_logging, format_time
from ihb_components.cli.cli_utils import WorkflowManager

from .core import control_manager, db_tools, job_manager
from .data import verify_db

logger = logging.getLogger(__name__)


MANAGER_MAP: dict[str, WorkflowManager] = {
    "db": db_tools.DbTools(),
    "control": control_manager.ControlManager(),
    "jobs": job_manager.JobManager(),
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

    start_time = time.perf_counter()
    result = MANAGER_MAP[args.manager].dispatch(**vars(args))
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time

    logger.info(f"Executed {args.manager}.{args.action}: {result} in {format_time(elapsed_time)}")


if __name__ == "__main__":
    main()
