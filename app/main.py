from __future__ import annotations

import csv
import io
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.display import build_display_snapshot
from app.models import Security
from app.parsing import parse_year_tokens
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
    include_cash: bool = Query(default=True, description="Include cash row in holdings weights"),
    cash_value: float | None = Query(default=None, description="Optional explicit cash amount"),
    dart_api_key: str | None = Query(
        default=None,
        description="Optional OpenDART key applied for this request",
    ),
):
    return _build_snapshot_body(
        ticker=ticker,
        market=market,
        corp_code=corp_code,
        name=name,
        years=years,
        include_cash=include_cash,
        cash_value=cash_value,
        dart_api_key=dart_api_key,
    )


@app.get("/api/snapshot/{ticker}/download")
def snapshot_download(
    ticker: str,
    market: str | None = Query(default=None),
    corp_code: str | None = Query(default=None),
    name: str | None = Query(default=None),
    years: str | None = Query(default=None, description="Comma-separated fiscal years"),
    include_cash: bool = Query(default=True),
    cash_value: float | None = Query(default=None),
    dart_api_key: str | None = Query(default=None),
    fmt: str = Query(default="csv", alias="format", pattern="^(csv|excel)$"),
):
    body = _build_snapshot_body(
        ticker=ticker,
        market=market,
        corp_code=corp_code,
        name=name,
        years=years,
        include_cash=include_cash,
        cash_value=cash_value,
        dart_api_key=dart_api_key,
    )
    csv_text = _snapshot_export_csv(body["display"])
    filename = f"{ticker.upper()}_snapshot_export.csv"
    media_type = "text/csv" if fmt == "csv" else "application/vnd.ms-excel"
    return Response(
        content=csv_text,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_snapshot_body(
    *,
    ticker: str,
    market: str | None,
    corp_code: str | None,
    name: str | None,
    years: str | None,
    include_cash: bool,
    cash_value: float | None,
    dart_api_key: str | None,
) -> dict:
    security = Security(ticker=ticker, market=market, corp_code=corp_code, name=name)
    try:
        fiscal_years = (
            parse_year_tokens(years)
            if years
            else pipeline.default_fiscal_years(5)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    snapshot = pipeline.build_valuation_snapshot(security, fiscal_years, dart_api_key=dart_api_key)
    body = snapshot.to_dict()
    body["display"] = build_display_snapshot(
        snapshot,
        fiscal_years,
        include_cash=include_cash,
        cash_value=cash_value,
    )
    return body


def _snapshot_export_csv(display: dict) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "section",
            "metric",
            "value",
            "unit",
            "source",
            "as_of",
            "delay_sec",
            "confidence",
        ]
    )

    meta = display.get("meta", {})
    source = meta.get("source")
    as_of = meta.get("as_of")
    delay_sec = meta.get("delay_sec")
    confidence = meta.get("confidence")

    fair = display.get("fair_value", {})
    writer.writerow(
        [
            "fair_value",
            "current_price",
            fair.get("current_price_formatted"),
            display.get("units", {}).get("per_share", {}).get("display", ""),
            source,
            as_of,
            delay_sec,
            confidence,
        ]
    )
    writer.writerow(
        [
            "fair_value",
            "fair_value",
            fair.get("fair_value_formatted"),
            display.get("units", {}).get("per_share", {}).get("display", ""),
            source,
            as_of,
            delay_sec,
            confidence,
        ]
    )
    writer.writerow(
        [
            "fair_value",
            "disparity_pct",
            fair.get("disparity_pct_formatted"),
            "%",
            source,
            as_of,
            delay_sec,
            confidence,
        ]
    )

    for row in display.get("holdings", []):
        writer.writerow(
            [
                "holdings",
                row.get("symbol"),
                row.get("weight_formatted"),
                "%",
                source,
                as_of,
                delay_sec,
                confidence,
            ]
        )
    for key, item in (display.get("risk", {}).get("metrics", {}) or {}).items():
        writer.writerow(
            [
                "risk",
                key,
                f"{item.get('value', 0):.2f}",
                "%",
                source,
                as_of,
                delay_sec,
                confidence,
            ]
        )
    return output.getvalue()


@app.get("/api/index/{index_code}")
def index_quote(index_code: str):
    return pipeline.get_index_quote(index_code).to_dict()


@app.post("/api/fallbacks/clear")
def clear_stale_fallbacks(ticker: str | None = Query(default=None)):
    return {"deleted": pipeline.clear_stale_fallback_values(ticker)}

