"""Diagnostics for missing fundamental table cells."""

from __future__ import annotations

from dataclasses import dataclass

from peaberry.domain.fundamentals import FundamentalRow, SourceKind
from peaberry.domain.market import Symbol


@dataclass(frozen=True, slots=True)
class FundamentalAcquisitionRequest:
    """Actionable request to fill a missing row/field."""

    symbol: Symbol
    fiscal_period: str
    target_field: str
    required_fields: tuple[str, ...]
    recommended_sources: tuple[SourceKind, ...]
    reason: str
    estimate_allowed: bool = False


class FundamentalCoveragePlanner:
    """Create source-specific acquisition work for unresolved table gaps."""

    def plan(self, rows: tuple[FundamentalRow, ...]) -> tuple[FundamentalAcquisitionRequest, ...]:
        requests: list[FundamentalAcquisitionRequest] = []
        for row in rows:
            for field_name in row.missing_fields:
                request = self._request_for(row, field_name)
                if request is not None:
                    requests.append(request)
        return tuple(requests)

    def _request_for(
        self,
        row: FundamentalRow,
        field_name: str,
    ) -> FundamentalAcquisitionRequest | None:
        estimate_allowed = self._estimate_allowed(row.fiscal_period)
        if field_name in ("revenue", "operating_income", "net_income"):
            return FundamentalAcquisitionRequest(
                symbol=row.symbol,
                fiscal_period=row.fiscal_period,
                target_field=field_name,
                required_fields=(field_name,),
                recommended_sources=self._statement_sources(estimate_allowed),
                reason=f"{field_name} is absent from the resolved statement row",
                estimate_allowed=estimate_allowed,
            )
        if field_name == "roe":
            return FundamentalAcquisitionRequest(
                symbol=row.symbol,
                fiscal_period=row.fiscal_period,
                target_field=field_name,
                required_fields=("net_income", "shareholders_equity"),
                recommended_sources=self._statement_sources(estimate_allowed),
                reason="ROE requires net income and shareholders' equity",
                estimate_allowed=estimate_allowed,
            )
        if field_name == "eps":
            required = (
                ("diluted_shares",)
                if row.net_income is not None
                else ("net_income", "diluted_shares")
            )
            return FundamentalAcquisitionRequest(
                symbol=row.symbol,
                fiscal_period=row.fiscal_period,
                target_field=field_name,
                required_fields=required,
                recommended_sources=self._statement_sources(estimate_allowed),
                reason="EPS requires net income and diluted share count",
                estimate_allowed=estimate_allowed,
            )
        if field_name == "bps":
            return FundamentalAcquisitionRequest(
                symbol=row.symbol,
                fiscal_period=row.fiscal_period,
                target_field=field_name,
                required_fields=("shareholders_equity", "diluted_shares"),
                recommended_sources=self._statement_sources(estimate_allowed),
                reason="BPS requires shareholders' equity and diluted share count",
                estimate_allowed=estimate_allowed,
            )
        if field_name == "per":
            return FundamentalAcquisitionRequest(
                symbol=row.symbol,
                fiscal_period=row.fiscal_period,
                target_field=field_name,
                required_fields=self._valuation_requirements(row, "eps"),
                recommended_sources=self._valuation_sources(row, "eps", estimate_allowed),
                reason="PER requires positive EPS and a period-specific price or market cap",
                estimate_allowed=estimate_allowed,
            )
        if field_name == "pbr":
            return FundamentalAcquisitionRequest(
                symbol=row.symbol,
                fiscal_period=row.fiscal_period,
                target_field=field_name,
                required_fields=self._valuation_requirements(row, "bps"),
                recommended_sources=self._valuation_sources(row, "bps", estimate_allowed),
                reason="PBR requires BPS and a period-specific price or market cap",
                estimate_allowed=estimate_allowed,
            )
        if field_name == "dividend_yield":
            return FundamentalAcquisitionRequest(
                symbol=row.symbol,
                fiscal_period=row.fiscal_period,
                target_field=field_name,
                required_fields=("dividend_per_share", "period_end_price_or_market_cap"),
                recommended_sources=tuple(
                    dict.fromkeys(
                        self._statement_sources(estimate_allowed)
                        + (SourceKind.MARKET_DATA,)
                    )
                ),
                reason="Dividend yield requires dividend per share and market price",
                estimate_allowed=estimate_allowed,
            )
        return None

    def _statement_sources(self, estimate_allowed: bool) -> tuple[SourceKind, ...]:
        sources = [SourceKind.REGULATORY_FILING, SourceKind.COMPANY_IR]
        if estimate_allowed:
            sources.append(SourceKind.ANALYST_ESTIMATE)
        return tuple(sources)

    def _valuation_sources(
        self,
        row: FundamentalRow,
        base_metric: str,
        estimate_allowed: bool,
    ) -> tuple[SourceKind, ...]:
        sources = [SourceKind.MARKET_DATA]
        if getattr(row, base_metric) is None:
            sources.extend(self._statement_sources(estimate_allowed))
        return tuple(dict.fromkeys(sources))

    def _valuation_requirements(
        self,
        row: FundamentalRow,
        base_metric: str,
    ) -> tuple[str, ...]:
        requirements = ["period_end_price_or_market_cap"]
        if getattr(row, base_metric) is None:
            if base_metric == "eps":
                requirements.extend(("net_income", "diluted_shares"))
            if base_metric == "bps":
                requirements.extend(("shareholders_equity", "diluted_shares"))
        return tuple(requirements)

    def _estimate_allowed(self, fiscal_period: str) -> bool:
        return "(E)" in fiscal_period.upper()
