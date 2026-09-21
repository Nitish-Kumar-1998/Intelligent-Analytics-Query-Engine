"""
sql_generator.py
-----------------
LLM call #2.

Takes the structured plan (from planner.py) plus the schema context,
and generates a single DuckDB SQL SELECT statement.

Also handles the self-correction retry: if the SQL fails to execute,
we feed the error message back to the model once and ask it to fix
the query. We cap this at one retry so a broken query can't loop forever.
"""

import json

from src.llm_client import call_llm

SQL_SYSTEM_PROMPT = """You write DuckDB SQL for an analytics engine.
You will be given a schema context and a structured plan describing
what the user wants. Output ONLY the SQL query — no prose, no markdown
fences, no explanation. Just the raw SQL statement.

Rules:
- Only SELECT statements. Never write/modify data.
- Tables available: sales, targets
- Always substitute metric formulas from the schema context (e.g. use the
  real revenue formula, don't reference a 'revenue' column directly since
  it doesn't exist).
- For month-based filters/joins, use strftime(order_date, '%Y-%m').
- Use window functions (RANK, ROW_NUMBER) for "top N within each group" style
  queries.
- If the plan indicates the question can't be answered with available data
  (e.g. missing prior-year data for a YoY query), still write your best-effort
  SQL using only what data exists, since we'll flag low confidence separately.
"""

SQL_FIX_SYSTEM_PROMPT = """You write DuckDB SQL. Your previous SQL query
failed with an error. Fix it and output ONLY the corrected SQL — no prose,
no markdown fences."""


def _clean_sql(raw_response: str) -> str:
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("sql"):
            cleaned = cleaned[3:]
        cleaned = cleaned.strip()
    return cleaned


def generate_sql(plan: dict, schema_context: str) -> str:
    user_prompt = f"""SCHEMA CONTEXT:
{schema_context}

PLAN:
{json.dumps(plan, indent=2)}

Output the SQL query now."""

    raw_response = call_llm(SQL_SYSTEM_PROMPT, user_prompt, max_tokens=500)
    return _clean_sql(raw_response)


def fix_sql(broken_sql: str, error_message: str, schema_context: str) -> str:
    user_prompt = f"""SCHEMA CONTEXT:
{schema_context}

BROKEN SQL:
{broken_sql}

ERROR MESSAGE:
{error_message}

Output the corrected SQL now."""

    raw_response = call_llm(SQL_FIX_SYSTEM_PROMPT, user_prompt, max_tokens=500)
    return _clean_sql(raw_response)


# Basic safety check: reject anything that isn't a read-only SELECT
FORBIDDEN_KEYWORDS = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "CREATE"]


def is_sql_safe(sql: str) -> bool:
    upper_sql = sql.upper()
    if not upper_sql.strip().startswith("SELECT") and not upper_sql.strip().startswith("WITH"):
        return False
    return not any(keyword in upper_sql for keyword in FORBIDDEN_KEYWORDS)
