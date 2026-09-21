# Intelligent Analytics Query Engine

Converts natural language questions about sales data into executable SQL,
runs them, and returns results with a confidence score and explanation.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here
```

## Usage

**Batch mode** — runs every question in `dataset/nl_queries.json`, writes `outputs/results.json`:
```bash
python run.py
```

**Web app** — API + frontend together:
```bash
uvicorn api.main:app --reload
```
Then open `http://localhost:8000` in a browser.

## Approach

1. **Schema grounding** (`src/schema_context.py`) — `data_dictionary.json` defines
   metrics like `revenue` as formulas (`quantity * unit_price * (1 - discount)`),
   not real columns. This module expands those formulas and folds in synonyms
   (`sales` → `revenue`, `earnings` → `profit`) into one text block given to
   the LLM on every call, so it never has to guess at business terms.

2. **Plan, then generate** (`src/planner.py` → `src/sql_generator.py`) —
   two separate LLM calls instead of one. The first turns the question into
   a structured plan (metric, grouping, filters, operation type). The second
   turns that plan into SQL. Splitting these noticeably improves accuracy on
   harder queries (top-N per group, contribution %, target comparisons)
   because the model isn't doing semantic understanding and SQL syntax at
   the same time. The plan is also reused as the explanation's "what the
   system understood" content — no extra work.

3. **Execution** (`src/executor.py`) — SQL runs against DuckDB, which reads
   the CSVs directly as SQL tables. SQL was chosen over generating raw Pandas
   code because it's easier to validate before running (a `SELECT`-only check
   is enough to make it safe) and the model generates correct SQL more
   reliably than chained Pandas operations for grouped/nested logic.

4. **Self-correction** (`src/pipeline.py`) — if the generated SQL fails to
   execute, the error message is fed back to the model once, asking it to
   fix the query. Capped at one retry so a broken query can't loop forever.

5. **Confidence score** (`src/confidence.py`) — a composite of three signals
   rather than an LLM self-report (which tends to be uncalibrated):
   - executed without needing the retry (0.4)
   - result came back non-empty (0.3)
   - the plan fully resolved to a known metric/operation (0.3)

6. **Frontend** (`frontend/`) — a single HTML/CSS/JS page, no build step,
   served by the same FastAPI app. Type a question, see the SQL, result,
   confidence bar, and explanation.

## Architecture

```
Browser (frontend/) ──POST /query──▶ FastAPI (api/main.py)
                                            │
                                            ▼
                                     src/pipeline.py
                                            │
        ┌───────────────┬───────────────┬──┴────────────┬────────────────┐
        ▼               ▼               ▼               ▼                ▼
  schema_context   planner (LLM)  sql_generator    executor        confidence
   (dictionary)      call #1      (LLM) call #2    (DuckDB)          scorer
```

`run.py` calls the exact same `pipeline.answer_query()` function for batch
mode, so there's one source of truth for the logic regardless of entrypoint.

## Known limitation / edge case handled deliberately

The "YoY growth in revenue" query has no prior-year data in this sample
dataset — there's only 2024 data. Rather than fabricate a number, the
pipeline still attempts the query, gets an empty/partial result, and the
confidence scorer reflects that with a low score. This is intentional:
a system that fails honestly on missing data is more trustworthy than
one that silently makes something up.

## If I had more time

- Embedding-based fuzzy matching for entity resolution (e.g. "US" → "USA")
  instead of relying on the LLM alone to see the distinct-values list
- Feedback loop using `feedback_log.csv` as a small retrieval corpus of
  past corrections, injected as few-shot examples
- Caching schema context per session instead of rebuilding it every call
- More granular confidence sub-scores per plan field (e.g. flag when
  a filter value doesn't exactly match a known dimension value)
