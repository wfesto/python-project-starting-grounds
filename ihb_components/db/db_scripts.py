select_tables = """
    SELECT name FROM sqlite_master
        WHERE 1=1
            and type = 'table'
            and name NOT LIKE 'sqlite_%'
"""

count_table_rows_str_format = """
    SELECT count(1) from {TABLE}
"""
