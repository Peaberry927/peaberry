"""Yahoo Finance chart adapter for market price references."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable, Sequence

from peaberry.domain.fundamentals import (
    Currency,
    DataSourceRef,
    FinancialStatement,
    MarketReference,
    SourceKind,
)
from peaberry.domain.market import Symbol
from peaberry.fundamentals.http import JsonHttpClient, UrlLibJsonHttpClient
from peaberry.fundamentals.periods import fiscal_period_end


class YahooChartMarketDataSource:
    """Fetch fiscal-period close prices from Yahoo Finance chart JSON."""

    name = "Yahoo Finance Chart"

    def __init__(
        self,
        symbol_to_ticker: dict[Symbol, str],
        symbol_to_currency: dict[Symbol, Currency] | None = None,
        http_client: JsonHttpClient | None = None,
    ) -> None:
        self.symbol_to_ticker = dict(symbol_to_ticker)
        self.symbol_to_currency = dict(symbol_to_currency or {})
        self.http_client = http_client or UrlLibJsonHttpClient()
        self._cache: dict[tuple[str, str | None], dict[str, Any]] = {}

    def statements(
        self,
        symbol: Symbol,
        fiscal_periods: Sequence[str],
    ) -> Iterable[FinancialStatement]:
        return ()

    def market_reference(
        self,
        symbol: Symbol,
        fiscal_period: str | None = None,
    ) -> MarketReference | None:
        ticker = self.symbol_to_ticker.get(symbol)
        if ticker is None:
            return None

        payload = self._chart_payload(ticker, fiscal_period)
        result = self._chart_result(payload)
        if result is None:
            return None

        selected = self._select_close(result, fiscal_period)
        if selected is None:
            return None
        selected_at, close_price = selected

        currency = self.symbol_to_currency.get(symbol) or Currency(
            str(result.get("meta", {}).get("currency", "UNKNOWN"))
        )
        return MarketReference(
            symbol=symbol,
            currency=currency,
            fiscal_period=fiscal_period,
            as_of=selected_at,
            source=DataSourceRef(
                name=self.name,
                kind=SourceKind.MARKET_DATA,
                as_of=selected_at,
                confidence=Decimal("0.9"),
            ),
            price=close_price,
        )

    def _chart_payload(self, ticker: str, fiscal_period: str | None) -> dict[str, Any]:
        cache_key = (ticker, fiscal_period)
        if cache_key in self._cache:
            return self._cache[cache_key]

        if fiscal_period is None:
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=10)
        else:
            end = min(fiscal_period_end(fiscal_period), datetime.now(timezone.utc))
            start = end - timedelta(days=10)
        period1 = int(start.timestamp())
        period2 = int((end + timedelta(days=2)).timestamp())
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            f"?period1={period1}&period2={period2}&interval=1d"
        )
        self._cache[cache_key] = self.http_client.get_json(url)
        return self._cache[cache_key]

    def _chart_result(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        chart = payload.get("chart", {})
        if chart.get("error"):
            raise ValueError(f"Yahoo chart request failed: {chart['error']}")
        results = chart.get("result") or []
        if not results:
            return None
        result = results[0]
        return result if isinstance(result, dict) else None

    def _select_close(
        self,
        result: dict[str, Any],
        fiscal_period: str | None,
    ) -> tuple[datetime, Decimal] | None:
        timestamps = result.get("timestamp") or []
        quote = (result.get("indicators", {}).get("quote") or [{}])[0]
        closes = quote.get("close") or []
        if not timestamps or not closes:
            return None

        target = (
            min(fiscal_period_end(fiscal_period), datetime.now(timezone.utc))
            if fiscal_period is not None
            else datetime.now(timezone.utc)
        )
        candidates: list[tuple[datetime, Decimal]] = []
        for timestamp, close in zip(timestamps, closes):
            if close is None:
                continue
            observed_at = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
            if observed_at <= target:
                candidates.append((observed_at, Decimal(str(close))))
        if not candidates:
            return None
        return max(candidates, key=lambda item: item[0])
