import logging
import os
import threading
from pathlib import Path, PurePath
from typing import Any

from ihb_ext import video_manager
from ihb_utils.cli_utils import BaseWorkflowManager, CliArgument
from ihb_utils.gen_utils import generate_aligned_table
from ihb_utils.video_models import VideoMetrics

from ..conf.config import get_config
from ..core import encoder, user_prompts
from ..data import *

logger = logging.getLogger(__name__)

CLI_INPUT_PATH = CliArgument("i", "input", type=str, help="The input path")
CLI_OUTPUT_PATH = CliArgument("o", "output", type=str, help="The output directory")
CLI_ENCODING_PROFILE = CliArgument("e", "encoding_profile", type=str, help="Encoding profile to use")
CLI_JOB_ID = CliArgument("j", "job_id", type=int, help="Job ID to modify")
CLI_JOB_LIST = CliArgument("j", "job_list", nargs="*", type=int, help="Job ID list to modify")
CLI_SKIP_PROMPT = CliArgument("s", "skip_prompt", action="store_true", help="skip displaying the ffmpeg command and prompting to encode.")
CLI_QUEUE_JOB = CliArgument("q", "queue_job", action="store_true", help="Queue job instead of immediately encoding it.")
CLI_SIMULATE = CliArgument("t", "simulate", action="store_true", help="Generate ffmpeg commmand but do not enqueue any job (Testing)")


class JobManager(BaseWorkflowManager):
    CLI_HELP = "Job Operations"
    COMMAND_MAP: dict[str, callable] = {}
    FLAG_MAP: dict[str, tuple[CliArgument, ...]] = {}


@JobManager.register_command("validate-job")
def _validate_job(*args, **kwargs) -> list[bool]:
    job_list = kwargs[CLI_JOB_LIST.name]
    results = [False] * len(job_list)

    for idx, job_id in enumerate(job_list):
        job_dto = db_manager.get_job(job_id)
        if job_dto.status not in [Job_Status.REVIEW, Job_Status.ERROR]:
            logger.warning(f"{job_id} in {job_dto.status}, skipping")
            continue

        if video_manager.rerun_validation(job_dto, get_config()):
            job_dto.status = Job_Status.REVIEW
            db_manager.upsert_job(job_dto)
            results[idx] = True
        else:
            logger.warning(f"Unable to rerun validaton on job {job_id}")

    return results


@JobManager.register_command("reset-job")
def _reset_job(*args, **kwargs) -> Encoding_Job_DTO:
    job_id = kwargs[CLI_JOB_ID.name]
    job_dto = db_manager.get_job(job_id)
    if not job_dto:
        logger.error(f"{job_id} not found or is not in error")
        return

    job_dto, command = encoder.get_encode_command(job_dto, None)

    output_file = job_dto.output
    if os.path.exists(output_file):
        output_metadata = video_manager.get_video_metadata(output_file)
        if is_reset := user_prompts.prompt_review_job(job_dto, None, output_metadata):
            db_manager.upsert_job(job_dto)

    return job_dto


@JobManager.register_command("process-dir", CLI_INPUT_PATH, CLI_OUTPUT_PATH, CLI_ENCODING_PROFILE)
def _process_dir(*args, **kwargs) -> int:
    input_dir = kwargs[CLI_INPUT_PATH.name]
    output_dir = kwargs[CLI_OUTPUT_PATH.name]
    profile_s = kwargs[CLI_ENCODING_PROFILE.name]
    profile = types.get_profile(profile_s)

    if not os.path.isdir(input_dir):
        logger.error(f"Invalid directory: {input_dir}")
        return 0
    proc_count = 0
    for dir_name, _, file_list in os.walk(input_dir):
        pending_jobs = db_manager.get_pending_jobs_by_directory(PurePath(dir_name).as_posix(), status=Job_Status.PENDING)
        review_jobs = db_manager.get_pending_jobs_by_directory(PurePath(dir_name).as_posix(), status=Job_Status.REVIEW)
        existing_jobs = pending_jobs + review_jobs
        logger.verbose(f"{len(existing_jobs)} pending jobs for {dir_name}")
        existing_files = [PurePath(dto.input).as_posix() for dto in existing_jobs]
        dir_count = len(file_list) - len(existing_files)
        file_idx = 0
        for file_name in sorted(
            [file for file in file_list if video_manager.is_video_file(file)], key=lambda file: Path(os.path.join(dir_name, file)).stat().st_size, reverse=True
        ):
            file_idx += 1
            file_path = os.path.join(dir_name, file_name)
            if PurePath(file_path).as_posix() in existing_files:
                logger.info(f"Skipping {file_path}, job already exists")
                continue
            else:
                logger.info(f"Job {file_idx} / {dir_count}")
                job_dto, _ = _process_file(file_path, output_dir, profile, Job_Status.PENDING)
                if job_dto:
                    logger.info(f"{file_path} processed. Proceeding to next file")
                    proc_count += 1
                elif os.path.exists(file_path):
                    logger.info("User selected quit")
                    return proc_count
                else:
                    logger.info(f"User deleted {file_path}, continuing")
                    continue

    return proc_count


