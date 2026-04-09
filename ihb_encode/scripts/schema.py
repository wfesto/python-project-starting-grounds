SCHEMA_SCRIPTS = []


def register_schema(func):
    SCHEMA_SCRIPTS.append(func())
    return func


@register_schema
def _create_table_jobs():
    return """
    create table if not exists jobs (
        job_id INTEGER PRIMARY KEY,
        input TEXT UNIQUE,
        output TEXT,
        duration REAL,
        size_in INTEGER,
        size_out INTEGER,
        status INTEGER,
        current_exe_id INTEGER,
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
    );
"""


@register_schema
def _create_table_job_execution():
    return """
    create table if not exists job_execution (
        pk_id INTEGER PRIMARY KEY,
        job_id INTEGER NOT NULL,
        run_ctr INTEGER NOT NULL,
        profile_id INTEGER NOT NULL,
        size_in INTEGER NOT NULL,
        size_out INTEGER,
        duration REAL,
        encode_cmd TEXT,
        exit_cd INTEGER,
        error_log TEXT,
        status INTEGER NOT NULL,
        ts_created TEXT DEFAULT CURRENT_TIMESTAMP,
        ts_modified TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (job_id, run_ctr),
        FOREIGN KEY (job_id)
        REFERENCES jobs(job_id)
        ON DELETE CASCADE
    );

    CREATE TRIGGER IF NOT EXISTS update_job_exe_timestamp 
        AFTER UPDATE ON job_execution
        BEGIN
        UPDATE job_execution
        SET ts_modified = CURRENT_TIMESTAMP
            WHERE pk_id = OLD.pk_id;
    END;
"""


@register_schema
def _create_table_status():
    return """
    create table if not exists status (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status INTEGER,
        status_name TEXT,
        language TEXT default 'def',
        ts_created TEXT default CURRENT_TIMESTAMP,
        ts_modified TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(status, language)
    );

    CREATE TRIGGER IF NOT EXISTS update_status_timestamp 
        AFTER UPDATE ON status
        BEGIN
        UPDATE status
        SET ts_modified = CURRENT_TIMESTAMP
            WHERE id = OLD.id;
    END;    
"""


@register_schema
def _create_table_profile():
    return """
    create table if not exists profile (
        id integer PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        version INTEGER,
        is_active INTEGER,
        fixed_dim INTEGER,
        crf REAL,
        encoder_preset TEXT,
        is_source INTEGER,
        params TEXT,
        ts_created TEXT default CURRENT_TIMESTAMP,
        ts_modified TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TRIGGER IF NOT EXISTS update_profile_timestamp 
        AFTER UPDATE ON profile
        BEGIN
        UPDATE profile
        SET ts_modified = CURRENT_TIMESTAMP
            WHERE id = OLD.id;
    END;    
"""
