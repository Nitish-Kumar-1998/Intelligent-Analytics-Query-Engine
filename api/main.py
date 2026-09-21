"""
api/main.py
-----------
Small FastAPI app with one endpoint: POST /query.
Takes a single natural language question, runs it through the same
pipeline as run.py, and returns the same JSON shape.

Also serves the frontend folder as static files, so you can open
the whole app at http://localhost:8000

Usage:
    export ANTHROPIC_API_KEY=your_key_here
    uvicorn api.main:app --reload
"""
from dotenv import load_dotenv

load_dotenv()

import os
import sys

# allow importing from src/ when running from project root
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.data_loader import get_connection
from src.pipeline import answer_query

app = FastAPI(title="Intelligent Analytics Query Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# One shared DuckDB connection, loaded once at startup
_con = get_connection()


class QueryRequest(BaseModel):
    query: str


@app.post("/query")
def query_endpoint(request: QueryRequest):
    return answer_query(_con, request.query)


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve the frontend at the root URL
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
