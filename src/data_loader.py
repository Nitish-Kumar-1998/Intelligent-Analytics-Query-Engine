"""
data_loader.py
---------------
Loads the CSV files into an in-memory DuckDB database.
DuckDB lets us run real SQL directly against the CSVs, no separate
database server needed.
"""

import duckdb
import os

DATASET_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset")


def get_connection():
    """
    Creates a fresh in-memory DuckDB connection and loads
    sales_data.csv and targets.csv into it as real SQL tables.
    """
    con = duckdb.connect(database=":memory:")

    sales_path = os.path.join(DATASET_DIR, "sales_data.csv")
    targets_path = os.path.join(DATASET_DIR, "targets.csv")

    con.execute(f"""
        CREATE TABLE sales AS
        SELECT * FROM read_csv_auto('{sales_path}')
    """)

    con.execute(f"""
        CREATE TABLE targets AS
        SELECT * FROM read_csv_auto('{targets_path}')
    """)

    return con


def get_table_columns(con, table_name):
    """Returns a list of column names for a given table."""
    result = con.execute(f"DESCRIBE {table_name}").fetchall()
    return [row[0] for row in result]


def get_sample_rows(con, table_name, limit=3):
    """Returns a few sample rows as a list of dicts, for grounding the LLM."""
    columns = get_table_columns(con, table_name)
    rows = con.execute(f"SELECT * FROM {table_name} LIMIT {limit}").fetchall()
    return [dict(zip(columns, row)) for row in rows]


def get_distinct_values(con, table_name, column_name, limit=20):
    """Returns distinct values for a column (useful for categorical fields)."""
    rows = con.execute(
        f"SELECT DISTINCT {column_name} FROM {table_name} LIMIT {limit}"
    ).fetchall()
    return [row[0] for row in rows]


if __name__ == "__main__":
    # Quick manual test
    con = get_connection()
    print("sales columns:", get_table_columns(con, "sales"))
    print("targets columns:", get_table_columns(con, "targets"))
    print("sample sales rows:", get_sample_rows(con, "sales"))