@JobManager.register_command("manual-job", CLI_INPUT_PATH, CLI_OUTPUT_PATH, CLI_ENCODING_PROFILE, CLI_SIMULATE, CLI_QUEUE_JOB, CLI_SKIP_PROMPT)
def _manual_run_file(*args, **kwargs) -> bool:
    input_path = kwargs[CLI_INPUT_PATH.name]
    input_file_path = input_path
    output_path = kwargs[CLI_OUTPUT_PATH.name]

    profile = None
    if profile_s := kwargs.get(CLI_ENCODING_PROFILE.name, None):
        profile = types.get_profile(profile_s)

    is_simulate = kwargs[CLI_SIMULATE.name]
    is_queue = kwargs[CLI_QUEUE_JOB.name]
    is_skip_prompt = kwargs[CLI_SKIP_PROMPT.name]

    if os.path.isdir(input_path):
        existing_jobs = db_manager.get_pending_jobs_by_directory(PurePath(input_path).as_posix())
        logger.verbose(f"{len(existing_jobs)} pending jobs for {input_path}")
        existing_files = [dto.input for dto in existing_jobs]

        path = Path(input_path)
        files = [
            file for file in path.iterdir() if file.is_file() and video_manager.is_video_file(file.name) and PurePath(file).as_posix() not in existing_files
        ]
        files_by_size = sorted(files, key=lambda file: file.stat().st_size, reverse=True)
        input_file_path = str(files_by_size[0].absolute())
    elif not os.path.isfile(input_path):
        logger.error(f"Invalid path: {input_path}")
        return False

    job_dto, input_metadata = _process_file(input_file_path, output_path, profile, Job_Status.IND_JOB, is_simulate)

    if not job_dto or not input_metadata:
        return False

    if is_simulate:
        updated_dto, encode_command = encoder.get_encode_command(job_dto, input_metadata)
        print(" ".join(encode_command))

        metrics = VideoMetrics.from_ffprobe_data(input_metadata, job_dto.profile, False).to_pretty_list()
        table = generate_aligned_table([VideoMetrics.get_data_labels(), metrics])
        print("\n".join(table))

        return True

    if is_queue:
        job_dto.status = Job_Status.PENDING
        db_manager.upsert_job(job_dto)
        logger.info(f"Job queued for {input_path}")
        return True

    job_dto.status = Job_Status.WORKING
    db_manager.upsert_job(job_dto)

    job_results_dto, ouptut_metadata = encoder.encode_file(job_dto, input_metadata, is_skip_prompt)
    if job_results_dto:
        db_manager.upsert_job(job_results_dto)
        if job_results_dto.status == Job_Status.REVIEW:
            _review_job(job_results_dto, input_metadata, ouptut_metadata)
            return job_results_dto.status == Job_Status.COMPLETE
    else:
        job_dto.status = Job_Status.PENDING
        db_manager.upsert_job(job_dto)

    return False


@JobManager.register_command("review-jobs")
def review_results(*args, **kwargs):
    job_list = db_manager.get_next_job_by_status(Job_Status.REVIEW, limit=999)
    if not job_list:
        print("No jobs available to review.")
        return
    job_count = len(job_list)
    logger.info(f"{job_count} jobs to review")
    job_idx = 0

    curr_job_prepx_results = encoder.JobPreprocessResult(None, None, None, None)

    curr_job = job_list.pop(0)
    next_job = job_list.pop(0) if job_list else None
    while True:
        job_idx += 1
        next_job_prepx_results = encoder.JobPreprocessResult(None, None, None, None)

        if next_job:
            preprocess_thread = threading.Thread(target=encoder.background_process_job, args=(next_job, next_job_prepx_results), daemon=True)
            preprocess_thread.start()
        else:
            preprocess_thread = None

        logger.verbose(f"Next Job: {curr_job.job_id}")
        logger.info(f"Progress: {job_idx}/{job_count} ({job_count - job_idx} remaining)")

        if not _review_job(curr_job, curr_job_prepx_results):
            print("User terminated review.")
            break

        if preprocess_thread:
            preprocess_thread.join()

        curr_job = next_job
        next_job = job_list.pop(0) if job_list else None
        curr_job_prepx_results = next_job_prepx_results

        if not curr_job:
            print("No jobs available to review.")
            break


def _process_file(
    input_file_path: str, output_dir: str, profile: EncodingProfile, initial_status: Job_Status, is_simulate: bool = False
) -> tuple[Encoding_Job_DTO, dict[str, Any]]:
    input_metadata = video_manager.get_video_metadata(input_file_path)
    if input_metadata["v_count"] == 0:
        logger.warning(f"{input_file_path} is actually an audio file, skipping")
        return None, None

    job_dto = _generate_job_dto(input_metadata, output_dir, profile)
    if job_dto:
        if not is_simulate:
            job_dto.status = initial_status
            db_manager.upsert_job(job_dto)
        return job_dto, input_metadata

    return None, None


def _review_job(job_dto: Encoding_Job_DTO, preprocess_results: encoder.JobPreprocessResult = encoder.JobPreprocessResult(None, None, None, None)) -> bool:
    if not job_dto:
        return False

    if user_prompts.prompt_review_job(job_dto, **vars(preprocess_results)):
        db_manager.upsert_job(job_dto)
        return True
    return False


def _generate_job_dto(input_metadata: dict[str, Any], output_dir: str, profile: EncodingProfile) -> Encoding_Job_DTO:
    input_file_path = input_metadata["format_data"]["filename"]

    if not os.path.isfile(input_file_path):
        logger.error(f"Invalid input file: {input_file_path}")
        return False
    if not os.path.isdir(output_dir):
        logger.error(f"Invalid output directory: {output_dir}")
        return False

    adv_opts = Advanced_Options_DTO()
    if not profile:
        profile = user_prompts.prompt_encoding_profile(input_metadata, adv_opts)

    if not profile:
        return None

    encoding_params = Encoding_Job_DTO(
        job_id=None,
        input=input_file_path,
        output=output_dir,
        profile=profile,
        adv_params=adv_opts,
        duration=input_metadata["format_data"]["duration"],
        size_in=input_metadata["format_data"]["size"],
    )

    logger.verbose(f"Chosen profile: {profile}")
    logger.verbose(f"Advanced Options: {adv_opts}")

    return encoding_params


def test():
    pass


if __name__ == "__main__":
    test()
