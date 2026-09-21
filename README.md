# Intelligent Analytics Query Engine

An AI-powered analytics engine that converts natural language business
questions into executable SQL, runs them against a real dataset, and
returns results with a calibrated confidence score and a plain-English
explanation of what was understood and how the answer was computed.

Built for a take-home assignment with a 4–8 hour time budget. Demonstrates:
- Two-stage LLM reasoning (plan → generate SQL) instead of one-shot generation
- Schema-grounded prompting to resolve business terms into real formulas
- Self-correcting execution (one retry on SQL errors)
- A confidence score derived from actual execution signals, not LLM self-report
- Deliberate testing against unseen/impossible queries to confirm graceful failure instead of hallucination

**Live demo:** [add your Render URL here]

---

## Setup

```bash
git clone <your-repo-url>
cd Intelligent-Analytics-Query-Engine
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:
```
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
```

Get a free Gemini key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
`GROQ_API_KEY` is optional — only needed if you switch `LLM_PROVIDER` to `groq` as a fallback (free key at [console.groq.com/keys](https://console.groq.com/keys)).

## Usage

**Batch mode** — runs every question in `dataset/nl_queries.json`, writes `outputs/results.json`:
```bash
python run.py
```

**Edge-case test set** — runs 3 self-authored queries designed to probe unseen/impossible questions:
```bash
python run.py edge_case_queries.json
```

**Web app** — API + frontend together:
```bash
uvicorn api.main:app --reload
```
Open `http://localhost:8000`.

**Docker:**
```bash
docker build -t analytics-engine .
docker run -p 8000:8000 --env-file .env analytics-engine
```

---

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

`run.py` and `api/main.py` both call the same `pipeline.answer_query()` function — one source of truth for the logic regardless of entrypoint.

### Repo structure
```
Intelligent-Analytics-Query-Engine/
├── dataset/
│   ├── sales_data.csv
│   ├── targets.csv
│   ├── data_dictionary.json
│   ├── nl_queries.json              # the 8 required test queries
│   └── edge_case_queries.json       # self-authored unseen-query tests
├── src/
│   ├── data_loader.py               # loads CSVs into DuckDB
│   ├── schema_context.py            # expands metric formulas + synonyms for the LLM
│   ├── llm_client.py                # provider-agnostic LLM wrapper (gemini / groq)
│   ├── planner.py                   # LLM call 1: NL question → structured plan
│   ├── sql_generator.py             # LLM call 2: plan → SQL, plus self-correction retry
│   ├── executor.py                  # runs SQL against DuckDB, catches errors
│   ├── confidence.py                # composite 0–1 confidence score
│   └── pipeline.py                  # orchestrates the full flow per question
├── api/
│   └── main.py                      # FastAPI: /query endpoint, serves the frontend
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
├── outputs/
│   └── results.json
├── Dockerfile
├── requirements.txt
└── run.py
```

---

## Approach

**1. Schema grounding** (`src/schema_context.py`)
`data_dictionary.json` defines metrics like `revenue` as formulas
(`quantity * unit_price * (1 - discount)`), not real columns. This module
expands those formulas and folds in synonyms (`sales` → `revenue`,
`earnings` → `profit`) into one text block given to the LLM on every call,
so it never has to guess at business terms or invent a column that doesn't
exist.

**2. Plan, then generate** (`src/planner.py` → `src/sql_generator.py`)
Two separate LLM calls instead of one. The first turns the question into a
structured plan (metric, grouping, filters, operation type). The second
turns that plan into SQL. Splitting these improves accuracy on harder
queries (top-N per group, contribution %, target comparisons) because the
model isn't doing semantic understanding and SQL syntax generation in the
same pass. The plan doubles as the "what the system understood" content
in the final explanation.

**3. Execution** (`src/executor.py`)
SQL runs against DuckDB, which reads the CSVs directly as real SQL tables.
SQL was chosen over generating raw Pandas code because it's easier to
validate before running (a `SELECT`-only check plus a keyword blocklist is
enough to make it safe), and the model generates correct SQL more reliably
than chained Pandas operations for grouped/nested logic.

