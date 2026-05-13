from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.models import (
    AnnualFinancials,
    IndexQuote,
    Quote,
    Security,
    ValuationFields,
    is_us_ticker,
    utc_now_iso,
)


class SQLiteStore:
    def __init__(self, database_path: str | Path = "peaberry.db") -> None:
        self.database_path = Path(database_path)
        self.init_schema()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def init_schema(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                PRAGMA synchronous = NORMAL;

                CREATE TABLE IF NOT EXISTS securities (
                    ticker TEXT PRIMARY KEY,
                    market TEXT,
                    name TEXT,
                    corp_code TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS market_quotes (
                    ticker TEXT PRIMARY KEY,
                    price REAL,
                    currency TEXT,
                    source TEXT NOT NULL,
                    is_fallback INTEGER NOT NULL DEFAULT 0,
                    as_of TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS index_quotes (
                    index_code TEXT PRIMARY KEY,
                    value REAL,
                    source TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS annual_financials (
                    ticker TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    revenue REAL,
                    operating_income REAL,
                    net_income REAL,
                    assets REAL,
                    liabilities REAL,
                    equity REAL,
                    eps REAL,
                    bps REAL,
                    per REAL,
                    pbr REAL,
                    source TEXT NOT NULL,
                    is_fallback INTEGER NOT NULL DEFAULT 0,
                    is_estimate INTEGER NOT NULL DEFAULT 0,
                    as_of TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (ticker, year)
                );

                CREATE TABLE IF NOT EXISTS valuation_fields (
                    ticker TEXT PRIMARY KEY,
                    per REAL,
                    pbr REAL,
                    eps REAL,
                    bps REAL,
                    estimated_per REAL,
                    estimated_eps REAL,
                    source TEXT NOT NULL,
                    is_fallback INTEGER NOT NULL DEFAULT 0,
                    as_of TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS provider_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    provider TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_annual_ticker_year
                    ON annual_financials(ticker, year);
                CREATE INDEX IF NOT EXISTS idx_events_ticker_created
                    ON provider_events(ticker, created_at);
                """
            )
            self._ensure_column(connection, "annual_financials", "eps", "REAL")
            self._ensure_column(connection, "annual_financials", "bps", "REAL")
            self._ensure_column(connection, "annual_financials", "per", "REAL")
            self._ensure_column(connection, "annual_financials", "pbr", "REAL")
            self._ensure_column(
                connection,
                "annual_financials",
                "is_estimate",
                "INTEGER NOT NULL DEFAULT 0",
            )
            self._ensure_column(connection, "valuation_fields", "estimated_per", "REAL")
            self._ensure_column(connection, "valuation_fields", "estimated_eps", "REAL")

    def upsert_security(self, security: Security) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO securities (ticker, market, name, corp_code, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    market=excluded.market,
                    name=excluded.name,
                    corp_code=excluded.corp_code,
                    updated_at=excluded.updated_at
                """,
                (
                    security.normalized_ticker,
                    security.market,
                    security.name,
                    security.corp_code,
                    utc_now_iso(),
                ),
            )

    def get_security(self, ticker: str) -> Security | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT ticker, market, name, corp_code FROM securities WHERE ticker = ?",
                (ticker.strip().upper(),),
            ).fetchone()
        if row is None:
            return None
        return Security(
            ticker=row["ticker"],
            market=row["market"],
            name=row["name"],
            corp_code=row["corp_code"],
        )

    def save_quote(self, quote: Quote) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO market_quotes
                    (ticker, price, currency, source, is_fallback, as_of, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    price=excluded.price,
                    currency=excluded.currency,
                    source=excluded.source,
                    is_fallback=excluded.is_fallback,
                    as_of=excluded.as_of,
                    updated_at=excluded.updated_at
                """,
                (
                    quote.ticker,
                    quote.price,
                    quote.currency,
                    quote.source,
                    int(quote.is_fallback),
                    quote.as_of,
                    utc_now_iso(),
                ),
            )

    def save_index_quote(self, quote: IndexQuote) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO index_quotes (index_code, value, source, as_of, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(index_code) DO UPDATE SET
                    value=excluded.value,
                    source=excluded.source,
                    as_of=excluded.as_of,
                    updated_at=excluded.updated_at
                """,
                (quote.index_code, quote.value, quote.source, quote.as_of, utc_now_iso()),
            )

    def save_annual_financials(self, financials: AnnualFinancials) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO annual_financials
                    (
                        ticker, year, revenue, operating_income, net_income, assets,
                        liabilities, equity, eps, bps, per, pbr, source,
                        is_fallback, is_estimate, as_of, updated_at
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, year) DO UPDATE SET
                    revenue=excluded.revenue,
                    operating_income=excluded.operating_income,
                    net_income=excluded.net_income,
                    assets=excluded.assets,
                    liabilities=excluded.liabilities,
                    equity=excluded.equity,
                    eps=excluded.eps,
                    bps=excluded.bps,
                    per=excluded.per,
                    pbr=excluded.pbr,
                    source=excluded.source,
                    is_fallback=excluded.is_fallback,
                    is_estimate=excluded.is_estimate,
                    as_of=excluded.as_of,
                    updated_at=excluded.updated_at
                """,
                (
                    financials.ticker,
                    financials.year,
                    financials.revenue,
                    financials.operating_income,
                    financials.net_income,
                    financials.assets,
                    financials.liabilities,
                    financials.equity,
                    financials.eps,
                    financials.bps,
                    financials.per,
                    financials.pbr,
                    financials.source,
                    int(financials.is_fallback),
                    int(financials.is_estimate),
                    financials.as_of,
                    utc_now_iso(),
                ),
            )

    def save_valuation_fields(self, fields: ValuationFields) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO valuation_fields
                    (
                        ticker, per, pbr, eps, bps, estimated_per, estimated_eps,
                        source, is_fallback, as_of, updated_at
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    per=excluded.per,
                    pbr=excluded.pbr,
                    eps=excluded.eps,
                    bps=excluded.bps,
                    estimated_per=excluded.estimated_per,
                    estimated_eps=excluded.estimated_eps,
                    source=excluded.source,
                    is_fallback=excluded.is_fallback,
                    as_of=excluded.as_of,
                    updated_at=excluded.updated_at
                """,
                (
                    fields.ticker,
                    fields.per,
                    fields.pbr,
                    fields.eps,
                    fields.bps,
                    fields.estimated_per,
                    fields.estimated_eps,
                    fields.source,
                    int(fields.is_fallback),
                    fields.as_of,
                    utc_now_iso(),
                ),
            )

    def record_event(
        self,
        provider: str,
        event_type: str,
        message: str,
        ticker: str | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO provider_events
                    (ticker, provider, event_type, message, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (ticker, provider, event_type, message, utc_now_iso()),
            )

    def load_quote(self, ticker: str) -> Quote | None:
        row = self._fetch_one("SELECT * FROM market_quotes WHERE ticker = ?", ticker)
        if row is None:
            return None
        return Quote(
            ticker=row["ticker"],
            price=row["price"],
            currency=row["currency"],
            source=row["source"],
            is_fallback=bool(row["is_fallback"]),
            as_of=row["as_of"],
        )

    def load_annual_financials(self, ticker: str, years: list[int]) -> list[AnnualFinancials]:
        placeholders = ",".join("?" for _ in years)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM annual_financials
                WHERE ticker = ? AND year IN ({placeholders})
                ORDER BY year DESC
                """,
                (ticker.strip().upper(), *years),
            ).fetchall()
        return [
            AnnualFinancials(
                ticker=row["ticker"],
                year=row["year"],
                revenue=row["revenue"],
                operating_income=row["operating_income"],
                net_income=row["net_income"],
                assets=row["assets"],
                liabilities=row["liabilities"],
                equity=row["equity"],
                eps=row["eps"],
                bps=row["bps"],
                per=row["per"],
                pbr=row["pbr"],
                source=row["source"],
                is_fallback=bool(row["is_fallback"]),
                is_estimate=bool(row["is_estimate"]),
                as_of=row["as_of"],
            )
            for row in rows
        ]

    def load_valuation_fields(self, ticker: str) -> ValuationFields | None:
        row = self._fetch_one("SELECT * FROM valuation_fields WHERE ticker = ?", ticker)
        if row is None:
            return None
        return ValuationFields(
            ticker=row["ticker"],
            per=row["per"],
            pbr=row["pbr"],
            eps=row["eps"],
            bps=row["bps"],
            estimated_per=row["estimated_per"],
            estimated_eps=row["estimated_eps"],
            source=row["source"],
            is_fallback=bool(row["is_fallback"]),
            as_of=row["as_of"],
        )

    def clear_stale_fallback_values(self, ticker: str | None = None) -> int:
        """Remove fallback rows that can no longer be trusted.

        Yahoo-derived rows for non-US securities are considered stale because Yahoo is
        only allowed as a US-stock fallback in this pipeline.
        """

        deleted = 0
        market_by_ticker = self._security_markets()
        with self.connect() as connection:
            for table, key_columns in (
                ("market_quotes", ("ticker",)),
                ("valuation_fields", ("ticker",)),
                ("annual_financials", ("ticker", "year")),
            ):
                rows = connection.execute(
                    f"SELECT * FROM {table} WHERE is_fallback = 1"
                    + (" AND ticker = ?" if ticker else ""),
                    ((ticker.strip().upper(),) if ticker else ()),
                ).fetchall()
                for row in rows:
                    symbol = row["ticker"]
                    market = market_by_ticker.get(symbol)
                    if is_us_ticker(symbol, market):
                        continue
                    where_clause = " AND ".join(f"{column} = ?" for column in key_columns)
                    values = tuple(row[column] for column in key_columns)
                    cursor = connection.execute(
                        f"DELETE FROM {table} WHERE {where_clause}",
                        values,
                    )
                    deleted += cursor.rowcount
        return deleted

    def _security_markets(self) -> dict[str, str | None]:
        with self.connect() as connection:
            rows = connection.execute("SELECT ticker, market FROM securities").fetchall()
        return {row["ticker"]: row["market"] for row in rows}

    def _fetch_one(self, query: str, ticker: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute(query, (ticker.strip().upper(),)).fetchone()

    def dump_table(self, table: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(f"SELECT * FROM {table}").fetchall()
        return [dict(row) for row in rows]

    def _ensure_column(
        self,
        connection: sqlite3.Connection,
        table: str,
        column: str,
        ddl: str,
    ) -> None:
        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column in columns:
            return
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

