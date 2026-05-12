"""OpenDART financial statement acquisition adapter."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Sequence
from urllib.parse import urlencode

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
from peaberry.fundamentals.periods import fiscal_year


class OpenDartFundamentalsSource:
    """Fetch Korean issuer annual facts from OpenDART."""

    name = "OpenDART"

    _FIELD_ALIASES = {
        "revenue": (
            "ifrs-full_Revenue",
            "매출액",
            "영업수익",
            "수익(매출액)",
        ),
        "operating_income": (
            "dart_OperatingIncomeLoss",
            "영업이익",
            "영업손실",
        ),
        "net_income": (
            "ifrs-full_ProfitLoss",
            "당기순이익",
            "당기순손익",
            "연결당기순이익",
        ),
        "shareholders_equity": (
            "ifrs-full_Equity",
            "자본총계",
            "지배기업 소유주지분",
        ),
    }

    def __init__(
        self,
        api_key: str,
        symbol_to_corp_code: dict[Symbol, str],
        http_client: JsonHttpClient | None = None,
        fs_div: str = "CFS",
        cache_ttl: timedelta = timedelta(days=1),
    ) -> None:
        if not api_key:
            raise ValueError("OpenDART api_key is required")
        self.api_key = api_key
        self.symbol_to_corp_code = dict(symbol_to_corp_code)
        self.http_client = http_client or UrlLibJsonHttpClient()
        self.fs_div = fs_div
        self._cache: TtlCache[dict[str, Any]] = TtlCache(cache_ttl)

    def statements(
        self,
        symbol: Symbol,
        fiscal_periods: Sequence[str],
    ) -> Iterable[FinancialStatement]:
        corp_code = self.symbol_to_corp_code.get(symbol)
        if corp_code is None:
            return ()

        statements: list[FinancialStatement] = []
        for period in fiscal_periods:
            year = fiscal_year(period)
            payload = self._statement_payload(corp_code, year)
            rows = payload.get("list", [])
            if not isinstance(rows, list):
                continue

            values = {
                field_name: self._extract_field(rows, aliases)
                for field_name, aliases in self._FIELD_ALIASES.items()
            }
            if not any(value is not None for value in values.values()):
                continue

            source = DataSourceRef(
                name=self.name,
                kind=SourceKind.REGULATORY_FILING,
                as_of=datetime(year + 1, 4, 1, tzinfo=timezone.utc),
                confidence=Decimal("0.95"),
            )
            statements.append(
                FinancialStatement(
                    symbol=symbol,
                    fiscal_period=period,
                    currency=Currency("KRW"),
                    source=source,
                    value_sources=tuple(
                        (field_name, source)
                        for field_name in values
                        if values[field_name] is not None
                    ),
                    **values,
                )
            )
        return tuple(statements)

    def market_reference(
        self,
        symbol: Symbol,
        fiscal_period: str | None = None,
    ) -> MarketReference | None:
        return None

    def _statement_payload(self, corp_code: str, year: int) -> dict[str, Any]:
        cache_key = (corp_code, year)
        cached = self._cache.get(cache_key)
        if cached is None:
            query = urlencode(
                {
                    "crtfc_key": self.api_key,
                    "corp_code": corp_code,
                    "bsns_year": str(year),
                    "reprt_code": "11011",
                    "fs_div": self.fs_div,
                }
            )
            url = f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json?{query}"
            payload = self.http_client.get_json(url)
            if payload.get("status") not in (None, "000"):
                raise ValueError(f"OpenDART request failed: {payload.get('message')}")
            cached = self._cache.set(cache_key, payload)
        return cached

    def _extract_field(
        self,
        rows: list[dict[str, Any]],
        aliases: tuple[str, ...],
    ) -> Decimal | None:
        for row in rows:
            account_id = str(row.get("account_id", ""))
            account_name = str(row.get("account_nm", ""))
            if account_id in aliases or account_name in aliases:
                return self._parse_amount(row.get("thstrm_amount"))
        return None

    def _parse_amount(self, value: Any) -> Decimal | None:
        if value is None:
            return None
        normalized = str(value).replace(",", "").replace(" ", "")
        if not normalized or normalized == "-":
            return None
        try:
            return Decimal(normalized)
        except InvalidOperation:
            return None
