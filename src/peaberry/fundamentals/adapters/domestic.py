"""Domestic market price adapters and fallback composition."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Sequence

from peaberry.domain.fundamentals import (
    Currency,
    DataSourceRef,
    FinancialStatement,
    MarketReference,
    SourceKind,
)
from peaberry.domain.market import Symbol
from peaberry.fundamentals.cache import TtlCache
from peaberry.fundamentals.http import JsonHttpClient, UrlLibJsonHttpClient
from peaberry.fundamentals.periods import fiscal_period_end
from peaberry.fundamentals.sources import FundamentalsSource


class FallbackMarketDataSource:
    """Try market data providers in priority order and record provider errors."""

    def __init__(self, name: str, sources: Sequence[FundamentalsSource]) -> None:
        if not sources:
            raise ValueError("at least one market data source is required")
        self.name = name
        self.sources = tuple(sources)
        self._source_errors: list[tuple[str, str]] = []

    @property
    def source_errors(self) -> tuple[tuple[str, str], ...]:
        return tuple(self._source_errors)

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
        for source in self.sources:
            try:
                reference = source.market_reference(symbol, fiscal_period)
            except Exception as exc:
                self._source_errors.append((source.name, str(exc)))
                continue
            if reference is not None:
                return reference
        return None


class NaverChartMarketDataSource:
    """Fetch Korean daily close prices from Naver chart JSON."""

    name = "Naver Finance Chart"

    def __init__(
        self,
        symbol_to_code: dict[Symbol, str],
        http_client: JsonHttpClient | None = None,
        cache_ttl: timedelta = timedelta(minutes=15),
    ) -> None:
        self.symbol_to_code = dict(symbol_to_code)
        self.http_client = http_client or UrlLibJsonHttpClient()
        self._cache: TtlCache[dict[str, Any]] = TtlCache(cache_ttl)

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
        code = self.symbol_to_code.get(symbol)
        if code is None:
            return None
        payload = self._payload(code, fiscal_period)
        selected = self._select_close(payload, fiscal_period)
        if selected is None:
            return None
        selected_at, price = selected
        return MarketReference(
            symbol=symbol,
            currency=Currency("KRW"),
            fiscal_period=fiscal_period,
            as_of=selected_at,
            source=DataSourceRef(
                name=self.name,
                kind=SourceKind.MARKET_DATA,
                as_of=selected_at,
                confidence=Decimal("0.85"),
            ),
            price=price,
        )

    def _payload(self, code: str, fiscal_period: str | None) -> dict[str, Any]:
        cache_key = (code, fiscal_period)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        target = self._target_datetime(fiscal_period)
        start = target - timedelta(days=10)
        url = (
            f"https://api.stock.naver.com/chart/domestic/item/{code}/day"
            f"?startDateTime={start:%Y%m%d}0000&endDateTime={target:%Y%m%d}2359"
        )
        return self._cache.set(cache_key, self.http_client.get_json(url))

    def _select_close(
        self,
        payload: dict[str, Any],
        fiscal_period: str | None,
    ) -> tuple[datetime, Decimal] | None:
        target = self._target_datetime(fiscal_period)
        rows = payload.get("data") or payload.get("priceInfos") or payload.get("items") or []
        candidates: list[tuple[datetime, Decimal]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            observed_at = self._parse_date(row.get("localDate") or row.get("date"))
            price = self._parse_decimal(
                row.get("closePrice") or row.get("close") or row.get("endPrice")
            )
            if observed_at is not None and price is not None and observed_at <= target:
                candidates.append((observed_at, price))
        if not candidates:
            return None
        return max(candidates, key=lambda item: item[0])

    def _target_datetime(self, fiscal_period: str | None) -> datetime:
        if fiscal_period is None:
            return datetime.now(timezone.utc)
        return min(fiscal_period_end(fiscal_period), datetime.now(timezone.utc))

    def _parse_date(self, value: Any) -> datetime | None:
        if value is None:
            return None
        raw = str(value).replace("-", "")
        if len(raw) < 8:
            return None
        return datetime(
            int(raw[:4]),
            int(raw[4:6]),
            int(raw[6:8]),
            tzinfo=timezone.utc,
        )

    def _parse_decimal(self, value: Any) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value).replace(",", ""))
        except InvalidOperation:
            return None


class KrxDailyMarketDataSource:
    """Fetch Korean daily close and market cap from KRX JSON endpoints."""

    name = "KRX Daily Trading"

    def __init__(
        self,
        symbol_to_code: dict[Symbol, str],
        http_client: JsonHttpClient | None = None,
        endpoint: str = "https://data-api.krx.co.kr/svc/apis/sto/stk_bydd_trd",
        cache_ttl: timedelta = timedelta(minutes=15),
    ) -> None:
        self.symbol_to_code = dict(symbol_to_code)
        self.http_client = http_client or UrlLibJsonHttpClient()
        self.endpoint = endpoint
        self._cache: TtlCache[dict[str, Any]] = TtlCache(cache_ttl)

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
        code = self.symbol_to_code.get(symbol)
        if code is None:
            return None
        payload = self._payload(code, fiscal_period)
        selected = self._select_reference(payload, fiscal_period)
        if selected is None:
            return None
        selected_at, price, market_cap = selected
        return MarketReference(
            symbol=symbol,
            currency=Currency("KRW"),
            fiscal_period=fiscal_period,
            as_of=selected_at,
            source=DataSourceRef(
                name=self.name,
                kind=SourceKind.MARKET_DATA,
                as_of=selected_at,
                confidence=Decimal("0.9"),
            ),
            price=price,
            market_cap=market_cap,
        )

    def _payload(self, code: str, fiscal_period: str | None) -> dict[str, Any]:
        cache_key = (code, fiscal_period)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        target = self._target_datetime(fiscal_period)
        url = f"{self.endpoint}?basDd={target:%Y%m%d}&likeSrtnCd={code}"
        return self._cache.set(cache_key, self.http_client.get_json(url))

    def _select_reference(
        self,
        payload: dict[str, Any],
        fiscal_period: str | None,
    ) -> tuple[datetime, Decimal | None, Decimal | None] | None:
        rows = payload.get("OutBlock_1") or payload.get("output") or payload.get("data") or []
        target = self._target_datetime(fiscal_period)
        candidates: list[tuple[datetime, Decimal | None, Decimal | None]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            observed_at = self._parse_date(row.get("BAS_DD") or row.get("basDd"))
            price = self._parse_decimal(row.get("CLSPRC") or row.get("closePrice"))
            market_cap = self._parse_decimal(row.get("MKTCAP") or row.get("marketCap"))
            if observed_at is not None and observed_at <= target and (price or market_cap):
                candidates.append((observed_at, price, market_cap))
        if not candidates:
            return None
        return max(candidates, key=lambda item: item[0])

    def _target_datetime(self, fiscal_period: str | None) -> datetime:
        if fiscal_period is None:
            return datetime.now(timezone.utc)
        return min(fiscal_period_end(fiscal_period), datetime.now(timezone.utc))

    def _parse_date(self, value: Any) -> datetime | None:
        if value is None:
            return None
        raw = str(value).replace("-", "")
        if len(raw) < 8:
            return None
        return datetime(
            int(raw[:4]),
            int(raw[4:6]),
            int(raw[6:8]),
            tzinfo=timezone.utc,
        )

    def _parse_decimal(self, value: Any) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value).replace(",", ""))
        except InvalidOperation:
            return None
