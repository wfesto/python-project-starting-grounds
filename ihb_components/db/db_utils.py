import logging
import os
import sqlite3
from typing import Any, Dict, List

from ihb_components.db import db_scripts

logger = logging.getLogger(__name__)

COMMAND_MAP = {}


def get_actions() -> List[str]:
    return list(COMMAND_MAP.keys())


def execute_action(action: str, *args, **kwargs):
    if method := COMMAND_MAP.get(action):
        try:
            logger.info(f"Executing {action}")
            return method(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error executing {action}: {str(e)}", exc_info=True)
    else:
        logger.error(f"Undefined action: {action}")


def register_command(command):
    def decorator(func):
        COMMAND_MAP[command] = func
        return func

    return decorator


@register_command("drop")
def drop_db(db_conn: str):
    db_file = db_conn
    if os.path.isfile(db_file):
        os.remove(db_file)
    return True


@register_command("count")
def count_records_by_table(db_conn: str):
    with sqlite3.connect(db_conn) as db:
        cursor = db.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(db_scripts.select_tables)
        table_list = [str(row[0]) for row in cursor.fetchall()]
        table_count = {}
        for table in table_list:
            table_count[table] = cursor.execute(db_scripts.count_table_rows_str_format.format(TABLE=table)).fetchone()[0]

        return table_count


""""
@register_command("output")
def output_db():
    print_records(is_include_metadata=False)


@register_command("output-json")
def output_db_with_records():
    print_records(is_include_metadata=True)


@register_command("verify")
def verify_db():
    db_file = get_config()["db"]["conn"]
    if not os.path.isfile(db_file):
        create_db()


@register_command("update")
def update_db():
    with sqlite3.connect(get_config()["db"]["conn"]) as db:
        cursor = db.cursor()
        for script in schema.UPDATE_SCRIPTS:
            cursor.execute(script)
        db.commit()


@register_command("ghosts")
def delete_ghost_records():
    dto_list = read_all_records()
    path_list = [dto.path for dto in dto_list if not os.path.isfile(dto.path)]
    delete_records(path_list)
"""
