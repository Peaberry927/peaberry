from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Iterable

from app.models import (
    AnnualFinancials,
    IndexQuote,
    Quote,
    Security,
    ValuationFields,
    ValuationSnapshot,
    utc_now_iso,
)
from app.providers import NaverFinanceProvider, OpenDartProvider, ProviderError, YahooFinanceProvider
from app.storage import SQLiteStore


class QuantDataPipeline:
    """Orchestrates provider order and persistence for quant-ready snapshots."""

    def __init__(
        self,
        store: SQLiteStore | None = None,
        naver: NaverFinanceProvider | None = None,
        opendart: OpenDartProvider | None = None,
        yahoo: YahooFinanceProvider | None = None,
    ) -> None:
        self.store = store or SQLiteStore()
        self.naver = naver or NaverFinanceProvider()
        self.opendart = opendart or OpenDartProvider()
        self.yahoo = yahoo or YahooFinanceProvider()

    def get_current_price(self, security: Security) -> Quote:
        self.store.upsert_security(security)
        self.store.clear_stale_fallback_values(security.normalized_ticker)

        if security.is_korean:
            return self._save_or_raise(
                self.naver.fetch_current_price,
                self.store.save_quote,
                security,
                provider="naver",
            )

        if security.is_us:
            return self._save_or_raise(
                self.yahoo.fetch_current_price,
                self.store.save_quote,
                security,
                provider="yahoo",
            )

        raise ProviderError(f"No current price provider configured for {security.ticker}")

    def get_index_quote(self, index_code: str) -> IndexQuote:
        quote = self._save_or_raise(
            self.naver.fetch_index,
            self.store.save_index_quote,
            index_code,
            provider="naver",
            ticker=index_code,
        )
        return quote

    def get_annual_financials(self, security: Security, years: list[int]) -> list[AnnualFinancials]:
        self.store.upsert_security(security)
        self.store.clear_stale_fallback_values(security.normalized_ticker)

        output: list[AnnualFinancials] = []
        errors: list[str] = []
        for year in years:
            try:
                if security.is_korean:
                    output.append(
                        self._save_or_raise(
                            lambda item, fiscal_year=year: self.opendart.fetch_annual_financials(
                                item, fiscal_year
                            ),
                            self.store.save_annual_financials,
                            security,
                            provider="opendart",
                        )
                    )
                    continue

                if security.is_us:
                    output.append(
                        self._save_or_raise(
                            lambda item, fiscal_year=year: self.yahoo.fetch_annual_financials(
                                item, fiscal_year
                            ),
                            self.store.save_annual_financials,
                            security,
                            provider="yahoo",
                        )
                    )
                    continue

                raise ProviderError(f"No annual financials provider configured for {security.ticker}")
            except ProviderError as exc:
                errors.append(str(exc))
                continue

        if output:
            return output
        if errors:
            raise ProviderError(errors[0])
        raise ProviderError(f"No annual financials provider configured for {security.ticker}")

    def get_valuation_fields(self, security: Security) -> ValuationFields:
        self.store.upsert_security(security)
        self.store.clear_stale_fallback_values(security.normalized_ticker)

        if security.is_korean:
            return self._save_or_raise(
                self.naver.fetch_valuation_fields,
                self.store.save_valuation_fields,
                security,
                provider="naver",
            )

        if security.is_us:
            return self._save_or_raise(
                self.yahoo.fetch_valuation_fields,
                self.store.save_valuation_fields,
                security,
                provider="yahoo",
            )

        raise ProviderError(f"No valuation provider configured for {security.ticker}")

    def build_valuation_snapshot(
        self,
        security: Security,
        years: list[int] | None = None,
        dart_api_key: str | None = None,
    ) -> ValuationSnapshot:
        years = years or self.default_fiscal_years(5)
        diagnostics: list[str] = []
        if dart_api_key:
            self.opendart.api_key = dart_api_key

        quote = self._optional(lambda: self.get_current_price(security), diagnostics)
        annuals = self._optional(
            lambda: self.get_annual_financials(security, years),
            diagnostics,
            default=[],
        )
        valuation = self._optional(lambda: self.get_valuation_fields(security), diagnostics)
        annuals = self._enrich_annual_financials(
            security=security,
            years=years,
            annuals=annuals,
            quote=quote,
            valuation=valuation,
            diagnostics=diagnostics,
        )

        return ValuationSnapshot(
            security=security,
            quote=quote,
            annual_financials=annuals,
            valuation=valuation,
            diagnostics=diagnostics,
        )

    def clear_stale_fallback_values(self, ticker: str | None = None) -> int:
        return self.store.clear_stale_fallback_values(ticker)

    def default_fiscal_years(self, count: int) -> list[int]:
        current_year = datetime.now(timezone.utc).year
        return [current_year - offset - 1 for offset in range(count)]

    def _save_or_raise(self, fetch, save, arg, provider: str, ticker: str | None = None):
        try:
            result = fetch(arg)
        except ProviderError as exc:
            self.store.record_event(provider, "error", str(exc), ticker or getattr(arg, "ticker", None))
            raise
        save(result)
        self.store.record_event(
            provider,
            "success",
            f"stored {result.__class__.__name__}",
            ticker or getattr(result, "ticker", None) or getattr(result, "index_code", None),
        )
        return result

    def _optional(self, operation, diagnostics: list[str], default=None):
        try:
            return operation()
        except ProviderError as exc:
            diagnostics.append(str(exc))
            return default

    def _enrich_annual_financials(
        self,
        security: Security,
        years: list[int],
        annuals: list[AnnualFinancials],
        quote: Quote | None,
        valuation: ValuationFields | None,
        diagnostics: list[str],
    ) -> list[AnnualFinancials]:
        rows_by_year = {row.year: row for row in annuals}
        if security.is_korean:
            naver_rows = self._optional(
                lambda: self.naver.fetch_annual_metrics(security),
                diagnostics,
                default=[],
            )
            naver_by_year = {row.year: row for row in naver_rows}
            for year in years:
                merged = self._merge_annual_row(
                    security.normalized_ticker,
                    year,
                    rows_by_year.get(year),
                    naver_by_year.get(year),
                )
                if merged is not None:
                    rows_by_year[year] = merged

        current_year = datetime.now(timezone.utc).year
        for year in years:
            if year in rows_by_year:
                continue
            if valuation is None:
                continue
            if year < current_year:
                continue
            if valuation.estimated_eps is None and valuation.estimated_per is None:
                continue
            rows_by_year[year] = AnnualFinancials(
                ticker=security.normalized_ticker,
                year=year,
                eps=valuation.estimated_eps,
                per=valuation.estimated_per,
                source=valuation.source or "estimated",
                as_of=utc_now_iso(),
                is_fallback=valuation.is_fallback,
                is_estimate=True,
            )

        share_count = self._estimate_share_count(rows_by_year.values(), valuation)
        for year in years:
            row = rows_by_year.get(year)
            if row is None:
                continue
            enriched = self._apply_derived_valuation_fields(row, quote, valuation, share_count)
            rows_by_year[year] = enriched
            self.store.save_annual_financials(enriched)

        return [rows_by_year[year] for year in years if year in rows_by_year]

    def _merge_annual_row(
        self,
        ticker: str,
        year: int,
        base: AnnualFinancials | None,
        supplemental: AnnualFinancials | None,
    ) -> AnnualFinancials | None:
        if base is None and supplemental is None:
            return None
        if base is None and supplemental is not None:
            return replace(supplemental, ticker=ticker, year=year)
        if base is None:
            return None
        if supplemental is None:
            return replace(base, ticker=ticker, year=year)

        updates: dict[str, object] = {}
        merged_fields = (
            "revenue",
            "operating_income",
            "net_income",
            "assets",
            "liabilities",
            "equity",
            "eps",
            "bps",
            "per",
            "pbr",
        )
        used_supplemental = False
        for field in merged_fields:
            base_value = getattr(base, field)
            supplemental_value = getattr(supplemental, field)
            if base_value is None and supplemental_value is not None:
                updates[field] = supplemental_value
                used_supplemental = True
        if not base.is_estimate and supplemental.is_estimate:
            updates["is_estimate"] = True
            used_supplemental = True
        if used_supplemental and supplemental.source and supplemental.source not in base.source:
            updates["source"] = f"{base.source}+{supplemental.source}"
        return replace(base, ticker=ticker, year=year, **updates)

    def _estimate_share_count(
        self,
        annuals: Iterable[AnnualFinancials],
        valuation: ValuationFields | None,
    ) -> float | None:
        rows = list(annuals)
        for row in sorted(rows, key=lambda item: item.year, reverse=True):
            if row.net_income is not None and row.eps not in (None, 0):
                return abs(row.net_income / row.eps)
        if valuation is None or valuation.eps in (None, 0):
            return None
        for row in sorted(rows, key=lambda item: item.year, reverse=True):
            if row.net_income is not None:
                return abs(row.net_income / valuation.eps)
        return None

    def _apply_derived_valuation_fields(
        self,
        annual: AnnualFinancials,
        quote: Quote | None,
        valuation: ValuationFields | None,
        share_count: float | None,
    ) -> AnnualFinancials:
        updates: dict[str, object] = {}
        derived = False

        eps = annual.eps
        if eps is None:
            if annual.net_income is not None and share_count not in (None, 0):
                eps = annual.net_income / share_count
                updates["eps"] = eps
                derived = True
            elif annual.is_estimate and valuation and valuation.estimated_eps is not None:
                eps = valuation.estimated_eps
                updates["eps"] = eps
                derived = True

        bps = annual.bps
        if bps is None and annual.equity is not None and share_count not in (None, 0):
            bps = annual.equity / share_count
            updates["bps"] = bps
            derived = True

        if annual.per is None:
            if quote and quote.price is not None and eps not in (None, 0):
                updates["per"] = quote.price / eps
                derived = True
            elif annual.is_estimate and valuation and valuation.estimated_per is not None:
                updates["per"] = valuation.estimated_per
                derived = True

        if annual.pbr is None and quote and quote.price is not None and bps not in (None, 0):
            updates["pbr"] = quote.price / bps
            derived = True

        if derived and "+derived" not in annual.source:
            updates["source"] = f"{annual.source}+derived"

        if not updates:
            return annual
        return replace(annual, **updates)

