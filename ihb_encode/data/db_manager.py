import json
import logging
import os
import sqlite3

from ..conf.config import get_config
from ..scripts import insert, schema, seed_data, select, update
from .types import *

logger = logging.getLogger(__name__)


def get_job(job_id: int) -> Encoding_Job_DTO:
    with sqlite3.connect(get_config()["db_conn"]) as db:
        cursor = db.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(select.select_job_by_id, {"job_id": job_id})
        job_dto = Encoding_Job_DTO.from_sql_row(cursor.fetchall()[0])
        return job_dto


def get_pending_jobs_by_directory(input_dir: str, status: Job_Status = Job_Status.PENDING) -> list[Encoding_Job_DTO]:
    with sqlite3.connect(get_config()["db_conn"]) as db:
        cursor = db.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(select.select_jobs_by_directory, {"directory": input_dir, "status": status.value})
        job_list = [Encoding_Job_DTO.from_sql_row(row) for row in cursor.fetchall()]
        return job_list


def get_jobs_by_status_and_size(status: Job_Status, max_size: int) -> list[Encoding_Job_DTO]:
    with sqlite3.connect(get_config()["db_conn"]) as db:
        cursor = db.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(select.select_bulk_jobs_by_status_and_size, {"status": status.value, "max_size": max_size})
        job_list = [Encoding_Job_DTO.from_sql_row(row) for row in cursor.fetchall()]
        return job_list


def bulk_update_job_status(old_status: Job_Status, new_status: Job_Status):
    with sqlite3.connect(get_config()["db_conn"]) as db:
        cursor = db.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(update.update_bulk_job_status, {"old_status": old_status.value, "new_status": new_status.value})
        rowcount = cursor.rowcount
        logger.verbose(f"{rowcount} rows updated.")
        db.commit()
        return rowcount


def force_job_status(job_id: int, new_status: Job_Status) -> bool:
    with sqlite3.connect(get_config()["db_conn"]) as db:
        cursor = db.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(update.update_job_status, {"job_id": job_id, "status": new_status.value})
        rowcount = cursor.rowcount
        logger.verbose(f"{rowcount} rows updated.")
        db.commit()
        return rowcount == 1


def select_job_counts():
    with sqlite3.connect(get_config()["db_conn"]) as db:
        cursor = db.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(select.select_job_counts)
        status_counts = []
        for row in cursor.fetchall():
            status_counts.append(dict(row))

        return status_counts


def get_next_job_by_status(status: Job_Status, limit: int = 1) -> list[Encoding_Job_DTO]:
    with sqlite3.connect(get_config()["db_conn"]) as db:
        cursor = db.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(select.select_largest_job_by_status, {"status": status.value, "limit": limit})
        rows = list(cursor.fetchall())
        if rows:
            job_list = [Encoding_Job_DTO.from_sql_row(row) for row in rows]
            return job_list

        return None


def upsert_job(job_dto: Encoding_Job_DTO):
    with sqlite3.connect(get_config()["db_conn"]) as db:
        job_params = job_dto.to_sql_params()
        logger.verbose(job_params)

        cursor = db.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(insert.insert_table_jobs, job_params)
        updated_job_data = dict(cursor.fetchone())
        logger.verbose(updated_job_data)

        updated_job_data["status_before"] = Job_Status.INIT
        updated_job_data["status_after"] = job_params["status"]
        if job_params["notes"]:
            updated_job_data["notes"] = json.dumps(job_params["notes"])
        else:
            updated_job_data["notes"] = None
        cursor.execute(insert.insert_table_job_history, updated_job_data)

        db.commit()


def create_db():
    with sqlite3.connect(get_config()["db_conn"]) as db:
        cursor = db.cursor()
        for script in schema.SCHEMA_SCRIPTS:
            cursor.executescript(script)
        db.commit()

        insert_seed_data()


def insert_seed_data():
    with sqlite3.connect(get_config()["db_conn"]) as db:
        cursor = db.cursor()

        sql_param_list = [status.to_sql_params("en") for status in Job_Status]
        cursor.executemany(seed_data.insert_status, sql_param_list)

        db.commit()


def verify_db():
    db_file = get_config()["db_conn"]
    if not os.path.isfile(db_file):
        create_db()


def drop_db():
    db_file = get_config()["db_conn"]
    if os.path.isfile(db_file):
        os.remove(db_file)


def test():
    pass


if __name__ == "__main__":
    test()
