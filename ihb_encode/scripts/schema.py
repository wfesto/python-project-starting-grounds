SCHEMA_SCRIPTS = []


def register_schema(func):
    SCHEMA_SCRIPTS.append(func())
    return func


@register_schema
def _create_table_jobs():
    return """
    create table if not exists jobs (
        job_id INTEGER PRIMARY KEY,
        input TEXT UNIQUE NOT NULL,
        output TEXT,
        profile TEXT,
        duration REAL,
        size_in INTEGER,
        size_out INTEGER,
        status INTEGER,
        ts_created TEXT DEFAULT CURRENT_TIMESTAMP,
        ts_modified TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TRIGGER IF NOT EXISTS update_jobs_timestamp 
        AFTER UPDATE ON jobs
        BEGIN
        UPDATE jobs 
        SET ts_modified = CURRENT_TIMESTAMP
            WHERE job_id = OLD.job_id;
    END;
"""


@register_schema
def _create_table_job_history():
    return """
    create table if not exists job_history (
        job_id INTEGER,
        seq_id INTEGER,
        status_before INTEGER,
        status_after INTEGER,
        notes TEXT,
        ts_created TEXT DEFAULT CURRENT_TIMESTAMP,
        ts_modified TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(job_id, seq_id),
        FOREIGN KEY (job_id)
            REFERENCES jobs(job_id)
            ON DELETE CASCADE
    )
"""


@register_schema
def _create_table_status():
    return """
    create table if not exists status (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status INTEGER,
        status_name TEXT,
        language TEXT default 'def',
        ts_created TEXT default CURRENT_TIMESTAMP
    )
"""


@register_schema
def _create_table_profile():
    return """"
    create table if not exists profile (
        id integer PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        fixed_dim NUMBER,
        scaled_dim NUMBER,
        crf NUMBER,
        encoder_preset TEXT,
        params_265 TEXT,
        is_source: BOOLEAN,
        ts_created TEXT default CURRENT_TIMESTAMP,
        ts_modified TEXT default CURRENT_TIMESTAMP
    )
"""
