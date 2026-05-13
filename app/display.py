from __future__ import annotations

from typing import Any

from app.models import AnnualFinancials, Security, ValuationSnapshot


FINANCIAL_FIELDS = ("revenue", "operating_income", "net_income")
ROW_VALUATION_FIELDS = ("eps", "per", "bps", "pbr")
VALUATION_FIELDS = ("eps", "per", "bps", "pbr", "estimated_eps", "estimated_per")

FIELD_LABELS = {
    "revenue": "매출",
    "operating_income": "영업이익",
    "net_income": "순이익",
    "roe": "ROE",
    "eps": "EPS",
    "per": "PER",
    "bps": "BPS",
    "pbr": "PBR",
    "estimated_eps": "추정 EPS",
    "estimated_per": "추정 PER",
}


def build_display_snapshot(
    snapshot: ValuationSnapshot,
    years: list[int] | None = None,
) -> dict[str, Any]:
    """Build market-aware display metadata without changing raw provider values."""

    security = snapshot.security
    units = _display_units(security, snapshot.quote.currency if snapshot.quote else None)
    annuals_by_year = {item.year: item for item in snapshot.annual_financials}
    display_years = years or sorted(annuals_by_year.keys(), reverse=True)
    annual_rows = [
        _annual_row(year, annuals_by_year.get(year), units)
        for year in display_years
    ]
    valuation_items = _valuation_items(snapshot, units)
    fill_template = _fill_template(annual_rows, valuation_items)

    return {
        "market": {
            "kind": _market_kind(security),
            "ticker": security.normalized_ticker,
            "market": security.market,
        },
        "units": units,
        "annual_rows": annual_rows,
        "valuation_items": valuation_items,
        "missing_fields": fill_template,
        "notes": _notes(security, units),
    }


def _display_units(security: Security, quote_currency: str | None) -> dict[str, Any]:
    if security.is_korean:
        amount_unit = "억원"
        amount_divisor = 100_000_000
        raw_amount_unit = "KRW"
        currency = quote_currency or "KRW"
        per_share_unit = f"{currency}/주"
    elif security.is_us:
        amount_unit = "USD mn"
        amount_divisor = 1_000_000
        raw_amount_unit = "USD"
        currency = quote_currency or "USD"
        per_share_unit = f"{currency}/share"
    else:
        amount_unit = "raw"
        amount_divisor = 1
        raw_amount_unit = quote_currency or "provider raw"
        currency = quote_currency or "raw"
        per_share_unit = f"{currency}/share"

    return {
        "amount": {
            "display": amount_unit,
            "raw": raw_amount_unit,
            "divisor": amount_divisor,
            "applies_to": list(FINANCIAL_FIELDS),
        },
        "per_share": {
            "display": per_share_unit,
            "applies_to": ["eps", "bps"],
        },
        "multiple": {
            "display": "배",
            "applies_to": ["per", "pbr"],
        },
        "percent": {
            "display": "%",
            "applies_to": ["roe"],
        },
    }


def _annual_row(
    year: int,
    annual: AnnualFinancials | None,
    units: dict[str, Any],
) -> dict[str, Any]:
    row = {
        "year": year,
        "period": f"{year}.12(E)" if annual and annual.is_estimate else f"{year}.12",
        "source": annual.source if annual else None,
        "is_fallback": annual.is_fallback if annual else False,
        "is_estimate": annual.is_estimate if annual else False,
        "values": {},
    }
    for field in FINANCIAL_FIELDS:
        raw_value = getattr(annual, field) if annual else None
        row["values"][field] = _value_cell(
            raw_value,
            units["amount"]["display"],
            divisor=units["amount"]["divisor"],
            fill_scope="annual_financials",
            year=year,
            field=field,
        )

    roe = _roe_value(annual)
    row["values"]["roe"] = _value_cell(
        roe,
        units["percent"]["display"],
        fill_scope="derived",
        year=year,
        field="roe",
    )
    for field in ROW_VALUATION_FIELDS:
        raw_value = getattr(annual, field) if annual else None
        unit = (
            units["multiple"]["display"]
            if field in {"per", "pbr"}
            else units["per_share"]["display"]
        )
        row["values"][field] = _value_cell(
            raw_value,
            unit,
            fill_scope="annual_financials",
            year=year,
            field=field,
        )
    return row


