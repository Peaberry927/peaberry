"""SEC Company Facts acquisition adapter."""

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
from peaberry.fundamentals.cache import TtlCache
from peaberry.fundamentals.http import JsonHttpClient, UrlLibJsonHttpClient
from peaberry.fundamentals.periods import fiscal_year


class SecCompanyFactsSource:
    """Fetch annual US issuer fundamentals from SEC Company Facts."""

    name = "SEC Company Facts"

    _CONCEPTS = {
        "revenue": (
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet",
        ),
        "operating_income": ("OperatingIncomeLoss",),
        "net_income": ("NetIncomeLoss", "ProfitLoss"),
        "shareholders_equity": (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ),
        "diluted_shares": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
        "dividend_per_share": (
            "CommonStockDividendsPerShareDeclared",
            "CommonStockDividendsPerShareCashPaid",
        ),
    }

    _UNITS = {
        "revenue": ("USD",),
        "operating_income": ("USD",),
        "net_income": ("USD",),
        "shareholders_equity": ("USD",),
        "diluted_shares": ("shares",),
        "dividend_per_share": ("USD/shares",),
    }

    def __init__(
        self,
        symbol_to_cik: dict[Symbol, str],
        http_client: JsonHttpClient | None = None,
        user_agent: str = "peaberry/0.1 contact@example.com",
        cache_ttl: timedelta = timedelta(days=1),
    ) -> None:
        self.symbol_to_cik = dict(symbol_to_cik)
        self.http_client = http_client or UrlLibJsonHttpClient()
        self.user_agent = user_agent
        self._cache: TtlCache[dict[str, Any]] = TtlCache(cache_ttl)

    def statements(
        self,
        symbol: Symbol,
        fiscal_periods: Sequence[str],
    ) -> Iterable[FinancialStatement]:
        cik = self.symbol_to_cik.get(symbol)
        if cik is None:
            return ()

        facts = self._company_facts(cik)
        statements: list[FinancialStatement] = []
        for period in fiscal_periods:
            values: dict[str, Decimal | None] = {}
            value_sources: list[tuple[str, DataSourceRef]] = []
            as_of_dates: list[datetime] = []
            for field_name in self._CONCEPTS:
                value, as_of = self._extract_field(facts, field_name, fiscal_year(period))
                values[field_name] = value
                if value is not None and as_of is not None:
                    value_sources.append((field_name, self._source_ref(as_of)))
                    as_of_dates.append(as_of)

            if not any(value is not None for value in values.values()):
                continue

            source = self._source_ref(
                max(as_of_dates) if as_of_dates else datetime.now(timezone.utc)
            )
            statements.append(
                FinancialStatement(
                    symbol=symbol,
                    fiscal_period=period,
                    currency=Currency("USD"),
                    source=source,
                    value_sources=tuple(value_sources),
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

    def _company_facts(self, cik: str) -> dict[str, Any]:
        normalized = str(cik).zfill(10)
        cached = self._cache.get(normalized)
        if cached is None:
            url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{normalized}.json"
            cached = self._cache.set(
                normalized,
                self.http_client.get_json(
                    url,
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept-Encoding": "gzip, deflate",
                    },
                ),
            )
        return cached

    def _extract_field(
        self,
        facts: dict[str, Any],
        field_name: str,
        year: int,
    ) -> tuple[Decimal | None, datetime | None]:
        us_gaap = facts.get("facts", {}).get("us-gaap", {})
        for concept in self._CONCEPTS[field_name]:
            concept_data = us_gaap.get(concept)
            if not isinstance(concept_data, dict):
                continue
            units = concept_data.get("units", {})
            for unit in self._UNITS[field_name]:
                candidates = [
                    fact
                    for fact in units.get(unit, [])
                    if self._is_annual_fact(fact, year)
                ]
                if not candidates:
                    continue
                fact = max(candidates, key=self._fact_sort_key)
                return Decimal(str(fact["val"])), self._parse_date(fact.get("filed"))
        return None, None

    def _is_annual_fact(self, fact: dict[str, Any], year: int) -> bool:
        return (
            str(fact.get("fy")) == str(year)
            and fact.get("fp") == "FY"
            and fact.get("form") in {"10-K", "10-K/A", "20-F", "40-F"}
            and "val" in fact
        )

    def _fact_sort_key(self, fact: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(fact.get("end", "")),
            str(fact.get("filed", "")),
            str(fact.get("accn", "")),
        )

    def _source_ref(self, as_of: datetime) -> DataSourceRef:
        return DataSourceRef(
            name=self.name,
            kind=SourceKind.REGULATORY_FILING,
            as_of=as_of,
        )

    def _parse_date(self, value: str | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
