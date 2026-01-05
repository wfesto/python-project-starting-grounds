import argparse
import logging
import os

from ihb_utils.gen_utils import configure_logging

from .conf.config import get_config
from .core import db_tools, job_manager
from .data import get_profile, verify_db
from .data.types import Job_Status

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--level", type=str, help="Override the logging level")

    sub_parsers = parser.add_subparsers(dest="command")

    enc_subparser = sub_parsers.add_parser("encode-file")
    enc_subparser.add_argument("-i", "--input", type=str, help="The input file/directory")
    enc_subparser.add_argument("-o", "--output", type=str, help="The output directory")
    enc_subparser.add_argument("-e", "--encoding_profile", type=str, help="Encoding profile to use")
    enc_subparser.add_argument("-s", "--skip_prompt", action="store_true", help="skip displaying the ffmpeg command and prompting to encode.")
    enc_subparser.add_argument("-q", "--queue_job", action="store_true", help="Queue job instead of immediately encoding it.")
    enc_subparser.add_argument("-t", "--simulate", action="store_true", help="Generate ffmpeg commmand but do not enqueue any job (Testing)")

    dir_subparser = sub_parsers.add_parser("process-dir")
    dir_subparser.add_argument("-i", "--input", type=str, help="The input directory")
    dir_subparser.add_argument("-o", "--output", type=str, help="The output directory")
    dir_subparser.add_argument("-e", "--encoding_profile", type=str, help="Encoding profile to use")

    jobs_subparser = sub_parsers.add_parser("start-jobs")
    jobs_subparser.add_argument("-s", "--stop", action="store_true", help="Immediately create a stop file. The encoding will stop after 1 job.")

    stop_subparser = sub_parsers.add_parser("stop")

    results_subparser = sub_parsers.add_parser("review-jobs")

    validation_subparser = sub_parsers.add_parser("validate-jobs")
    validation_subparser.add_argument("-j", "--job_list", nargs="*", type=int, help="Job ID list to modify")

    reset_subparser = sub_parsers.add_parser("reset-error")
    reset_subparser.add_argument("-j", "--job_id", type=int, help="Job ID to reset")

    db_subparser = sub_parsers.add_parser("db-tools")
    db_subparser.add_argument("-a", "--action", type=str, choices=sorted(db_tools.get_actions()), help="Operations directly on the database")
    db_subparser.add_argument("-j", "--job_id", type=int, help="Job ID to modify")
    db_subparser.add_argument("-z", "--size_max", type=int, help="Maximum output size to bulk approve")

    args = parser.parse_args()
    configure_logging(level=args.level)
    config = get_config()
    verify_db()

    if args.command == "encode-file":
        job_manager.manual_run_file(vars(args))

    elif args.command == "process-dir":
        profile = get_profile(args.encoding_profile)
        job_count = job_manager.process_dir(args.input, args.output, profile)
        logger.info(f"{job_count} jobs added")

    elif args.command == "reset-error":
        job_dto = job_manager.reset_job(args.job_id)
        logger.info(f"{args.job_id} reset {"UN" if job_dto.status == Job_Status.ERROR else ""}SUCCESSFUL")
        results_subparser

    elif args.command == "review-jobs":
        job_manager.review_results()

    elif args.command == "start-jobs":
        job_manager.start_jobs(args.stop)

    elif args.command == "validate-jobs":
        job_manager.validate_job(args.job_list)

    elif args.command == "db-tools":
        db_tools.execute_action(args.action, **vars(args))

    elif args.command == "stop":
        if not os.path.exists(r".\ihb_encode\db\STOP"):
            with open(r".\ihb_encode\db\STOP", "x") as f:
                logger.info("STOP file created")
        else:
            logger.info("STOP file already exists.")


if __name__ == "__main__":
    main()
