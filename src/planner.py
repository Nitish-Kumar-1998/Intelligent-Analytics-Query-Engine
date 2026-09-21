"""
planner.py
----------
LLM call #1.

Takes the raw natural-language question and turns it into a small
structured "plan" — what metric, what grouping, what filter, what
kind of operation (simple aggregate / ranking / comparison / time-based).

Why this is a separate step from writing SQL:
splitting "understand the question" from "write the query" makes the
model much more reliable on the harder queries (top-N per group,
contribution %, target comparisons) because it isn't trying to do
both jobs in one shot.

This plan is also reused later as the "what the system understood"
part of the final explanation, so we don't waste the work.
"""

import json

from src.llm_client import call_llm

PLANNER_SYSTEM_PROMPT = """You are a query planner for an analytics system.
Given a natural language business question and a schema description,
output ONLY a JSON object (no prose, no markdown fences) with these fields:

{
  "metric": "the metric being asked about (e.g. revenue, profit, orders, avg_order_value)",
  "operation": "one of: simple_aggregate, group_by, top_n, ranking_within_group, contribution_percent, target_comparison, time_based, nested",
  "group_by": ["list of dimension columns to group by, empty list if none"],
  "filters": ["list of plain-English filter conditions, e.g. 'country = India', 'month = March 2024'"],
  "top_n": "integer if the query asks for a top/bottom N, otherwise null",
  "time_reference": "any time phrase in the query, otherwise null",
  "needs_target_join": true/false,
  "understanding": "one plain sentence describing what the user is asking for"
}

Use the schema context to resolve business terms (e.g. 'sales' -> revenue metric).
If the query cannot be answered with the available schema (e.g. asks for data
that doesn't exist, like a year with no rows), still fill in the fields as best
you can, but note this clearly inside "understanding".
"""


def make_plan(question: str, schema_context: str) -> dict:
    user_prompt = f"""SCHEMA CONTEXT:
{schema_context}

QUESTION: {question}

Output the JSON plan now."""

    raw_response = call_llm(PLANNER_SYSTEM_PROMPT, user_prompt, max_tokens=500)

    # Defensive parsing: strip accidental markdown fences if the model adds them
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        plan = json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback plan if the model returned something unparseable
        plan = {
            "metric": None,
            "operation": "unknown",
            "group_by": [],
            "filters": [],
            "top_n": None,
            "time_reference": None,
            "needs_target_join": False,
            "understanding": f"Could not parse plan. Raw model output: {raw_response[:200]}",
        }

    return plan


if __name__ == "__main__":
    from src.data_loader import get_connection
    from src.schema_context import build_schema_context

    con = get_connection()
    ctx = build_schema_context(con)
    plan = make_plan("Top 2 cities by profit", ctx)
    print(json.dumps(plan, indent=2))
