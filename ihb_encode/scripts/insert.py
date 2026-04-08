insert_table_jobs = """
    insert into jobs (input, output, profile, duration, size_in, size_out, status) 
        VALUES (:input, :output, :profile, :duration, :size_in, :size_out, :status)
    ON CONFLICT (input)
    DO UPDATE SET
        output = excluded.output,
        profile = excluded.profile,
        size_out = excluded.size_out,
        status = excluded.status
    RETURNING *
"""

insert_table_job_history = """
    INSERT INTO job_history (job_id, seq_id, status_before, status_after, notes)
        SELECT 
            :job_id,
            (SELECT COALESCE(MAX(seq_id), 0) + 1 FROM job_history WHERE job_id = :job_id),
            COALESCE((SELECT status_after FROM job_history WHERE job_id = :job_id ORDER BY seq_id DESC LIMIT 1), :status_before),
            :status_after,
            :notes
"""

insert_table_job_errors = """"
    insert into job_errors (job_id, seq_id, error)
    VALUES (:job_id, :seq_id, :error)
"""
