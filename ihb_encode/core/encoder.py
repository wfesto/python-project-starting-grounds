import logging
from typing import Any, Dict, Tuple

from ihb_ext import video_manager
from ihb_utils.video_models import VideoMetrics

from ..conf.config import get_config
from ..data import *

logger = logging.getLogger(__name__)


def get_encode_command(encoding_params: Encoding_Job_DTO, input_metadata: Dict[str, Any]) -> Tuple[Encoding_Job_DTO, List]:
    config = get_config()
    return video_manager.generate_encode_command(encoding_params, input_metadata, config)


def encode_file(encoding_params: Encoding_Job_DTO, input_metadata: Dict[str, Any], is_skip_prompt: bool = False) -> Tuple[Encoding_Job_DTO, Dict[str, Any]]:
    config = get_config()

    try:
        job_results, output_metadata = video_manager.encode_video(encoding_params, input_metadata, config, is_skip_prompt)
        if job_results and output_metadata:
            job_results.status = Job_Status.REVIEW
            return job_results, output_metadata

    except Exception as e:
        logger.error(f"Error occured while encoding: {str(e)}", exc_info=True)
        encoding_params.status = Job_Status.ERROR
        encoding_params.notes = str(e)
        return encoding_params, None

    return None, None


@dataclass
class JobPreprocessResult:
    input_metadata: Dict[str, Any]
    output_metadata: Dict[str, Any]
    old_metrics: VideoMetrics
    new_metrics: VideoMetrics


def background_process_job(job_dto: Encoding_Job_DTO, preprocess_results: JobPreprocessResult):
    if not job_dto:
        return

    try:
        preprocess_results.input_metadata = video_manager.get_video_metadata(job_dto.input)
        preprocess_results.output_metadata = video_manager.get_video_metadata(job_dto.output)

        preprocess_results.old_metrics = VideoMetrics.from_ffprobe_data(preprocess_results.input_metadata, job_dto.profile, True)
        preprocess_results.new_metrics = VideoMetrics.from_ffprobe_data(preprocess_results.output_metadata, job_dto.profile, True)
    except Exception as e:
        logger.error(f"Error during preprocessing job for {job_dto.job_id}: {str(e)}", exc_info=True)


def test():
    pass


if __name__ == "__main__":
    test()
