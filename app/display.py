from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import AnnualFinancials, Security, ValuationSnapshot
from app.quant import (
    compute_disparity_percent,
    confidence_score,
    estimate_fair_value,
    normalize_holdings_weights,
    parse_delay_seconds,
)


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
    *,
    include_cash: bool = True,
    cash_value: float | None = None,
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
    fair_value = _fair_value_section(snapshot, annual_rows, units)
    holdings, holdings_policy = _holdings_section(
        snapshot,
        fair_value,
        include_cash=include_cash,
        cash_value=cash_value,
    )
    risk = _risk_section(snapshot, fair_value, holdings, fill_template)
    regime = _market_regime_section(snapshot, fair_value, risk)
    performance = _performance_section(fair_value)
    meta = _snapshot_meta(snapshot)

    return {
        "market": {
            "kind": _market_kind(security),
            "ticker": security.normalized_ticker,
            "market": security.market,
        },
        "tabs": (
            {"id": "market-regime", "label": "Market Regime Board"},
            {"id": "holdings", "label": "Holdings"},
            {"id": "fair-value", "label": "Fair Value"},
            {"id": "risk", "label": "Risk"},
            {"id": "performance", "label": "Portfolio Performance"},
        ),
        "meta": meta,
        "units": units,
        "annual_rows": annual_rows,
        "valuation_items": valuation_items,
        "missing_fields": fill_template,
        "fair_value": fair_value,
        "holdings": holdings,
        "holdings_policy": holdings_policy,
        "risk": risk,
        "market_regime": regime,
        "portfolio_performance": performance,
        "missing_summary": _missing_summary(fill_template),
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
        "meta": _provider_meta(
            source=annual.source if annual else None,
            as_of=annual.as_of if annual else None,
            is_fallback=annual.is_fallback if annual else False,
            diagnostics_count=0,
        ),
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
                "meta": _provider_meta(
                    source=source,
                    as_of=valuation.as_of if valuation else None,
                    is_fallback=is_fallback,
                    diagnostics_count=0,
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
            "Holdings 비중은 평가금액 기준이며 표시 비중 합계가 100.00%가 되도록 마지막 행에서 반올림 보정합니다.",
            "Fair Value 괴리율은 (적정가-현재가)/현재가*100 공식을 모든 화면/API/다운로드에 공통 적용합니다.",
        ]
    if security.is_us:
        return [
            f"Yahoo 재무 금액은 {amount['raw']} 원자료를 {amount['display']} 단위로 나누어 표시합니다.",
            "연도별 EPS/PER/BPS/PBR은 제공값이 없으면 현재가 및 재무값에서 파생 계산합니다.",
            "PER/PBR은 배수, ROE는 %, EPS/BPS는 주당 통화 단위로 별도 표시합니다.",
            "Holdings 비중은 평가금액 기준이며 표시 비중 합계가 100.00%가 되도록 마지막 행에서 반올림 보정합니다.",
            "Fair Value 괴리율은 (적정가-현재가)/현재가*100 공식을 모든 화면/API/다운로드에 공통 적용합니다.",
        ]
    return [
        "시장 구분을 알 수 없어 제공자 원자료 단위로 표시합니다.",
        "PER/PBR은 배수, ROE는 %, EPS/BPS는 주당 통화 단위로 별도 표시합니다.",
    ]


def _snapshot_meta(snapshot: ValuationSnapshot) -> dict[str, Any]:
    provider = snapshot.quote or snapshot.valuation
    source = provider.source if provider else "unavailable"
    as_of = provider.as_of if provider else None
    is_fallback = bool(provider.is_fallback) if provider else True
    delay = parse_delay_seconds(as_of)
    diagnostics_count = len(snapshot.diagnostics or [])
    return {
        "source": source,
        "as_of": as_of,
        "delay_sec": delay,
        "confidence": confidence_score(
            is_fallback=is_fallback,
            diagnostics_count=diagnostics_count,
        ),
        "diagnostics_count": diagnostics_count,
        "has_data": bool(snapshot.quote or snapshot.annual_financials or snapshot.valuation),
    }


def _provider_meta(
    source: str | None,
    as_of: str | None,
    is_fallback: bool,
    diagnostics_count: int,
) -> dict[str, Any]:
    return {
        "source": source or "unknown",
        "as_of": as_of,
        "delay_sec": parse_delay_seconds(as_of),
        "confidence": confidence_score(
            is_fallback=is_fallback,
            diagnostics_count=diagnostics_count,
        ),
    }


def _fair_value_section(
    snapshot: ValuationSnapshot,
    annual_rows: list[dict[str, Any]],
    units: dict[str, Any],
) -> dict[str, Any]:
    current_price = snapshot.quote.price if snapshot.quote else None
    fair_value, components = estimate_fair_value(snapshot.valuation)
    disparity = compute_disparity_percent(current_price, fair_value)

    actual_rows = [row for row in annual_rows if not row["is_estimate"]][-5:]
    estimate_rows = [row for row in annual_rows if row["is_estimate"]][:2]
    if len(estimate_rows) < 2:
        estimate_rows.extend(_estimated_projection_rows(snapshot, units, 2 - len(estimate_rows)))

    rows = []
    for row in (*actual_rows, *estimate_rows):
        year_fair = _row_fair_value(row)
        year_disparity = compute_disparity_percent(current_price, year_fair)
        rows.append(
            {
                "period": row["period"],
                "kind": "E" if row["is_estimate"] else "A",
                "revenue": row["values"]["revenue"]["formatted"],
                "eps": row["values"]["eps"]["formatted"],
                "per": row["values"]["per"]["formatted"],
                "roe": row["values"]["roe"]["formatted"],
                "current_price": format_display_number(current_price),
                "fair_value": format_display_number(year_fair),
                "disparity_pct": format_display_number(year_disparity),
                "signal": _valuation_signal(year_disparity),
            }
        )

    return {
        "current_price": current_price,
        "fair_value": fair_value,
        "disparity_pct": disparity,
        "current_price_formatted": format_display_number(current_price),
        "fair_value_formatted": format_display_number(fair_value),
        "disparity_pct_formatted": format_display_number(disparity),
        "components": components,
        "signal": _valuation_signal(disparity),
        "rows": rows,
        "actual_count": len(actual_rows),
        "estimate_count": len(estimate_rows),
        "policy": {
            "formula": "(fair_value-current_price)/current_price*100",
            "precision": 2,
            "actual_periods": "5A",
            "estimate_periods": "2E",
        },
        "meta": _provider_meta(
            source=snapshot.valuation.source if snapshot.valuation else None,
            as_of=snapshot.valuation.as_of if snapshot.valuation else None,
            is_fallback=bool(snapshot.valuation.is_fallback) if snapshot.valuation else True,
            diagnostics_count=len(snapshot.diagnostics),
        ),
    }


def _estimated_projection_rows(
    snapshot: ValuationSnapshot,
    units: dict[str, Any],
    count: int,
) -> list[dict[str, Any]]:
    if count <= 0:
        return []
    current_year = datetime.now(timezone.utc).year
    valuation = snapshot.valuation
    rows = []
    for offset in range(count):
        year = current_year + offset
        row = _annual_row(year, None, units)
        row["period"] = f"{year}.12(E)"
        row["is_estimate"] = True
        if valuation is not None:
            row["values"]["eps"] = _value_cell(
                valuation.estimated_eps,
                units["per_share"]["display"],
                fill_scope="annual_financials",
                year=year,
                field="eps",
            )
            row["values"]["per"] = _value_cell(
                valuation.estimated_per,
                units["multiple"]["display"],
                fill_scope="annual_financials",
                year=year,
                field="per",
            )
        rows.append(row)
    return rows


def _row_fair_value(row: dict[str, Any]) -> float | None:
    eps = row["values"]["eps"]["raw"]
    per = row["values"]["per"]["raw"]
    bps = row["values"]["bps"]["raw"]
    pbr = row["values"]["pbr"]["raw"]
    values: list[float] = []
    if eps not in (None, 0) and per not in (None, 0):
        values.append(float(eps) * float(per))
    if bps not in (None, 0) and pbr not in (None, 0):
        values.append(float(bps) * float(pbr))
    if not values:
        return None
    return sum(values) / len(values)


def _holdings_section(
    snapshot: ValuationSnapshot,
    fair_value: dict[str, Any],
    *,
    include_cash: bool,
    cash_value: float | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    current_price = snapshot.quote.price if snapshot.quote else None
    base_position_value = max(0.0, float(current_price or fair_value["fair_value"] or 0.0) * 100)
    holdings = [
        {
            "symbol": snapshot.security.normalized_ticker,
            "name": snapshot.security.name or snapshot.security.normalized_ticker,
            "market_value": base_position_value * 0.68,
        },
        {
            "symbol": "FACTOR-ETF",
            "name": "Factor ETF",
            "market_value": base_position_value * 0.22,
        },
        {
            "symbol": "HEDGE",
            "name": "Market Neutral Hedge",
            "market_value": base_position_value * 0.10,
        },
    ]
    resolved_cash = base_position_value * 0.18 if cash_value is None else max(0.0, float(cash_value))
    rows, policy = normalize_holdings_weights(
        holdings,
        include_cash=include_cash,
        cash_value=resolved_cash,
        rounding_digits=2,
    )
    disparity = fair_value["disparity_pct"] or 0.0
    for index, row in enumerate(rows):
        if row.get("is_cash"):
            row["return_pct"] = 0.0
            row["daily_change_pct"] = 0.0
        else:
            scaling = max(0.25, 1 - index * 0.2)
            row["return_pct"] = round(disparity * scaling, 2)
            row["daily_change_pct"] = round((row["return_pct"] / 15), 2)
        row["return_formatted"] = format_display_number(row["return_pct"])
        row["daily_change_formatted"] = format_display_number(row["daily_change_pct"])
        row["weight_formatted"] = format_display_number(row["weight_percent"])
        row["market_value_formatted"] = format_display_number(row["market_value"])
    policy["cash_value"] = resolved_cash
    policy["include_cash"] = include_cash
    policy["assumption"] = "single-ticker snapshot is expanded into model sleeves for dashboard visualization"
    return rows, policy


def _risk_section(
    snapshot: ValuationSnapshot,
    fair_value: dict[str, Any],
    holdings: list[dict[str, Any]],
    missing_fields: list[dict[str, Any]],
) -> dict[str, Any]:
    non_cash = [row for row in holdings if not row.get("is_cash")]
    concentration = max((row["weight_percent"] for row in non_cash), default=0.0)
    cash_weight = next((row["weight_percent"] for row in holdings if row.get("is_cash")), 0.0)
    disparity = abs(float(fair_value["disparity_pct"] or 0.0))
    var95 = round(min(99.0, 4 + concentration * 0.08 + disparity * 0.15), 2)
    volatility = round(min(99.0, 8 + disparity * 0.45), 2)
    liquidity_cover = round(max(0.0, min(100.0, cash_weight * 1.1)), 2)
    missing_score = min(100.0, len(missing_fields) * 4.0)

    alerts = []
    if concentration >= 35:
        alerts.append(
            {
                "id": "risk-concentration",
                "severity": "high",
                "title": "집중도 경보",
                "summary": f"최대 보유 비중이 {format_display_number(concentration)}%입니다.",
                "factors": ("single-name exposure", "sector crowding"),
                "contributors": _top_contributors(non_cash),
                "impact": "포트폴리오 변동성 확대 가능성이 높습니다.",
                "actions": (
                    "비중 상한(예: 25%)을 적용해 분산 리밸런싱",
                    "헤지 비중을 확대하거나 손절 한도를 재설정",
                ),
            }
        )
    if disparity >= 20:
        alerts.append(
            {
                "id": "risk-valuation-gap",
                "severity": "medium",
                "title": "밸류에이션 괴리 확대",
                "summary": f"적정가 대비 괴리율 절대값이 {format_display_number(disparity)}%입니다.",
                "factors": ("valuation dispersion", "estimate uncertainty"),
                "contributors": _top_contributors(non_cash),
                "impact": "평가 손익 변동성이 커질 수 있습니다.",
                "actions": (
                    "목표가 재검증 후 단계적 진입/축소",
                    "추정치 의존 구간은 보수적 할인율 적용",
                ),
            }
        )
    if missing_fields:
        alerts.append(
            {
                "id": "risk-data-gaps",
                "severity": "low",
                "title": "데이터 결측 존재",
                "summary": f"결측 필드 {len(missing_fields)}건이 남아 있습니다.",
                "factors": ("provider coverage", "financial statement gaps"),
                "contributors": (),
                "impact": "일부 지표 신뢰도 저하 가능",
                "actions": (
                    "수동 보정값 입력 또는 데이터 소스 우선순위 조정",
                    "다음 업데이트 시 재수집 수행",
                ),
            }
        )

    metrics = {
        "var95": {"value": var95, "status": _risk_status(var95, high=20, medium=12)},
        "volatility": {"value": volatility, "status": _risk_status(volatility, high=35, medium=20)},
        "concentration": {"value": concentration, "status": _risk_status(concentration, high=35, medium=20)},
        "liquidity_cover": {"value": liquidity_cover, "status": _risk_status(100 - liquidity_cover, high=70, medium=45)},
        "data_gap_score": {"value": missing_score, "status": _risk_status(missing_score, high=45, medium=20)},
    }
    for item in metrics.values():
        item["formatted"] = format_display_number(item["value"])

    return {
        "metrics": metrics,
        "alerts": alerts,
        "selected_alert_id": alerts[0]["id"] if alerts else None,
        "meta": _provider_meta(
            source=snapshot.quote.source if snapshot.quote else (snapshot.valuation.source if snapshot.valuation else None),
            as_of=snapshot.quote.as_of if snapshot.quote else (snapshot.valuation.as_of if snapshot.valuation else None),
            is_fallback=bool(snapshot.quote.is_fallback) if snapshot.quote else bool(snapshot.valuation.is_fallback) if snapshot.valuation else True,
            diagnostics_count=len(snapshot.diagnostics),
        ),
    }


def _top_contributors(rows: list[dict[str, Any]], top_n: int = 3) -> tuple[dict[str, Any], ...]:
    ranked = sorted(rows, key=lambda item: item.get("weight_percent", 0), reverse=True)[:top_n]
    return tuple(
        {
            "symbol": row["symbol"],
            "name": row["name"],
            "weight_percent": row["weight_percent"],
            "market_value": row["market_value"],
        }
        for row in ranked
    )


def _risk_status(value: float, *, high: float, medium: float) -> str:
    if value >= high:
        return "risk"
    if value >= medium:
        return "down"
    return "neutral"


def _market_regime_section(
    snapshot: ValuationSnapshot,
    fair_value: dict[str, Any],
    risk: dict[str, Any],
) -> dict[str, Any]:
    disparity = float(fair_value["disparity_pct"] or 0.0)
    var95 = risk["metrics"]["var95"]["value"]
    diagnostics_count = len(snapshot.diagnostics or [])
    if diagnostics_count >= 2 or var95 >= 18:
        regime = "defensive"
    elif disparity >= 8 and var95 < 12:
        regime = "risk-on"
    else:
        regime = "neutral"
    return {
        "state": regime,
        "indicators": (
            {
                "label": "Valuation Gap",
                "value": format_display_number(disparity),
                "status": "up" if disparity >= 5 else ("down" if disparity <= -5 else "neutral"),
            },
            {
                "label": "VaR(95%)",
                "value": format_display_number(var95),
                "status": "down" if var95 >= 18 else ("neutral" if var95 >= 12 else "up"),
            },
            {
                "label": "Data Diagnostics",
                "value": str(diagnostics_count),
                "status": "down" if diagnostics_count else "up",
            },
        ),
        "meta": _provider_meta(
            source=snapshot.quote.source if snapshot.quote else None,
            as_of=snapshot.quote.as_of if snapshot.quote else None,
            is_fallback=bool(snapshot.quote.is_fallback) if snapshot.quote else True,
            diagnostics_count=diagnostics_count,
        ),
    }


def _performance_section(fair_value: dict[str, Any]) -> dict[str, Any]:
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    disparity = float(fair_value["disparity_pct"] or 0.0)
    target = max(-18.0, min(24.0, disparity))
    portfolio: list[float] = []
    benchmark: list[float] = []
    for index in range(len(months)):
        progress = (index + 1) / len(months)
        cycle = (index % 4 - 1.5) * 0.6
        portfolio.append(round(100 + target * progress + cycle, 2))
        benchmark.append(round(100 + target * 0.65 * progress, 2))
    return {
        "months": months,
        "series": (
            {"name": "Portfolio", "color": "chart-1", "pattern": "solid", "values": portfolio},
            {"name": "Benchmark", "color": "muted-foreground", "pattern": "dashed", "values": benchmark},
        ),
    }


def _valuation_signal(disparity: float | None) -> str:
    if disparity is None:
        return "neutral"
    if disparity >= 15:
        return "buy"
    if disparity <= -15:
        return "trim"
    return "hold"


def _missing_summary(fills: list[dict[str, Any]]) -> dict[str, Any]:
    if not fills:
        return {"count": 0, "items": (), "message": "결측 데이터가 없습니다."}
    items = tuple(
        {
            "scope": item.get("scope"),
            "year": item.get("year"),
            "field": item.get("field"),
            "label": item.get("label"),
            "unit": item.get("input_unit"),
        }
        for item in fills[:8]
    )
    return {
        "count": len(fills),
        "items": items,
        "message": f"결측 필드 {len(fills)}건이 있어 일부 지표는 추정/보정이 필요합니다.",
    }
