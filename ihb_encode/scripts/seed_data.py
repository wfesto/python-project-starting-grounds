insert_status = """
    insert into status (status, status_name, language)
        VALUES (:status, :status_name, :language)
    ON CONFLICT (status, language)
        DO UPDATE SET
            status_name = excluded.status_name
        WHERE status.status_name IS DISTINCT FROM EXCLUDED.status_name
    ;
"""


select_all_status = """
    select * from status
        where language = :language
        order by status asc
"""
