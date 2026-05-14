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
    fair_meta = fair.get("meta") or meta
    fair_source = fair_meta.get("source")
    fair_as_of = fair_meta.get("as_of")
    fair_delay_sec = fair_meta.get("delay_sec")
    fair_confidence = fair_meta.get("confidence")
    writer.writerow(
        [
            "fair_value",
            "current_price",
            fair.get("current_price_formatted"),
            display.get("units", {}).get("per_share", {}).get("display", ""),
            fair_source,
            fair_as_of,
            fair_delay_sec,
            fair_confidence,
        ]
    )
    writer.writerow(
        [
            "fair_value",
            "fair_value",
            fair.get("fair_value_formatted"),
            display.get("units", {}).get("per_share", {}).get("display", ""),
            fair_source,
            fair_as_of,
            fair_delay_sec,
            fair_confidence,
        ]
    )
    writer.writerow(
        [
            "fair_value",
            "disparity_pct",
            fair.get("disparity_pct_formatted"),
            "%",
            fair_source,
            fair_as_of,
            fair_delay_sec,
            fair_confidence,
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
    risk = display.get("risk", {}) or {}
    risk_meta = risk.get("meta") or meta
    risk_source = risk_meta.get("source")
    risk_as_of = risk_meta.get("as_of")
    risk_delay_sec = risk_meta.get("delay_sec")
    risk_confidence = risk_meta.get("confidence")
    for key, item in (risk.get("metrics", {}) or {}).items():
        writer.writerow(
            [
                "risk",
                key,
                item.get("formatted") or f"{item.get('value', 0):.2f}",
                "%",
                risk_source,
                risk_as_of,
                risk_delay_sec,
                risk_confidence,
            ]
        )
    return output.getvalue()
