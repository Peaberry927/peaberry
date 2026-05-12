"""Display mapping for resolved fundamental rows."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from peaberry.domain.fundamentals import Currency, FundamentalRow, FundamentalValue


@dataclass(frozen=True, slots=True)
class DisplayMetric:
    """Metric value prepared for table rendering."""

    key: str
    label: str
    unit: str
    value: Decimal | None
    description: str
    is_estimate: bool = False
    source_name: str | None = None


@dataclass(frozen=True, slots=True)
class FundamentalDisplayRow:
    """Display row with market-specific units."""

    fiscal_period: str
    currency: Currency
    metrics: tuple[DisplayMetric, ...]
    missing_fields: tuple[str, ...]


METRIC_DESCRIPTIONS = {
    "revenue": "회사가 해당 기간에 인식한 총수익.",
    "operating_income": "매출에서 영업비용을 뺀 영업 성과.",
    "net_income": "모든 비용과 세금을 반영한 순이익.",
    "roe": "순이익 / 자본총계 x 100. 자본 대비 이익률.",
    "eps": "순이익 / 희석주식수. 1주당 이익.",
    "per": "주가 / EPS. 이익 대비 주가 배수.",
    "bps": "자본총계 / 희석주식수. 1주당 순자산.",
    "pbr": "주가 / BPS. 순자산 대비 주가 배수.",
    "dividend_yield": "주당배당금 / 주가 x 100. 배당 수익률.",
}


class FundamentalDisplayMapper:
    """Convert raw pipeline rows into UI-ready units and labels."""

    def map_row(self, row: FundamentalRow) -> FundamentalDisplayRow:
        metrics = (
            self._statement_metric(row, "revenue", "매출"),
            self._statement_metric(row, "operating_income", "영업이익"),
            self._statement_metric(row, "net_income", "순이익"),
            self._ratio_metric(row, "roe", "ROE", "%"),
            self._per_share_metric(row, "eps", "EPS"),
            self._ratio_metric(row, "per", "PER", "배"),
            self._per_share_metric(row, "bps", "BPS"),
            self._ratio_metric(row, "pbr", "PBR", "배"),
            self._ratio_metric(row, "dividend_yield", "배당수익률", "%"),
        )
        return FundamentalDisplayRow(
            fiscal_period=row.fiscal_period,
            currency=row.currency,
            metrics=metrics,
            missing_fields=row.missing_fields,
        )

    def _statement_metric(
        self,
        row: FundamentalRow,
        key: str,
        label: str,
    ) -> DisplayMetric:
        value = getattr(row, key)
        if row.currency == Currency("KRW"):
            return self._metric(key, label, "억원", value, Decimal("100000000"))
        return self._metric(key, label, "USD mn", value, Decimal("1000000"))

    def _per_share_metric(
        self,
        row: FundamentalRow,
        key: str,
        label: str,
    ) -> DisplayMetric:
        unit = "원/주" if row.currency == Currency("KRW") else "USD/share"
        return self._metric(key, label, unit, getattr(row, key), Decimal("1"))

    def _ratio_metric(
        self,
        row: FundamentalRow,
        key: str,
        label: str,
        unit: str,
    ) -> DisplayMetric:
        return self._metric(key, label, unit, getattr(row, key), Decimal("1"))

    def _metric(
        self,
        key: str,
        label: str,
        unit: str,
        value: FundamentalValue | None,
        divisor: Decimal,
    ) -> DisplayMetric:
        return DisplayMetric(
            key=key,
            label=label,
            unit=unit,
            value=None if value is None else value.amount / divisor,
            description=METRIC_DESCRIPTIONS[key],
            is_estimate=False if value is None else value.is_estimate,
            source_name=None if value is None else value.source.name,
        )
