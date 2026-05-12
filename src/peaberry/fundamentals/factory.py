"""Factories for production-ready fundamentals source composition."""

from __future__ import annotations

from peaberry.domain.fundamentals import Currency
from peaberry.domain.market import Symbol
from peaberry.fundamentals.adapters import (
    OpenDartFundamentalsSource,
    SecCompanyFactsSource,
    YahooChartMarketDataSource,
)
from peaberry.fundamentals.http import JsonHttpClient
from peaberry.fundamentals.sources import CompositeFundamentalsSource, FundamentalsSource


def build_fundamentals_source(
    *,
    sec_ciks: dict[Symbol, str] | None = None,
    dart_corp_codes: dict[Symbol, str] | None = None,
    market_tickers: dict[Symbol, str] | None = None,
    market_currencies: dict[Symbol, Currency] | None = None,
    dart_api_key: str | None = None,
    http_client: JsonHttpClient | None = None,
    sec_user_agent: str = "peaberry/0.1 contact@example.com",
) -> CompositeFundamentalsSource:
    """Build a source chain that actually acquires external data.

    Priority order intentionally keeps audited filings ahead of market data and
    estimates: SEC/DART statements first, then period-specific Yahoo prices.
    """

    sources: list[FundamentalsSource] = []
    if sec_ciks:
        sources.append(
            SecCompanyFactsSource(
                symbol_to_cik=sec_ciks,
                http_client=http_client,
                user_agent=sec_user_agent,
            )
        )
    if dart_api_key and dart_corp_codes:
        sources.append(
            OpenDartFundamentalsSource(
                api_key=dart_api_key,
                symbol_to_corp_code=dart_corp_codes,
                http_client=http_client,
            )
        )
    if market_tickers:
        sources.append(
            YahooChartMarketDataSource(
                symbol_to_ticker=market_tickers,
                symbol_to_currency=market_currencies,
                http_client=http_client,
            )
        )
    return CompositeFundamentalsSource(sources)
