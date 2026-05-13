from __future__ import annotations

from datetime import datetime

from app.models import (
    AnnualFinancials,
    IndexQuote,
    Quote,
    Security,
    ValuationFields,
    ValuationSnapshot,
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
    ) -> ValuationSnapshot:
        years = years or self.default_fiscal_years(5)
        diagnostics: list[str] = []

        quote = self._optional(lambda: self.get_current_price(security), diagnostics)
        annuals = self._optional(
            lambda: self.get_annual_financials(security, years),
            diagnostics,
            default=[],
        )
        valuation = self._optional(lambda: self.get_valuation_fields(security), diagnostics)

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
        current_year = datetime.utcnow().year
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

