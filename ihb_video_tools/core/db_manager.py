import logging
import os
import queue
import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import PurePath
from typing import Any

from ihb_components.cli.cli_utils import BaseWorkflowManager, CliArgument

from ..conf.config import get_config
from ..data.dto import File_DTO
from ..scripts import data, schema

logger = logging.getLogger(__name__)


class DbManager(BaseWorkflowManager):
    CLI_HELP = "Duplicate Operations"
    COMMAND_MAP: dict[str, Callable] = {}
    FLAG_MAP: dict[str, tuple[CliArgument, ...]] = {}


def db_writer(record_queue: queue.Queue, stop_event: threading.Event):
    record_cache = []

    cache_max = get_config()["db"]["cache"]
    sleep_time = get_config()["db"]["writer_sleep"]

    while not (stop_event.is_set() and record_queue.empty()):
        try:
            dto: File_DTO = record_queue.get(timeout=0.1)
            record_cache.append(dto.to_db_params())
            record_queue.task_done()

            if len(record_cache) >= cache_max:
                logger.info(f"writing data {len(record_cache)}")
                _write_records(record_cache)
                logger.info("data written")

        except queue.Empty:
            time.sleep(sleep_time)

    _write_records(record_cache)


def _write_records(record_list: list[dict[str, Any]]):
    if not record_list:
        logger.debug("write_records called with no records")
        return

    logger.debug("Writing records")
    with sqlite3.connect(get_config()["db"]["conn"]) as db:
        cursor = db.cursor()
        cursor.executemany(data.upsert_table_file_data, record_list)
        db.commit()
    logger.debug(f"{len(record_list)} records upserted")
    record_list.clear()


def print_records(is_include_metadata: bool = False):
    if dto_list := read_all_records():
        for dto in dto_list:
            print(dto)
            if is_include_metadata:
                print(f"v{dto.md_version} {dto.metadata}")

        print(f"{len(dto_list)} records found")


def find_duplicates_by_hash():
    with sqlite3.connect(get_config()["db"]["conn"]) as db:

        path_dict = {}
        hash_list = []

        cursor = db.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(data.select_duplicates_hash_all)

        for record in cursor:
            hash = record["hash"]
            hash_list.append(hash)
            path_dict[hash] = []

        for hash in hash_list:
            result_set = cursor.execute(data.select_records_by_hash, {"hash": hash})
            for record in result_set.fetchall():
                dto = File_DTO.from_db_record(record)
                path_dict[hash].append(dto)

        return path_dict


def find_duplicate_pairs_by_duration():
    batch_size = get_config()["db"]["batch_size"]

    with sqlite3.connect(get_config()["db"]["conn"]) as db:
        cursor = db.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(f"{data.select_records_file_data_all} {data.order_by_duration_desc}")

        records = []

        while True:
            if results := cursor.fetchmany(batch_size):
                records.extend([File_DTO.from_db_record(record) for record in results])
            else:
                break

        print(len(records))


def read_all_records(target_dir: str = "", is_min_duration: bool = False):
    db_file = get_config()["db"]["conn"]
    if not os.path.isfile(db_file):
        logger.warning("No db found")
        return

    query_param = {"min_duration": (get_config()["general"]["min_duration"] if is_min_duration else 0)}
    sql_list = [data.select_records_file_data_all]
    if target_dir:
        sql_list.append(data.where_by_directory)
        query_param["path"] = PurePath(target_dir).as_posix()
    sql_list.append(data.order_by_duration_desc)

    sql_str = " ".join(sql_list)

    with sqlite3.connect(db_file) as db:
        cursor = db.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(sql_str, query_param)
        dto_list = [File_DTO.from_db_record(record) for record in cursor]
        return dto_list


def delete_records(path_list: list[str]):
    param_list = []
    for path in path_list:
        param_list.append({"path": path})

    with sqlite3.connect(get_config()["db"]["conn"]) as db:
        cursor = db.cursor()
        cursor.executemany(data.delete_record_by_path, param_list)
        db.commit()


def create_db():
    with sqlite3.connect(get_config()["db"]["conn"]) as db:
        cursor = db.cursor()
        for script in schema.CREATE_SCRIPTS:
            cursor.execute(script)
        db.commit()


@DbManager.register_command("drop")
def drop_db(*args, **kwargs):
    db_file = get_config()["db"]["conn"]
    if os.path.isfile(db_file):
        os.remove(db_file)


@DbManager.register_command("output")
def output_db(*args, **kwargs):
    print_records(is_include_metadata=False)


@DbManager.register_command("output-json")
def output_db_with_records(*args, **kwargs):
    print_records(is_include_metadata=True)


@DbManager.register_command("verify")
def verify_db(*args, **kwargs):
    db_file = get_config()["db"]["conn"]
    if not os.path.isfile(db_file):
        create_db()


@DbManager.register_command("update")
def update_db(*args, **kwargs):
    with sqlite3.connect(get_config()["db"]["conn"]) as db:
        cursor = db.cursor()
        for script in schema.UPDATE_SCRIPTS:
            cursor.execute(script)
        db.commit()


@DbManager.register_command("ghosts")
def delete_ghost_records(*args, **kwargs):
    dto_list = read_all_records()
    path_list = [dto.path for dto in dto_list if not os.path.isfile(dto.path)]
    delete_records(path_list)


@DbManager.register_command("count")
def count_ghost_records(*args, **kwargs):
    with sqlite3.connect(get_config()["db"]["conn"]) as db:
        cursor = db.cursor()
        cursor.execute(data.select_count_records_file_data)
        count = cursor.fetchone()[0]
        print(f"{count} records found")


def test():
    with sqlite3.connect(":memory:") as db:
        cursor = db.cursor()
        for script in schema.CREATE_SCRIPTS:
            cursor.execute(script)

        dto = File_DTO("test_path", "@#)TH)H)HJJIDSVOV#N@PTN", 0, 23.4234, None)
        cursor.execute(data.upsert_table_file_data, dto.to_db_params())
        db.commit()
        result_set = cursor.execute("select * from file_data")
        print(result_set.fetchall())

        time.sleep(2)

        dto = File_DTO("test_path", "@#)TH)H)HJJIDSVOV#N@PTN", 23423532523, 23.4234, None)
        cursor.execute(data.upsert_table_file_data, dto.to_db_params())
        db.commit()
        result_set = cursor.execute("select * from file_data")
        print(result_set.fetchall())


if __name__ == "__main__":
    test()
