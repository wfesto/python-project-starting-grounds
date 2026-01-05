update_bulk_job_status = """
    update jobs
        set status = :new_status
        where status = :old_status
"""

update_job_status = """
    update jobs
        set status = :status
        where job_id = :job_id
"""
