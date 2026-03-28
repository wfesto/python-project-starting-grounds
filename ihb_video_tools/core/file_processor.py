import concurrent.futures
import logging
import os
import queue
import threading
import time
from collections.abc import Callable, Generator
from pathlib import PurePath
from typing import Any

from ihb_common.utils.file_utils import get_xxh64_hash
from ihb_common.utils.gen_utils import format_time, generate_aligned_table
from ihb_components.cli.cli_utils import *
from ihb_video.manager import video_manager

from ..conf.config import get_config
from ..data.dto import File_DTO
from . import db_manager

logger = logging.getLogger(__name__)


class FileProcessor(BaseWorkflowManager):
    CLI_HELP = "File/Directory Operations"
    COMMAND_MAP: dict[str, Callable] = {}
    FLAG_MAP: dict[str, tuple[CliArgument, ...]] = {}


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
        file_hash = get_xxh64_hash(file_path, is_use_partial=is_use_partial)
        file_data = video_manager.get_py_video_metadata(file_path)
        dto = File_DTO.from_pym_data(file_data, file_hash)
        record_queue.put(dto, block=True)

    except Exception as e:
        exc = File_Processing_Exception(file_path, str(e))
        logger.error(f"{exc}")
        raise exc
    logger.debug(f"{threading.get_ident()} END")


def _find_ghosts(file_generator: Generator[str, None, None], is_delete_ghosts: bool = True) -> tuple[set[str], set[str]]:
    keep_list: set[str] = set()
    ghost_list: set[str] = set()

    idx = 0
    for file in file_generator:
        idx += 1
        if os.path.exists(file):
            keep_list.add(file)
        else:
            ghost_list.add(file)

    if is_delete_ghosts:
        db_manager.delete_records(ghost_list)

    logger.info(f"{idx} records - {len(keep_list)} kept, {len(ghost_list)} deleted")
    return keep_list, ghost_list


@FileProcessor.register_command("process-dir", CLI_INPUT_PATH)
def _process_dir(*args, **kwargs) -> int:
    input_dir = kwargs[CLI_INPUT_PATH.name]
    if not os.path.exists(input_dir):
        logger.error(f"{input_dir} does not exist. Existing.")
        return 0

    db_manager.verify_db()
    config = get_config()

    old_dto_list = db_manager.read_all_records(input_dir)
    logger.verbose(f"{len(old_dto_list)} records retrieved from db")
    path_generator = (dto.path for dto in old_dto_list)
    existing_set, ghost_set = _find_ghosts(path_generator, is_delete_ghosts=True)

    is_use_partial_hash = config["general"]["hash_partial"]
    max_workers = config["general"]["max_workers"]

    stop_event = threading.Event()
    record_queue = queue.Queue(max_workers * 4)
    db_writer_thread = threading.Thread(target=db_manager.db_writer, kwargs={"record_queue": record_queue, "stop_event": stop_event})
    db_writer_thread.start()

    total_files = 0
    video_files = 0
    dupe_count = 0
    fresh_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=(max_workers)) as processor_pool:
        logger.info("Pool started")
        processor_jobs: list[concurrent.futures.Future[File_DTO]] = []

        start_time = time.perf_counter()
        for dir_path, _, file_list in os.walk(input_dir):
            for file_name in file_list:
                file_path = PurePath(os.path.join(dir_path, file_name)).as_posix().lower()
                total_files += 1
                if video_manager.is_video_file(file_path):
                    video_files += 1
                    if file_path in existing_set:
                        existing_set.remove(file_path)
                        dupe_count += 1
                    else:
                        processor_job = processor_pool.submit(file_processor, file_path, is_use_partial_hash, record_queue)
                        processor_jobs.append(processor_job)
                        fresh_count += 1
        logger.info("all jobs added")
        logger.info(f"pending jobs: {processor_pool._work_queue.qsize()}")

        processor_pool.shutdown(wait=True)

    stop_event.set()
    db_writer_thread.join()
    end_time = time.perf_counter()
    time_elapsed = end_time - start_time

    logger.info(f"{dupe_count} duplicates ignored")
    logger.info(f"{fresh_count} new files processed")

    # file_results = []
    file_errors = []
    file_proc_count = 0

    for job in processor_jobs:
        if exc := job.exception():
            file_errors.append(exc)
        else:
            file_proc_count += 1

    labels = ["Total files", "Video Files", "Processed", "Duplicates", "Ghosts", "Errors"]
    data = [str(total_files), str(video_files), str(file_proc_count), str(dupe_count), str(len(ghost_set)), str(len(file_errors))]
    for row in generate_aligned_table(labels, data):
        logger.info(row)
    logger.info(f"Time elapsed: {format_time(time_elapsed)}")

    return file_proc_count, file_errors


def test():
    pass


if __name__ == "__main__":
    test()
