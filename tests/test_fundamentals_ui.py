from dataclasses import dataclass
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
from peaberry.fundamentals import FundamentalUiPresenter


@dataclass(frozen=True, slots=True)
class PipelineResultStub:
    rows: tuple[FundamentalRow, ...]
    source_errors: tuple[tuple[str, str], ...]


class FundamentalsUiTests(TestCase):
    def test_presenter_connects_units_and_source_errors_to_screen_model(self) -> None:
        source = DataSourceRef(
            name="OpenDART",
            kind=SourceKind.REGULATORY_FILING,
            as_of=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        result = PipelineResultStub(
            rows=(
                FundamentalRow(
                    symbol=Symbol("000660"),
                    fiscal_period="2024.12",
                    currency=Currency("KRW"),
                    revenue=FundamentalValue(Decimal("66193000000000"), source),
                    per=FundamentalValue(Decimal("6.36"), source),
                ),
            ),
            source_errors=(("Yahoo Finance Chart", "too many requests"),),
        )

        screen = FundamentalUiPresenter().present(result)  # type: ignore[arg-type]
        metrics = {metric.key: metric for metric in screen.rows[0].metrics}

        self.assertTrue(screen.has_source_errors)
        self.assertEqual(screen.source_errors[0][0], "Yahoo Finance Chart")
        self.assertEqual(metrics["revenue"].unit, "억원")
        self.assertEqual(metrics["per"].unit, "배")
