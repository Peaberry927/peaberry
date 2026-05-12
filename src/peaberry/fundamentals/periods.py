"""Fiscal period parsing helpers."""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timezone


def fiscal_year(fiscal_period: str) -> int:
    return int(_clean_period(fiscal_period).split(".", maxsplit=1)[0])


def fiscal_month(fiscal_period: str) -> int:
    parts = _clean_period(fiscal_period).split(".", maxsplit=1)
    return int(parts[1]) if len(parts) > 1 else 12


def fiscal_period_end(fiscal_period: str) -> datetime:
    year = fiscal_year(fiscal_period)
    month = fiscal_month(fiscal_period)
    return datetime(
        year,
        month,
        monthrange(year, month)[1],
        23,
        59,
        59,
        tzinfo=timezone.utc,
    )


def _clean_period(fiscal_period: str) -> str:
    return fiscal_period.upper().replace("(E)", "").strip()
