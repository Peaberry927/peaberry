from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def compute_disparity_percent(
    current_price: float | None,
    fair_value: float | None,
) -> float | None:
    """Return ((fair - current) / current) * 100 with decimal safety."""
    if current_price in (None, 0) or fair_value is None:
        return None
    current = Decimal(str(current_price))
    fair = Decimal(str(fair_value))
    return float((fair - current) / current * Decimal("100"))


def estimate_fair_value(valuation: Any) -> tuple[float | None, tuple[str, ...]]:
    """Estimate fair value from available valuation fields."""
    if valuation is None:
        return None, ()

    components: list[tuple[str, Decimal]] = []
    per = getattr(valuation, "per", None)
    eps = getattr(valuation, "eps", None)
    pbr = getattr(valuation, "pbr", None)
    bps = getattr(valuation, "bps", None)

    if per not in (None, 0) and eps not in (None, 0):
        components.append(("PER x EPS", Decimal(str(per)) * Decimal(str(eps))))
    if pbr not in (None, 0) and bps not in (None, 0):
        components.append(("PBR x BPS", Decimal(str(pbr)) * Decimal(str(bps))))

    if not components:
        return None, ()
    estimate = sum(value for _, value in components) / Decimal(str(len(components)))
    return float(estimate), tuple(label for label, _ in components)


def normalize_holdings_weights(
    holdings: list[dict[str, Any]],
    *,
    include_cash: bool,
    cash_value: float | None = None,
    rounding_digits: int = 2,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Normalize holding weights so the displayed sum is exactly 100.00."""
    rows = [dict(item) for item in holdings]
    if include_cash:
        cash_market_value = max(0.0, float(cash_value or 0.0))
        rows.append(
            {
                "symbol": "CASH",
                "name": "현금",
                "market_value": cash_market_value,
                "is_cash": True,
            }
        )

    q = Decimal("1").scaleb(-rounding_digits)
    values = [max(Decimal("0"), Decimal(str(item.get("market_value", 0) or 0))) for item in rows]
    total = sum(values)
    if total <= 0:
        for item in rows:
            item["weight_raw"] = 0.0
            item["weight_percent"] = 0.0
        return rows, {
            "include_cash": include_cash,
            "cash_included": include_cash,
            "weight_basis": "market_value",
            "rounding_mode": "HALF_UP",
            "rounding_digits": rounding_digits,
            "normalization": "no-positive-market-value",
            "total_market_value": 0.0,
            "weight_sum": 0.0,
        }

    raw_weights = [(value / total) * Decimal("100") for value in values]
    rounded_weights: list[Decimal] = []
    running = Decimal("0")
    for index, raw in enumerate(raw_weights):
        if index == len(raw_weights) - 1:
            rounded = (Decimal("100") - running).quantize(q, rounding=ROUND_HALF_UP)
        else:
            rounded = raw.quantize(q, rounding=ROUND_HALF_UP)
            running += rounded
        rounded_weights.append(rounded)

    for item, raw, rounded in zip(rows, raw_weights, rounded_weights):
        item["weight_raw"] = float(raw)
        item["weight_percent"] = float(rounded)

    return rows, {
        "include_cash": include_cash,
        "cash_included": include_cash,
        "weight_basis": "market_value",
        "rounding_mode": "HALF_UP",
        "rounding_digits": rounding_digits,
        "normalization": "last-row-adjustment",
        "total_market_value": float(total),
        "weight_sum": float(sum(rounded_weights)),
    }


def parse_delay_seconds(as_of: str | None) -> int | None:
    if not as_of:
        return None
    try:
        parsed = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()))


def confidence_score(*, is_fallback: bool, diagnostics_count: int) -> float:
    base = Decimal("0.92") if not is_fallback else Decimal("0.72")
    penalty = Decimal("0.07") * Decimal(str(min(5, diagnostics_count)))
    score = base - penalty
    if score < Decimal("0.35"):
        score = Decimal("0.35")
    if score > Decimal("0.98"):
        score = Decimal("0.98")
    return float(score)
