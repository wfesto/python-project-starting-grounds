import concurrent.futures
import logging
import os
import queue
import threading
import time
from typing import List

from ihb_ext.video_manager import get_video_metadata, is_video_file
from ihb_utils.file_utils import get_xxh64_hash
from ihb_utils.gen_utils import format_time
from ihb_video_tools.conf.config import get_config
from ihb_video_tools.data.db_manager import db_writer, verify_db
from ihb_video_tools.data.dto import File_DTO

logger = logging.getLogger(__name__)


class File_Processing_Exception(Exception):
    file_path: str
    message: str

    def __init__(self, file_path: str, message: str):
        super().__init__(file_path, message)
        self.file_path = file_path
        self.message = message

    def __str__(self):
        return f"Error processing {self.file_path} || {self.message}"


def file_processor(file_path: str, is_use_partial: bool, record_queue: queue.Queue):
    logger.debug(f"{threading.get_ident()} START")
    try:
        file_data = get_video_metadata(file_path)
        file_hash = get_xxh64_hash(file_path, is_use_partial=is_use_partial)
        dto = File_DTO.from_probe_data(file_data, file_hash)
        record_queue.put(dto, block=True)

    except Exception as e:
        exc = File_Processing_Exception(file_path, str(e))
        logger.error(f"{exc}")
        raise exc
    logger.debug(f"{threading.get_ident()} END")


def process(input_dir: str) -> int:
    verify_db()
    config = get_config()

    is_use_partial_hash = config["general"]["hash_partial"]
    max_workers = config["general"]["max_workers"]

    stop_event = threading.Event()
    record_queue = queue.Queue(max_workers * 4)
    db_writer_thread = threading.Thread(target=db_writer, kwargs={"record_queue": record_queue, "stop_event": stop_event})
    db_writer_thread.start()

    with concurrent.futures.ThreadPoolExecutor(max_workers=(max_workers)) as processor_pool:
        logger.info("Pool started")
        processor_jobs: List[concurrent.futures.Future[File_DTO]] = []

        start_time = time.perf_counter()
        for dir_path, _, file_list in os.walk(input_dir):
            for file_name in [file for file in file_list if is_video_file(file)]:
                file_path = os.path.join(dir_path, file_name)
                processor_job = processor_pool.submit(file_processor, file_path, is_use_partial_hash, record_queue)
                processor_jobs.append(processor_job)
        logger.info("all jobs added")
        logger.info(f"pending jobs: {processor_pool._work_queue.qsize()}")

        processor_pool.shutdown(wait=True)

    stop_event.set()
    db_writer_thread.join()
    end_time = time.perf_counter()
    time_elapsed = end_time - start_time

    # file_results = []
    file_errors = []
    file_proc_count = 0

    for job in processor_jobs:
        if exc := job.exception():
            file_errors.append(exc)
        else:
            file_proc_count += 1

    logger.info(f"{file_proc_count} files successfully processed, {len(file_errors)} errors || Time: {format_time(time_elapsed)}")

    return file_proc_count, file_errors


def test():
    pass


if __name__ == "__main__":
    test()
