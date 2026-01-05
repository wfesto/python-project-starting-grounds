select_job_by_id = """
    select * from jobs
    where 1=1
        and jobs.job_id = :job_id
"""

select_jobs_by_directory = """
    select * from jobs
    where 1=1
        and jobs.input like :directory || '%'
        and jobs.status = :status
"""

select_largest_job_by_status = """
    WITH RankedHistory AS (
        SELECT 
            job_id,
            notes,
            seq_id,
            ROW_NUMBER() OVER (PARTITION BY job_id ORDER BY seq_id DESC) as latest_rank
        FROM job_history
    )
    SELECT 
        j.*, rh.notes 
    FROM jobs j
    JOIN RankedHistory rh ON j.job_id = rh.job_id
    WHERE rh.latest_rank = 1
    AND j.status = :status
    ORDER BY j.size_in DESC
    limit :limit
"""

select_bulk_jobs_by_status_and_size = """
    select * from jobs
        where status = :status
        and size_out <= :max_size
"""

select_job_counts = """
    select 
	    status, count(1) as count, sum(size_in) as size_in, sum(size_out) as size_out
	    from jobs
	    group by status
	    order by status desc
"""
