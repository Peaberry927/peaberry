from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
import zipfile


OUTPUT_PATH = Path("/workspace/Quant_System_Implementation_Proposal_v2.docx")


def paragraph(
    text: str,
    *,
    bold: bool = False,
    center: bool = False,
    size_half_points: int | None = None,
) -> str:
    props = []
    if bold:
        props.append("<w:b/>")
    if size_half_points is not None:
        props.append(f'<w:sz w:val="{size_half_points}"/>')
        props.append(f'<w:szCs w:val="{size_half_points}"/>')
    run_props = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
    para_props = '<w:pPr><w:jc w:val="center"/></w:pPr>' if center else ""
    return (
        "<w:p>"
        f"{para_props}"
        "<w:r>"
        f"{run_props}"
        f'<w:t xml:space="preserve">{escape(text)}</w:t>'
        "</w:r>"
        "</w:p>"
    )


def table(headers: list[str], rows: list[list[str]]) -> str:
    col_width = 9000 // max(1, len(headers))
    grid = "".join(f'<w:gridCol w:w="{col_width}"/>' for _ in headers)
    border = (
        "<w:tblBorders>"
        '<w:top w:val="single" w:sz="6" w:space="0" w:color="AAB7C4"/>'
        '<w:left w:val="single" w:sz="6" w:space="0" w:color="AAB7C4"/>'
        '<w:bottom w:val="single" w:sz="6" w:space="0" w:color="AAB7C4"/>'
        '<w:right w:val="single" w:sz="6" w:space="0" w:color="AAB7C4"/>'
        '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="C7D1DC"/>'
        '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="C7D1DC"/>'
        "</w:tblBorders>"
    )

    def row_xml(cells: list[str], is_header: bool = False) -> str:
        rendered_cells = []
        for cell in cells:
            cell_bg = (
                '<w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="EAF0F7"/></w:tcPr>'
                if is_header
                else ""
            )
            rendered_cells.append(
                "<w:tc>"
                f"{cell_bg}"
                "<w:p><w:r>"
                + ("<w:rPr><w:b/></w:rPr>" if is_header else "")
                + f'<w:t xml:space="preserve">{escape(cell)}</w:t>'
                + "</w:r></w:p>"
                "</w:tc>"
            )
        return "<w:tr>" + "".join(rendered_cells) + "</w:tr>"

    body_rows = row_xml(headers, is_header=True) + "".join(row_xml(row) for row in rows)
    return (
        "<w:tbl>"
        f"<w:tblPr>{border}</w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>"
        f"{body_rows}"
        "</w:tbl>"
    )


