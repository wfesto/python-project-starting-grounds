import logging
import os
from pathlib import PurePath
from typing import List

from humanfriendly import format_size
from send2trash import send2trash

from ihb_utils.gen_utils import generate_aligned_table

from ..data import db_manager
from ..data.types import *

logger = logging.getLogger(__name__)


COMMAND_MAP = {}


def get_actions() -> List[str]:
    return list(COMMAND_MAP.keys())


def register_command(keyword):
    def decorator(func):
        COMMAND_MAP[keyword] = func
        return func

    return decorator


def execute_action(*args, **kwargs):
    action = kwargs["action"]
    if method := COMMAND_MAP.get(action):
        try:
            logger.info(f"Executing {action}")
            args_dict = {k: v for k, v in kwargs.items() if v is not None}
            return method(*args, **args_dict)
        except Exception as e:
            logger.error(f"Error executing {action}: {str(e)}", exc_info=True)
    else:
        logger.error(f"Undefined action: {action}")


@register_command("current-jobs")
def _get_jobs(*args, **kwargs):
    limit = int(kwargs.get("size_max", 1))
    if job_list := db_manager.get_next_job_by_status(Job_Status.WORKING, limit):
        print(str(job_list[0]))
        print(job_list[0].to_pretty_string())


@register_command("reset-job")
def _get_reset_job(*args, **kwargs):
    job_id = kwargs["job_id"]
    logger.info(f"Resettng {job_id} to status {Job_Status.PENDING.name}")
    is_succcess = db_manager.force_job_status(job_id, Job_Status.PENDING)
    logger.info(f"Update {job_id} is {"NOT" if is_succcess else ""} successful")


@register_command("list-errors")
def _get_error_Jobs(*args, **kwargs):
    limit = int(kwargs.get("size_max", 5))
    job_list = db_manager.get_next_job_by_status(Job_Status.ERROR, limit)
    print("\n".join(str(dto) for dto in job_list))


@register_command("list-jobs")
def _get_jobs(*args, **kwargs):
    limit = int(kwargs.get("size_max", 5))
    job_list = db_manager.get_next_job_by_status(Job_Status.PENDING, limit)
    job_list_list = [dto.to_pretty_string().split("\t") for dto in job_list]
    job_table = generate_aligned_table(*job_list_list, rotate=True)
    print("\n".join(job_table))


@register_command("bulk-approve")
def _bulk_approve_jobs(*args, **kwargs):
    size_max = int(kwargs.get("size_max", 10))
    job_list: list[Encoding_Job_DTO] = db_manager.get_jobs_by_status_and_size(Job_Status.REVIEW, size_max * (1024**2))
    complete_count = 0
    error_count = 0

    logger.info(f"{len(job_list)} jobs returned.")
    logger.verbose(f"{[job.job_id for job in job_list]}")
    for job in job_list:
        try:
            job.status = Job_Status.COMPLETE
            if not job.notes:
                job.notes = {}
            job.notes.setdefault("flow", []).append("Bulk-approved")
            if os.path.exists(job.input):
                send2trash(PurePath(job.input))
                logger.verbose(f"Deleted {job.input}")
            else:
                logger.verbose(f"Input file {job.input} missing, skipping deletion.")
        except Exception as e:
            logger.error(f"Error approving job {job.job_id}: {e}", stack_info=True)
            job.status = Job_Status.ERROR

        db_manager.upsert_job(job)
        if job.status == Job_Status.COMPLETE:
            complete_count += 1
        else:
            error_count += 1

    logger.info(f"Bulk approval results: {complete_count} completed, {error_count} errors")


def reset_stopped_working_jobs():
    upd_count = db_manager.bulk_update_job_status(Job_Status.WORKING, Job_Status.PENDING)
    return upd_count


@register_command("force-approve")
def _force_approve_job(*args, **kwargs):
    if job_id := int(kwargs.get("job_id", 0)):
        db_manager.force_job_status(job_id, Job_Status.COMPLETE)


@register_command("stats")
def _print_db_stats(*args, **kwargs):
    db_stats = db_manager.select_job_counts()
    status_list = ["STATUS"]
    count_list = ["COUNT"]
    size_in_list = ["SIZE_IN"]
    size_out_list = ["SIZE_OUT"]

    total_list = ["TOTAL", 0, 0, 0]

    for row in db_stats:
        status_list.append(Job_Status(int(row["status"])).name)

        count_list.append(row["count"])
        total_list[1] += int(row["count"])

        size_in_list.append(format_size(row["size_in"]))
        total_list[2] += int(row["size_in"])

        size_out = row["size_out"]
        size_out_list.append(format_size(0 if not size_out else size_out))
        total_list[3] += int(size_out if size_out else 0)

    status_list.append("TOTAL")
    count_list.append(total_list[1])
    size_in_list.append(format_size(total_list[2]))
    size_out_list.append(format_size(total_list[3]))

    print("\n".join(generate_aligned_table(status_list, count_list, size_in_list, size_out_list)))


def test():
    pass


if __name__ == "__main__":
    test()
