"""
run.py
------
Batch mode. Reads dataset/nl_queries.json, runs every question through
the pipeline, and writes outputs/results.json in the exact format
the assignment asks for.

Usage:
    export ANTHROPIC_API_KEY=your_key_here
    python run.py
"""
from dotenv import load_dotenv
load_dotenv()

import json
import os

from src.data_loader import get_connection

DATASET_DIR = os.path.join(os.path.dirname(__file__), "dataset")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "outputs", "results.json")


def main():
    from src.pipeline import answer_query
    import sys

    filename = sys.argv[1] if len(sys.argv) > 1 else "nl_queries.json"
    output_name = "results.json" if filename == "nl_queries.json" else f"{filename.replace('.json', '')}_results.json"

    with open(os.path.join(DATASET_DIR, filename), "r") as f:
        queries = json.load(f)

    con = get_connection()
    results = []

    for item in queries:
        question = item["query"]
        print(f"Running: {question}")
        answer = answer_query(con, question)
        results.append(answer)
        print(json.dumps(answer, indent=2, default=str))
        print("-" * 60)

    output_path = os.path.join(os.path.dirname(__file__), "outputs", output_name)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nDone. Results written to {output_path}")

if __name__ == "__main__":
    main()
