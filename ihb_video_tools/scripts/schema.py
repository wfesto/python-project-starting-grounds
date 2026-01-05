create_table_file_data = """
   create table if not exists file_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT UNIQUE,
        hash TEXT,
        size INTEGER,
        duration REAL,
        md_version INTEGER,
        metadata JSON,
        ts_created TEXT DEFAULT CURRENT_TIMESTAMP,
        ts_modified TEXT DEFAULT CURRENT_TIMESTAMP
    )
"""

create_index_hash_file_data = """
    create index if not exists file_data_hash
        on file_data(hash)
"""
create_index_duration_file_data = """
    create index if not exists file_data_duration
        on file_data(duration)
"""


CREATE_SCRIPTS = [
    create_table_file_data,
    create_index_hash_file_data,
    create_index_duration_file_data,
]

UPDATE_SCRIPTS = [
    create_index_hash_file_data,
    create_index_duration_file_data,
]