def _valuation_items(
    snapshot: ValuationSnapshot,
    units: dict[str, Any],
) -> list[dict[str, Any]]:
    valuation = snapshot.valuation
    source = valuation.source if valuation else None
    is_fallback = valuation.is_fallback if valuation else False
    unit_by_field = {
        "eps": units["per_share"]["display"],
        "per": units["multiple"]["display"],
        "bps": units["per_share"]["display"],
        "pbr": units["multiple"]["display"],
        "estimated_eps": units["per_share"]["display"],
        "estimated_per": units["multiple"]["display"],
    }

    items = []
    for field in VALUATION_FIELDS:
        raw_value = getattr(valuation, field) if valuation else None
        items.append(
            {
                "field": field,
                "label": FIELD_LABELS[field],
                "source": source,
                "is_fallback": is_fallback,
                "value": _value_cell(
                    raw_value,
                    unit_by_field[field],
                    fill_scope="valuation_fields",
                    field=field,
                ),
            }
        )
    return items


def _value_cell(
    raw_value: float | None,
    unit: str,
    divisor: float = 1,
    fill_scope: str | None = None,
    field: str | None = None,
    year: int | None = None,
) -> dict[str, Any]:
    display_value = None if raw_value is None else raw_value / divisor
    return {
        "raw": raw_value,
        "display": display_value,
        "formatted": format_display_number(display_value),
        "unit": unit,
        "is_missing": raw_value is None,
        "fill": {
            "scope": fill_scope,
            "field": field,
            "year": year,
            "label": FIELD_LABELS.get(field or "", field),
            "input_unit": unit,
            "input_scale": "display",
        }
        if raw_value is None and fill_scope and field
        else None,
    }


def format_display_number(value: float | None) -> str:
    if value is None:
        return "-"
    abs_value = abs(value)
    if abs_value >= 100:
        return f"{value:,.0f}"
    if abs_value >= 10:
        return f"{value:,.1f}"
    return f"{value:,.2f}"


def _roe_value(annual: AnnualFinancials | None) -> float | None:
    if annual is None or annual.net_income is None or annual.equity in (None, 0):
        return None
    return annual.net_income / annual.equity * 100


def _fill_template(
    annual_rows: list[dict[str, Any]],
    valuation_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    fills: list[dict[str, Any]] = []
    for row in annual_rows:
        for cell in row["values"].values():
            if cell["fill"]:
                fills.append(cell["fill"])
    for item in valuation_items:
        cell = item["value"]
        if cell["fill"]:
            fills.append(cell["fill"])
    return fills


def _market_kind(security: Security) -> str:
    if security.is_korean:
        return "korean"
    if security.is_us:
        return "us"
    return "unknown"


def _notes(security: Security, units: dict[str, Any]) -> list[str]:
    amount = units["amount"]
    if security.is_korean:
        return [
            f"OpenDART 금액은 원 단위 원자료를 {amount['display']} 단위로 나누어 표시합니다.",
            "연도별 EPS/PER/BPS/PBR은 Naver 실적표와 현재가 기반 파생 계산값을 함께 사용합니다.",
            "PER/PBR은 배수, ROE는 %, EPS/BPS는 주당 통화 단위로 별도 표시합니다.",
            "빈 칸은 표시 단위 기준으로 수동 입력할 수 있으며 원자료 값은 변경하지 않습니다.",
        ]
    if security.is_us:
        return [
            f"Yahoo 재무 금액은 {amount['raw']} 원자료를 {amount['display']} 단위로 나누어 표시합니다.",
            "연도별 EPS/PER/BPS/PBR은 제공값이 없으면 현재가 및 재무값에서 파생 계산합니다.",
            "PER/PBR은 배수, ROE는 %, EPS/BPS는 주당 통화 단위로 별도 표시합니다.",
            "빈 칸은 표시 단위 기준으로 수동 입력할 수 있으며 원자료 값은 변경하지 않습니다.",
        ]
    return [
        "시장 구분을 알 수 없어 제공자 원자료 단위로 표시합니다.",
        "PER/PBR은 배수, ROE는 %, EPS/BPS는 주당 통화 단위로 별도 표시합니다.",
    ]
