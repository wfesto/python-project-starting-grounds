import logging
from dataclasses import dataclass
from queue import PriorityQueue
from time import sleep
from typing import Any

from ihb_video.manager import video_manager
from ihb_video.types.video_models import VideoMetrics

from ..conf.config import get_config
from ..data import Encoding_Job_DTO, Job_Status, db_manager

logger = logging.getLogger(__name__)


def get_encode_command(encoding_params: Encoding_Job_DTO, input_metadata: dict[str, Any]) -> tuple[Encoding_Job_DTO, list]:
    config = get_config()
    return video_manager.generate_encode_command(encoding_params, input_metadata, config)


def encode_file(encoding_params: Encoding_Job_DTO, input_metadata: dict[str, Any], is_skip_prompt: bool = False) -> tuple[Encoding_Job_DTO, dict[str, Any]]:
    config = get_config()

    try:
        job_results, output_metadata = video_manager.encode_video(encoding_params, input_metadata, config, is_skip_prompt)
        if job_results and output_metadata:
            job_results.status = Job_Status.REVIEW
            return job_results, output_metadata

    except Exception as e:
        logger.error(f"Error occured while encoding: {str(e)}", exc_info=True)
        encoding_params.status = Job_Status.ERROR
        encoding_params.notes["error"] = str(e)
        return encoding_params, None

    return None, None


@dataclass
class JobPreprocessResult:
    input_metadata: dict[str, Any]
    output_metadata: dict[str, Any]
    old_metrics: VideoMetrics
    new_metrics: VideoMetrics


def background_process_job(job_queue: PriorityQueue):
    processed_jobs = set()

    while True:
        is_sleep = False
        logger.verbose(f"Retrieving more jobs to preprocess")
        if job_list := db_manager.get_next_job_by_status(Job_Status.REVIEW, limit=5):
            for job_dto in job_list:
                is_sleep = True
                if job_dto.job_id in processed_jobs:
                    continue

                processed_jobs.add(job_dto.job_id)

                try:
                    logger.verbose(f"Processing job {job_dto.job_id}")
                    preprocess_results = JobPreprocessResult(None, None, None, None)

                    preprocess_results.input_metadata = video_manager.get_video_metadata(job_dto.input)
                    preprocess_results.output_metadata = video_manager.get_video_metadata(job_dto.output)

                    preprocess_results.old_metrics = VideoMetrics.from_ffprobe_data(preprocess_results.input_metadata, job_dto.profile, True)
                    preprocess_results.new_metrics = VideoMetrics.from_ffprobe_data(preprocess_results.output_metadata, job_dto.profile, True)

                    neg_job_size = -1 * int(preprocess_results.input_metadata["format_data"]["size"])

                    job_queue.put((neg_job_size, job_dto.job_id, job_dto, preprocess_results))

                except Exception as e:
                    logger.error(f"Processed jobs: {processed_jobs}")
                    logger.error(f"Error during processing job for {job_dto.job_id}: {str(e)}", exc_info=True)

            if is_sleep:
                sleep(5)

        else:
            logger.info("No jobs remaning to proces.")
            job_queue.put(None)
            return False


def test():
    pass


if __name__ == "__main__":
    test()
