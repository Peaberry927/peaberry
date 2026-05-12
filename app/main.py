from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.display import build_display_snapshot
from app.models import Security
from app.pipeline import QuantDataPipeline
from app.storage import SQLiteStore


DATABASE_PATH = os.getenv("PEABERRY_DATABASE_PATH", "peaberry.db")
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Peaberry Quant Data API")
pipeline = QuantDataPipeline(store=SQLiteStore(DATABASE_PATH))

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/snapshot/{ticker}")
def valuation_snapshot(
    ticker: str,
    market: str | None = Query(default=None),
    corp_code: str | None = Query(default=None),
    name: str | None = Query(default=None),
    years: str | None = Query(default=None, description="Comma-separated fiscal years"),
):
    security = Security(ticker=ticker, market=market, corp_code=corp_code, name=name)
    fiscal_years = (
        [int(item.strip()) for item in years.split(",") if item.strip()]
        if years
        else pipeline.default_fiscal_years(5)
    )
    snapshot = pipeline.build_valuation_snapshot(security, fiscal_years)
    body = snapshot.to_dict()
    body["display"] = build_display_snapshot(snapshot, fiscal_years)
    return body


@app.get("/api/index/{index_code}")
def index_quote(index_code: str):
    return pipeline.get_index_quote(index_code).to_dict()


@app.post("/api/fallbacks/clear")
def clear_stale_fallbacks(ticker: str | None = Query(default=None)):
    return {"deleted": pipeline.clear_stale_fallback_values(ticker)}