def build_document_xml() -> str:
    now_label = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    blocks: list[str] = []

    # Cover page
    blocks.append(paragraph("Quant Investment Dashboard", bold=True, center=True, size_half_points=40))
    blocks.append(paragraph("System Implementation Proposal v2.0", bold=True, center=True, size_half_points=34))
    blocks.append(paragraph("", center=True))
    blocks.append(paragraph("Executable Design and Coding Blueprint", center=True, size_half_points=24))
    blocks.append(paragraph("", center=True))
    blocks.append(paragraph(f"Generated at: {now_label}", center=True))
    blocks.append(paragraph("Audience: Product / Quant / Backend / Frontend / QA / DevOps", center=True))
    blocks.append(paragraph(""))
    blocks.append(paragraph(""))

    # Manual table of contents
    blocks.append(paragraph("Table of Contents", bold=True, size_half_points=28))
    toc_items = [
        "1. Executive Summary",
        "2. Architecture and Layer Responsibilities",
        "3. Core Quant Policies (P0)",
        "4. API Contracts and Data Models",
        "5. UI Composition and Interaction Design",
        "6. Risk Drill-down Functional Design (P1)",
        "7. Error and Missing-data UX",
        "8. Development Backlog and Delivery Plan",
        "9. Requirement Traceability Matrix",
        "10. Test Strategy and Regression Checklist",
        "11. Done Criteria and Operational Handover",
    ]
    for item in toc_items:
        blocks.append(paragraph(f"- {item}"))
    blocks.append(paragraph(""))

    # Sections
    blocks.append(paragraph("1. Executive Summary", bold=True, size_half_points=28))
    blocks.append(
        paragraph(
            "This document is written as a coding-ready design. It freezes formulas, policies, API fields, "
            "UI component boundaries, and test gates so engineers can implement without interpretation drift."
        )
    )
    blocks.append(paragraph(""))

    blocks.append(paragraph("2. Architecture and Layer Responsibilities", bold=True, size_half_points=28))
    arch_rows = [
        ["Provider Layer", "Naver/OpenDART/Yahoo fetch, parse, and failure diagnostics"],
        ["Pipeline Layer", "Acquire + enrich + derive + aggregate diagnostics"],
        ["Quant Core Layer", "Shared formulas: weights, disparity, fair value, confidence, delay"],
        ["Display Layer", "Single DTO used by UI and export"],
        ["Delivery Layer", "FastAPI endpoints + static dashboard + CSV/Excel download"],
    ]
    blocks.append(table(["Layer", "Responsibility"], arch_rows))
    blocks.append(paragraph(""))

    blocks.append(paragraph("3. Core Quant Policies (P0)", bold=True, size_half_points=28))
    blocks.append(paragraph("3.1 Holdings weight normalization policy", bold=True))
    blocks.append(paragraph("- Weight basis: market_value"))
    blocks.append(paragraph("- Optional cash inclusion: include_cash + cash_value"))
    blocks.append(paragraph("- Display precision: 2 digits, ROUND_HALF_UP"))
    blocks.append(paragraph("- Guaranteed display sum: 100.00 via last-row adjustment"))
    blocks.append(paragraph("3.2 Fair value disparity policy", bold=True))
    blocks.append(paragraph("- Formula: (fair_value - current_price) / current_price * 100"))
    blocks.append(paragraph("- Formula implementation must be centralized in one function"))
    blocks.append(paragraph("- Same numeric output required across UI/API/CSV/Excel"))
    blocks.append(paragraph(""))

    blocks.append(paragraph("4. API Contracts and Data Models", bold=True, size_half_points=28))
    api_rows = [
        ["/api/snapshot/{ticker}", "GET", "market, corp_code, years, include_cash, cash_value, dart_api_key"],
        ["/api/snapshot/{ticker}/download", "GET", "format=csv|excel + snapshot query params"],
    ]
    blocks.append(table(["Endpoint", "Method", "Key Params"], api_rows))
    blocks.append(paragraph("Required response keys in display payload:", bold=True))
    blocks.append(paragraph("- tabs, meta, holdings, holdings_policy, fair_value, risk, market_regime, portfolio_performance"))
    blocks.append(paragraph("- meta contains source, as_of, delay_sec, confidence"))
    blocks.append(paragraph(""))

    blocks.append(paragraph("5. UI Composition and Interaction Design", bold=True, size_half_points=28))
    blocks.append(paragraph("Tabbed card layout (must not render all sections in one long list):"))
    blocks.append(paragraph("- Market Regime Board"))
    blocks.append(paragraph("- Holdings"))
    blocks.append(paragraph("- Fair Value"))
    blocks.append(paragraph("- Risk (with drill-down panel)"))
    blocks.append(paragraph("- Portfolio Performance"))
    blocks.append(paragraph("Unified state colors: up / down / neutral / risk"))
    blocks.append(paragraph("Numeric table style: right aligned, tabular-nums, thousand separators, fixed 2 decimals"))
    blocks.append(paragraph("Chart convention: series-specific colors and line patterns (solid, dashed)"))
    blocks.append(paragraph(""))

    blocks.append(paragraph("6. Risk Drill-down Functional Design (P1)", bold=True, size_half_points=28))
    blocks.append(paragraph("Alert object fields:", bold=True))
    blocks.append(paragraph("- id, severity, title, summary"))
    blocks.append(paragraph("- factors[]"))
    blocks.append(paragraph("- contributors[] (Top N positions)"))
    blocks.append(paragraph("- impact"))
    blocks.append(paragraph("- actions[]"))
    blocks.append(paragraph("Interaction rule: clicking an alert must immediately populate the drill-down panel"))
    blocks.append(paragraph(""))

    blocks.append(paragraph("7. Error and Missing-data UX", bold=True, size_half_points=28))
    blocks.append(paragraph("- If fetch fails and previous snapshot exists: render last-known-good + warning banner"))
    blocks.append(paragraph("- If provider partially fails: keep layout stable and display diagnostics summary"))
    blocks.append(paragraph("- Missing numeric fields should display placeholders, never collapse cards/tables"))
    blocks.append(paragraph(""))

    blocks.append(paragraph("8. Development Backlog and Delivery Plan", bold=True, size_half_points=28))
    backlog_rows = [
        ["QNT-101", "P0", "Holdings weight normalization and cash policy", "Quant + Backend"],
        ["QNT-102", "P0", "Central disparity function and display/export consistency", "Quant + Backend"],
        ["QNT-103", "P0", "Number format standardization in all tables/cards", "Frontend"],
        ["QNT-201", "P1", "Risk alert drill-down panel and interaction", "Frontend + Backend"],
        ["QNT-202", "P1", "Metadata exposure: source/as_of/delay_sec/confidence", "Backend"],
        ["QNT-203", "P1", "Resilient missing/error UX states", "Frontend"],
        ["QNT-301", "P2", "Stress scenario simulation panel", "Quant + Backend"],
        ["QNT-302", "P2", "Extended reporting pipeline", "Backend"],
    ]
    blocks.append(table(["Ticket", "Priority", "Deliverable", "Owner"], backlog_rows))
    blocks.append(paragraph(""))

    blocks.append(paragraph("9. Requirement Traceability Matrix", bold=True, size_half_points=28))
    trace_rows = [
        ["REQ-UI-01", "Tabbed card layout", "static/index.html", "E2E tab navigation", "Planned"],
        ["REQ-UI-02", "Color state consistency", "static/index.html", "Visual regression", "Planned"],
        ["REQ-P0-01", "Weight sum = 100.00", "app/quant.py", "tests/test_quant_calculations.py", "Planned"],
        ["REQ-P0-02", "Shared disparity formula", "app/quant.py + app/display.py", "tests/test_quant_calculations.py", "Planned"],
        ["REQ-P0-03", "UI/API/Export value parity", "app/display.py + app/export.py", "tests/test_export.py", "Planned"],
        ["REQ-P1-01", "Risk drill-down", "app/display.py + static/index.html", "E2E risk drill-down", "Planned"],
        ["REQ-P1-02", "Metadata on key metrics", "app/display.py", "API contract tests", "Planned"],
        ["REQ-UX-01", "Last-known-good fallback", "static/index.html", "Network failure test", "Planned"],
    ]
    blocks.append(table(["Req ID", "Requirement", "Implementation", "Verification", "Status"], trace_rows))
    blocks.append(paragraph(""))

    blocks.append(paragraph("10. Test Strategy and Regression Checklist", bold=True, size_half_points=28))
    checklist = [
        "Unit: disparity formula, weight normalization, export parity",
        "Integration: snapshot payload schema, include_cash/cash_value behavior",
        "E2E: tab flow, risk drill-down, download behavior, error fallback",
        "Regression gate: all P0 pass, 0 High defects, no UI/API/Export numeric mismatch",
    ]
    for line in checklist:
        blocks.append(paragraph(f"- {line}"))
    blocks.append(paragraph(""))

    blocks.append(paragraph("11. Done Criteria and Operational Handover", bold=True, size_half_points=28))
    done_items = [
        "Holdings displayed weights always equal 100.00",
        "Disparity formula centralized and reused everywhere",
        "CSV/Excel values equal to dashboard values",
        "Risk drill-down is interactive and complete",
        "Metadata displayed for core metrics",
        "Error and missing-data states do not break layout",
    ]
    for item in done_items:
        blocks.append(paragraph(f"- [ ] {item}"))

    body = "".join(blocks)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" '
        'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
        'xmlns:o="urn:schemas-microsoft-com:office:office" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
        'xmlns:v="urn:schemas-microsoft-com:vml" '
        'xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:w10="urn:schemas-microsoft-com:office:word" '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
        'xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" '
        'xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk" '
        'xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml" '
        'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
        'mc:Ignorable="w14 wp14">'
        f"<w:body>{body}"
        "<w:sectPr>"
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1200" w:bottom="1440" w:left="1200" w:header="708" w:footer="708" w:gutter="0"/>'
        "<w:cols w:space=\"708\"/>"
        "<w:docGrid w:linePitch=\"360\"/>"
        "</w:sectPr>"
        "</w:body></w:document>"
    )


def build_docx(path: Path) -> None:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""
    app_props = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
            xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft Office Word</Application>
</Properties>
"""
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    core_props = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/"
                   xmlns:dcterms="http://purl.org/dc/terms/"
                   xmlns:dcmitype="http://purl.org/dc/dcmitype/"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Quant System Implementation Proposal v2.0</dc:title>
  <dc:creator>Cursor Agent</dc:creator>
  <cp:lastModifiedBy>Cursor Agent</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>
"""
    document_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
"""

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", content_types)
        package.writestr("_rels/.rels", rels)
        package.writestr("docProps/app.xml", app_props)
        package.writestr("docProps/core.xml", core_props)
        package.writestr("word/_rels/document.xml.rels", document_rels)
        package.writestr("word/document.xml", build_document_xml())


if __name__ == "__main__":
    build_docx(OUTPUT_PATH)
    print(f"Generated: {OUTPUT_PATH}")
