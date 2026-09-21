"""
executor.py
-----------
Runs the generated SQL against DuckDB and returns a clean, JSON-serializable
result. Catches errors so the pipeline can decide whether to retry.
"""


def execute_sql(con, sql: str):
    """
    Runs the SQL. Returns (success: bool, result_or_error).
    On success, result is a list of dicts (rows). On failure,
    result is the error message string.
    """
    try:
        cursor = con.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        result = [dict(zip(columns, row)) for row in rows]
        return True, result
    except Exception as e:
        return False, str(e)


def simplify_result(rows):
    """
    If the result is a single row with a single column, return just
    that scalar value instead of a list-of-dicts — cleaner for simple
    aggregate answers like "total sales in March".
    """
    if len(rows) == 1 and len(rows[0]) == 1:
        return list(rows[0].values())[0]
    return rows
