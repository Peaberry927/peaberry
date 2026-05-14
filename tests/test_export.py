from __future__ import annotations

import unittest

from app.main import _snapshot_export_csv


class ExportTests(unittest.TestCase):
    def test_export_csv_reuses_display_values(self) -> None:
        display = {
            "meta": {
                "source": "naver",
                "as_of": "2026-05-14T05:00:00+00:00",
                "delay_sec": 12,
                "confidence": 0.88,
            },
            "units": {"per_share": {"display": "KRW/주"}},
            "fair_value": {
                "current_price_formatted": "100.00",
                "fair_value_formatted": "120.00",
                "disparity_pct_formatted": "20.00",
            },
            "holdings": [
                {"symbol": "AAA", "weight_formatted": "40.00"},
                {"symbol": "BBB", "weight_formatted": "60.00"},
            ],
            "risk": {
                "metrics": {
                    "var95": {"value": 8.0},
                    "volatility": {"value": 11.0},
                }
            },
        }

        csv_text = _snapshot_export_csv(display)

        self.assertIn("fair_value,disparity_pct,20.00,%", csv_text)
        self.assertIn("holdings,AAA,40.00,%", csv_text)
        self.assertIn("risk,var95,8.00,%", csv_text)


if __name__ == "__main__":
    unittest.main()
