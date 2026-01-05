upsert_table_file_data = """
    insert into file_data (path, hash, size, duration, md_version, metadata) 
    VALUES (:path, :hash, :size, :duration, :md_version, :metadata)
    ON CONFLICT (path)
    DO UPDATE SET
        hash = excluded.hash,
        size = excluded.size,
        duration = excluded.duration,
        md_version = excluded.md_version,
        metadata = excluded.metadata,
        ts_modified = CURRENT_TIMESTAMP
    WHERE 
        file_data.size = 0 or 
        file_data.duration = 0 or 
        file_data.metadata is NULL or 
        excluded.md_version > md_version 
"""

delete_record_by_path = """
    delete from file_data where path = :path
"""

select_records_file_data_all = """
    select * from file_data where duration >= :min_duration
"""

order_by_duration_desc = """
    order by duration desc
"""

select_count_records_file_data = """
    select count(1) from file_data
"""

select_records_by_hash = """
    select * from file_data where hash = :hash
"""

select_duplicates_hash_all = """
    select hash, count(1) as hash_count 
        from file_data
        group by hash
        having count(1) > 1
"""
