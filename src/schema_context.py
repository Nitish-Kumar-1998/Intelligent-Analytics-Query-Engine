"""
schema_context.py
------------------
Reads data_dictionary.json and the real database tables, and builds one
text block that gets injected into every LLM prompt. This is what lets
the LLM map business words ("sales", "earnings", "aov") to actual SQL.

The key trick: "revenue" is NOT a real column in sales_data.csv.
It's defined in data_dictionary.json as a formula:
    revenue = quantity * unit_price * (1 - discount)

So we expand every metric into a ready-to-use SQL expression here,
instead of hoping the LLM reconstructs the formula on its own.
"""

import json
import os

from src.data_loader import get_table_columns, get_sample_rows, get_distinct_values

DICTIONARY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "dataset", "data_dictionary.json"
)


def load_dictionary():
    with open(DICTIONARY_PATH, "r") as f:
        return json.load(f)


def build_metric_sql_map(dictionary):
    """
    Turns the 'metrics' block into real SQL expressions.
    Some metrics reference other metrics (e.g. avg_order_value = revenue / orders),
    so we substitute those in too (one pass is enough for this schema depth).
    """
    metrics = dictionary.get("metrics", {})
    sql_map = {}

    # First pass: copy raw formulas
    for name, formula in metrics.items():
        sql_map[name] = formula

    # Second pass: substitute any metric name used inside another metric's formula
    for name, formula in sql_map.items():
        for other_name, other_formula in metrics.items():
            if other_name != name and other_name in formula:
                formula = formula.replace(other_name, f"({other_formula})")
        sql_map[name] = formula

    return sql_map


def build_schema_context(con):
    """
    Builds the full text block injected into LLM prompts.
    Includes:
      - real table columns
      - metric name -> SQL formula mapping (with synonyms folded in)
      - dimension columns available for grouping/filtering
      - sample rows and distinct categorical values for grounding
      - time mapping hints
    """
    dictionary = load_dictionary()
    metric_sql_map = build_metric_sql_map(dictionary)
    synonyms = dictionary.get("synonyms", {})
    dimensions = dictionary.get("dimensions", [])
    time_mappings = dictionary.get("time_mappings", {})

    sales_columns = get_table_columns(con, "sales")
    targets_columns = get_table_columns(con, "targets")
    sample_rows = get_sample_rows(con, "sales", limit=2)

    # Ground categorical dimensions with their real distinct values
    dimension_values = {}
    for dim in dimensions:
        if dim in sales_columns and dim != "order_date":
            dimension_values[dim] = get_distinct_values(con, "sales", dim, limit=15)

    lines = []
    lines.append("=== TABLE: sales ===")
    lines.append(f"Columns: {', '.join(sales_columns)}")
    lines.append(f"Sample rows: {json.dumps(sample_rows, default=str)}")
    lines.append("")
    lines.append("=== TABLE: targets ===")
    lines.append(f"Columns: {', '.join(targets_columns)}")
    lines.append("Join key: targets.region = sales.region, targets.month = strftime(sales.order_date, '%Y-%m')")
    lines.append("")
    lines.append("=== METRICS (business term -> real SQL expression) ===")
    for name, formula in metric_sql_map.items():
        lines.append(f"- {name} = {formula}")
    lines.append("")
    lines.append("=== SYNONYMS (map these words to the metric above) ===")
    for word, target in synonyms.items():
        lines.append(f"- '{word}' means '{target}'")
    lines.append("")
    lines.append("=== DIMENSIONS available for GROUP BY / WHERE ===")
    for dim, values in dimension_values.items():
        lines.append(f"- {dim}: e.g. {values}")
    lines.append("")
    lines.append("=== TIME PHRASES ===")
    for phrase, meaning in time_mappings.items():
        lines.append(f"- '{phrase}' means {meaning}")
    lines.append("")
    lines.append(
        "IMPORTANT: 'revenue', 'profit', 'orders', 'avg_order_value' are NOT real "
        "columns except 'profit'. Always substitute the SQL expression above "
        "wherever these words or their synonyms are used."
    )

    return "\n".join(lines)


if __name__ == "__main__":
    from src.data_loader import get_connection

    con = get_connection()
    print(build_schema_context(con))
