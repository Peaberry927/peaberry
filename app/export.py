from __future__ import annotations

import csv
import io
from typing import Any


def snapshot_export_csv(display: dict[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "section",
            "metric",
            "value",
            "unit",
            "source",
            "as_of",
            "delay_sec",
            "confidence",
        ]
    )

    meta = display.get("meta", {})
    source = meta.get("source")
    as_of = meta.get("as_of")
    delay_sec = meta.get("delay_sec")
    confidence = meta.get("confidence")

    fair = display.get("fair_value", {})
    writer.writerow(
        [
            "fair_value",
            "current_price",
            fair.get("current_price_formatted"),
            display.get("units", {}).get("per_share", {}).get("display", ""),
            source,
            as_of,
            delay_sec,
            confidence,
        ]
    )
    writer.writerow(
        [
            "fair_value",
            "fair_value",
            fair.get("fair_value_formatted"),
            display.get("units", {}).get("per_share", {}).get("display", ""),
            source,
            as_of,
            delay_sec,
            confidence,
        ]
    )
    writer.writerow(
        [
            "fair_value",
            "disparity_pct",
            fair.get("disparity_pct_formatted"),
            "%",
            source,
            as_of,
            delay_sec,
            confidence,
        ]
    )

    for row in display.get("holdings", []):
        writer.writerow(
            [
                "holdings",
                row.get("symbol"),
                row.get("weight_formatted"),
                "%",
                source,
                as_of,
                delay_sec,
                confidence,
            ]
        )
    for key, item in (display.get("risk", {}).get("metrics", {}) or {}).items():
        writer.writerow(
            [
                "risk",
                key,
                f"{item.get('value', 0):.2f}",
                "%",
                source,
                as_of,
                delay_sec,
                confidence,
            ]
        )
    return output.getvalue()
