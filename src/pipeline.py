"""
pipeline.py
-----------
Ties every step together for ONE natural language query.
This is the function both run.py (batch mode) and api/main.py
(live API for the frontend) call.

Flow:
  1. Build schema context
  2. Plan (LLM call 1)
  3. Generate SQL (LLM call 2)
  4. Execute
  5. If it fails: try to fix once (LLM call 3, capped)
  6. Score confidence
  7. Build explanation
  8. Return the final JSON-shaped answer
"""

from src.schema_context import build_schema_context
from src.planner import make_plan
from src.sql_generator import generate_sql, fix_sql, is_sql_safe
from src.executor import execute_sql, simplify_result
from src.confidence import score_confidence


def answer_query(con, question: str) -> dict:
    schema_context = build_schema_context(con)

    # Step 1: plan
    plan = make_plan(question, schema_context)

    # Step 2: generate SQL
    sql = generate_sql(plan, schema_context)

    # Safety check before running anything
    if not is_sql_safe(sql):
        return {
            "query": question,
            "generated_logic": sql,
            "result": None,
            "confidence_score": 0.0,
            "explanation": "Generated SQL failed the safety check (not a read-only SELECT). Refused to execute.",
        }

    # Step 3: execute, with one self-correction retry on failure
    success, result_or_error = execute_sql(con, sql)
    executed_without_retry = success

    if not success:
        fixed_sql = fix_sql(sql, result_or_error, schema_context)
        if is_sql_safe(fixed_sql):
            success, result_or_error = execute_sql(con, fixed_sql)
            if success:
                sql = fixed_sql

    if success:
        result = simplify_result(result_or_error)
    else:
        result = None

    # Step 4: confidence score
    confidence = score_confidence(plan, executed_without_retry and success, result)

    # Step 5: explanation (reuses the plan's "understanding" + the SQL)
        # Step 5: explanation (reuses the plan's "understanding" + the SQL)
    if success:
        null_note = ""
        if isinstance(result, list):
            has_nulls = any(
                isinstance(row, dict) and any(v is None for v in row.values())
                for row in result
            )
            if has_nulls:
                null_note = (
                    " Note: the result contains missing values because the dataset "
                    "doesn't have enough historical data to fully answer this "
                    "(e.g. a prior period needed for comparison isn't present). "
                    "Confidence was lowered accordingly."
                )

        explanation = (
            f"Understood as: {plan.get('understanding', 'N/A')}. "
            f"Generated and ran SQL against the sales/targets tables to compute this."
            f"{null_note}"
        )
    else:
        explanation = (
            f"Understood as: {plan.get('understanding', 'N/A')}. "
            f"Query failed even after one correction attempt. Error: {result_or_error}"
        )

    return {
        "query": question,
        "generated_logic": sql,
        "result": result,
        "confidence_score": confidence,
        "explanation": explanation,
    }
