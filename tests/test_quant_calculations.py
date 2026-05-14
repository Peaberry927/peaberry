from __future__ import annotations

import unittest

from app.display import build_display_snapshot
from app.models import Quote, Security, ValuationFields, ValuationSnapshot, utc_now_iso
from app.quant import compute_disparity_percent, normalize_holdings_weights


class QuantCalculationTests(unittest.TestCase):
    def test_compute_disparity_percent_uses_common_formula(self) -> None:
        disparity = compute_disparity_percent(current_price=100.0, fair_value=120.0)
        self.assertAlmostEqual(disparity or 0, 20.0, places=6)

    def test_holdings_weights_sum_to_100_with_cash(self) -> None:
        rows, policy = normalize_holdings_weights(
            [
                {"symbol": "AAA", "market_value": 10},
                {"symbol": "BBB", "market_value": 20},
                {"symbol": "CCC", "market_value": 70},
            ],
            include_cash=True,
            cash_value=5,
            rounding_digits=2,
        )
        self.assertAlmostEqual(sum(item["weight_percent"] for item in rows), 100.0, places=6)
        self.assertTrue(policy["include_cash"])
        self.assertEqual(policy["normalization"], "last-row-adjustment")

    def test_display_fair_value_uses_same_disparity_formula(self) -> None:
        snapshot = ValuationSnapshot(
            security=Security(ticker="AAPL", market="US"),
            quote=Quote(
                ticker="AAPL",
                price=100.0,
                currency="USD",
                source="yahoo",
                as_of=utc_now_iso(),
                is_fallback=True,
            ),
            annual_financials=[],
            valuation=ValuationFields(
                ticker="AAPL",
                per=10.0,
                eps=12.0,
                pbr=None,
                bps=None,
                source="yahoo",
                as_of=utc_now_iso(),
                is_fallback=True,
            ),
            diagnostics=[],
        )

        display = build_display_snapshot(snapshot, [2024])
        self.assertAlmostEqual(display["fair_value"]["fair_value"], 120.0, places=6)
        self.assertAlmostEqual(display["fair_value"]["disparity_pct"], 20.0, places=6)


if __name__ == "__main__":
    unittest.main()
