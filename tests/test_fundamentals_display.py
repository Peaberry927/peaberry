from datetime import datetime, timezone
from decimal import Decimal
from unittest import TestCase

from peaberry.domain.fundamentals import (
    Currency,
    DataSourceRef,
    FundamentalRow,
    FundamentalValue,
    SourceKind,
)
from peaberry.domain.market import Symbol
from peaberry.fundamentals import FundamentalDisplayMapper


class FundamentalsDisplayTests(TestCase):
    def test_domestic_statement_values_are_displayed_in_eok_krw(self) -> None:
        source = DataSourceRef(
            name="OpenDART",
            kind=SourceKind.REGULATORY_FILING,
            as_of=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        row = FundamentalRow(
            symbol=Symbol("000660"),
            fiscal_period="2024.12",
            currency=Currency("KRW"),
            revenue=FundamentalValue(Decimal("66193000000000"), source),
            eps=FundamentalValue(Decimal("27193"), source),
            per=FundamentalValue(Decimal("6.36"), source),
        )

        display = FundamentalDisplayMapper().map_row(row)
        metrics = {metric.key: metric for metric in display.metrics}

        self.assertEqual(metrics["revenue"].unit, "억원")
        self.assertEqual(metrics["revenue"].value, Decimal("661930"))
        self.assertEqual(metrics["eps"].unit, "원/주")
        self.assertEqual(metrics["per"].unit, "배")

    def test_us_statement_values_are_displayed_in_usd_mn(self) -> None:
        source = DataSourceRef(
            name="SEC Company Facts",
            kind=SourceKind.REGULATORY_FILING,
            as_of=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        row = FundamentalRow(
            symbol=Symbol("AAPL"),
            fiscal_period="2024.12",
            currency=Currency("USD"),
            revenue=FundamentalValue(Decimal("391035000000"), source),
            eps=FundamentalValue(Decimal("6.11"), source),
            roe=FundamentalValue(Decimal("164.59"), source),
        )

        display = FundamentalDisplayMapper().map_row(row)
        metrics = {metric.key: metric for metric in display.metrics}

        self.assertEqual(metrics["revenue"].unit, "USD mn")
        self.assertEqual(metrics["revenue"].value, Decimal("391035"))
        self.assertEqual(metrics["eps"].unit, "USD/share")
        self.assertEqual(metrics["roe"].unit, "%")

    def test_metric_descriptions_are_formula_focused(self) -> None:
        row = FundamentalRow(
            symbol=Symbol("AAPL"),
            fiscal_period="2024.12",
            currency=Currency("USD"),
        )

        descriptions = [
            metric.description for metric in FundamentalDisplayMapper().map_row(row).metrics
        ]

        banned = (
            "".join(("보강", "됨")),
            "".join(("종", "합")),
            "".join(("보", "완")),
            "".join(("통합", " 분석")),
            "".join(("상세", " 보강")),
            "".join(("종", "합", " 요약")),
        )
        for description in descriptions:
            for term in banned:
                self.assertNotIn(term, description)
        self.assertIn("주가 / EPS", descriptions[5])
