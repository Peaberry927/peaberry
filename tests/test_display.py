from __future__ import annotations

import unittest

from app.display import build_display_snapshot
from app.models import AnnualFinancials, Quote, Security, ValuationFields, ValuationSnapshot, utc_now_iso


class DisplaySnapshotTests(unittest.TestCase):
    def test_korean_financials_use_eokwon_and_ratio_units(self) -> None:
        snapshot = ValuationSnapshot(
            security=Security(ticker="000660", market="KOSPI"),
            quote=Quote(
                ticker="000660",
                price=194000,
                currency="KRW",
                source="naver",
                as_of=utc_now_iso(),
            ),
            annual_financials=[
                AnnualFinancials(
                    ticker="000660",
                    year=2024,
                    revenue=100_000_000_000,
                    operating_income=20_000_000_000,
                    net_income=10_000_000_000,
                    equity=50_000_000_000,
                    source="opendart",
                    as_of=utc_now_iso(),
                )
            ],
            valuation=ValuationFields(
                ticker="000660",
                per=8.1,
                pbr=1.3,
                eps=24_000,
                bps=149_000,
                source="naver",
                as_of=utc_now_iso(),
            ),
            diagnostics=[],
        )

        display = build_display_snapshot(snapshot, [2024])

        self.assertEqual(display["units"]["amount"]["display"], "억원")
        self.assertEqual(display["units"]["multiple"]["display"], "배")
        self.assertEqual(display["units"]["percent"]["display"], "%")
        self.assertEqual(display["units"]["per_share"]["display"], "KRW/주")
        self.assertEqual(display["annual_rows"][0]["values"]["revenue"]["display"], 1000)
        self.assertEqual(display["annual_rows"][0]["values"]["roe"]["display"], 20)

    def test_us_financials_use_usd_millions(self) -> None:
        snapshot = ValuationSnapshot(
            security=Security(ticker="AAPL", market="US"),
            quote=Quote(
                ticker="AAPL",
                price=200,
                currency="USD",
                source="yahoo",
                as_of=utc_now_iso(),
                is_fallback=True,
            ),
            annual_financials=[
                AnnualFinancials(
                    ticker="AAPL",
                    year=2024,
                    revenue=383_285_000_000,
                    operating_income=114_301_000_000,
                    net_income=96_995_000_000,
                    equity=62_146_000_000,
                    source="yahoo",
                    as_of=utc_now_iso(),
                    is_fallback=True,
                )
            ],
            valuation=None,
            diagnostics=[],
        )

        display = build_display_snapshot(snapshot, [2024])

        self.assertEqual(display["units"]["amount"]["display"], "USD mn")
        self.assertEqual(display["units"]["per_share"]["display"], "USD/share")
        self.assertEqual(display["annual_rows"][0]["values"]["revenue"]["display"], 383285)
        self.assertEqual(display["valuation_items"][0]["value"]["is_missing"], True)

    def test_missing_fields_include_fill_template_with_display_units(self) -> None:
        snapshot = ValuationSnapshot(
            security=Security(ticker="AAPL", market="US"),
            quote=None,
            annual_financials=[
                AnnualFinancials(
                    ticker="AAPL",
                    year=2024,
                    revenue=None,
                    operating_income=120_000_000,
                    net_income=None,
                    equity=None,
                    source="yahoo",
                    as_of=utc_now_iso(),
                    is_fallback=True,
                )
            ],
            valuation=ValuationFields(
                ticker="AAPL",
                per=None,
                pbr=9,
                eps=None,
                bps=None,
                source="yahoo",
                as_of=utc_now_iso(),
                is_fallback=True,
            ),
            diagnostics=[],
        )

        display = build_display_snapshot(snapshot, [2024])
        fill_fields = {(item["scope"], item["year"], item["field"]) for item in display["missing_fields"]}

        self.assertIn(("annual_financials", 2024, "revenue"), fill_fields)
        self.assertIn(("valuation_fields", None, "eps"), fill_fields)
        self.assertIn(("derived", 2024, "roe"), fill_fields)
        revenue_fill = next(
            item for item in display["missing_fields"] if item["field"] == "revenue"
        )
        self.assertEqual(revenue_fill["input_unit"], "USD mn")


if __name__ == "__main__":
    unittest.main()
