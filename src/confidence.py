"""
confidence.py
-------------
Computes a 0-1 confidence score for each answer.
"""


def _contains_null(result) -> bool:
    """Checks if any value in the result is None/null — catches cases
    like YoY growth with no prior year data, where the query runs fine
    but the actual numbers we need are missing."""
    if result is None:
        return True
    if isinstance(result, list):
        for row in result:
            if isinstance(row, dict) and any(v is None for v in row.values()):
                return True
    return False


def score_confidence(plan: dict, executed_without_retry: bool, result) -> float:
    score = 0.0

    if executed_without_retry:
        score += 0.4

    is_empty = result is None or (isinstance(result, list) and len(result) == 0)
    has_nulls = _contains_null(result)
    if not is_empty and not has_nulls:
        score += 0.3

    plan_resolved = bool(plan.get("metric")) and plan.get("operation") != "unknown"
    if plan_resolved:
        score += 0.3

    return round(score, 2)