**4. Self-correction** (`src/pipeline.py`)
If the generated SQL fails to execute, the error message is fed back to
the model once, asking it to fix the query. Capped at one retry so a
broken query can't loop forever.

**5. Confidence score** (`src/confidence.py`)
A composite of concrete signals rather than an LLM self-report (which
tends to be uncalibrated):
- executed without needing the retry (0.4)
- result came back non-empty **and contains no null values** (0.3)
- the plan fully resolved to a known metric/operation (0.3)

The null-check was added after testing surfaced a real bug: the original
scorer only checked for empty results, so a query that executed
successfully but returned `null` inside a non-empty row (e.g. YoY growth
with no prior year to compare against) was incorrectly scoring 1.0. Fixed
to correctly score 0.7 in that case, with the explanation text updated to
state why.

**6. Frontend** (`frontend/`)
A single HTML/CSS/JS page, no build step, served by the same FastAPI app.
Type a question, see the generated SQL, result, confidence bar, and
explanation.

---

## Hallucination mitigation

No LLM-based system can guarantee zero hallucination, so this system
layers three defenses instead of relying on the model alone:

1. **Schema grounding** — every prompt is given the real column names,
   the revenue/profit formulas, and sample values, so the model has
   minimal room to invent fields.
2. **Low temperature (0.0)** — maximally deterministic output.
3. **Execution as ground truth** — DuckDB itself rejects any SQL
   referencing a column or table that doesn't exist. A hallucinated field
   fails to execute, triggers the self-correction retry, and if it still
   fails, returns a correctly low confidence score rather than a
   fabricated answer.

**Known limitation:** execution success only proves the SQL is
syntactically valid against the real schema — it doesn't independently
verify the SQL is *semantically* correct (e.g. a subtly wrong JOIN or
filter that still runs without error). Closing this would need a second
LLM pass comparing the generated SQL back against the original plan,
which was out of scope for this time budget.

---

## Edge-case testing (beyond the given 8 queries)

`dataset/edge_case_queries.json` contains 3 self-authored queries testing
the "must work for unseen queries" requirement, using conditions that
don't exist in the sample dataset:

| Query | Result |
|---|---|
| "What was profit in 2022?" | Ran correctly, returned `null` (no 2022 data exists), confidence dropped to 0.7, explanation states why |
| "Show me revenue by planet" | Correctly recognized "planet" isn't a real dimension, returned an empty result instead of fabricating a column |
| "Compare Mars region to Venus region" | Correctly recognized these aren't real region values, returned an empty result instead of inventing data |

Run with:
```bash
python run.py edge_case_queries.json
```

---

## Deployment

Deployed via Docker on Render, auto-deploying on every push to `main`.

- `Dockerfile` builds a slim Python 3.11 image, installs dependencies, and
  runs the FastAPI app with `uvicorn`.
- Render watches the connected GitHub repo and rebuilds/redeploys
  automatically on every push — no CI config needed beyond the Dockerfile
  itself.
- Environment variables (`LLM_PROVIDER`, `GEMINI_API_KEY`) are set in
  Render's dashboard, never committed to the repo (`.env` is git-ignored).

---

## If I had more time

- A second LLM validation pass comparing generated SQL back against the
  plan, to catch semantically-wrong-but-syntactically-valid queries
- Embedding-based fuzzy matching for entity resolution (e.g. "US" → "USA")
  instead of relying on the LLM alone against the distinct-values list
- A feedback loop using `feedback_log.csv` as a small retrieval corpus of
  past corrections, injected as few-shot examples (mini-RAG over
  corrections)
- Caching schema context per session instead of rebuilding it every call
- More granular confidence sub-scores per plan field (e.g. flag when a
  filter value doesn't exactly match a known dimension value)

## Tech stack

DuckDB · Gemini API (`google-genai`) · FastAPI · Docker · vanilla HTML/CSS/JS
