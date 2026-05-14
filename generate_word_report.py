from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
import zipfile


OUTPUT_PATH = Path("/workspace/Quant_System_Proposal_and_Development_Backlog.docx")


def paragraph(text: str, *, bold: bool = False) -> str:
    run_props = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return (
        "<w:p>"
        "<w:r>"
        f"{run_props}"
        f'<w:t xml:space="preserve">{escape(text)}</w:t>'
        "</w:r>"
        "</w:p>"
    )


def build_document_xml() -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[tuple[str, bool]] = [
        ("Quant Investment Dashboard / Quant System", True),
        ("수정 제안서 및 개발 백로그", True),
        ("", False),
        (f"문서 생성일: {generated_at}", False),
        ("버전: v1.0", False),
        ("작성 대상: Product / Quant / Frontend / Backend / QA", False),
        ("", False),
        ("1. 제안서 (Proposal)", True),
        ("1.1 목적", True),
        (
            "전수 테스트 결과를 기준으로 정확성, 신뢰성, 리스크 실행성, UI 성능을 개선하여 "
            "전문 투자자용 대시보드의 운영 품질을 상향한다.",
            False,
        ),
        ("", False),
        ("1.2 테스트 요약", True),
        ("- PASS: UI 레이아웃, 탭 전환, 색상 규칙, A/E 컬럼 구분, 반응형 배치", False),
        ("- FAIL(P0): BUG-001 비중 합계 오차, BUG-002 괴리율 반올림 불일치", False),
        ("- BLOCKED(P1): BUG-003 Risk Alert drill-down 미구현", False),
        ("", False),
        ("1.3 핵심 이슈 및 영향", True),
        (
            "A) 비중 합계 오차: 포트폴리오 집계 신뢰 저하 및 리밸런싱 판단 오류 가능성",
            False,
        ),
        (
            "B) 괴리율 반올림 불일치: Fair Value 투자판단 기준값 혼선, 보고서 수치 불일치",
            False,
        ),
        (
            "C) 리스크 알림 비실행성: 경보는 있으나 원인/대응이 연결되지 않아 운영 효율 저하",
            False,
        ),
        ("", False),
        ("1.4 수정 전략", True),
        ("- P0 우선: 계산 표준화(비중, 괴리율) 및 표시 규칙 일원화", False),
        ("- P1 다음: Risk Alert drill-down 구현 및 액션형 UX 도입", False),
        ("- 공통: source/as-of/delay/confidence 메타데이터 전 컴포넌트 표준화", False),
        ("", False),
        ("1.5 완료 기준", True),
        ("- P0 테스트케이스 100% PASS", False),
        ("- High 심각도 버그 0건", False),
        ("- API 응답값/화면표시값/다운로드값 간 계산 일치", False),
        ("", False),
        ("2. 개발 백로그 (Development Backlog)", True),
        ("2.1 Sprint P0 - 즉시 처리", True),
        ("[QNT-101] Holdings 비중 합계 정합성 보정", True),
        ("- 목적: 정렬/필터 상태와 무관하게 총합 100% 규칙 유지", False),
        ("- 구현: raw 정밀 계산 후 표시는 마지막 항목 보정 또는 cash bucket 보정", False),
        ("- 산출물: weight normalization utility + 회귀 테스트", False),
        ("- 완료조건: 합계 오차 허용범위(정책치) 이내", False),
        ("", False),
        ("[QNT-102] Fair Value 괴리율 계산/반올림 정책 단일화", True),
        ("- 목적: 모든 화면/툴팁/내보내기에서 동일 수식 및 반올림 적용", False),
        ("- 구현: Decimal 기반 공통 함수 calc_disparity_percent()", False),
        ("- 완료조건: 행별 결과와 API 결과 100% 일치", False),
        ("", False),
        ("[QNT-103] 숫자 포맷 공통 컴포넌트", True),
        ("- 목적: tabular-nums, 부호, 천단위, 소수점 자릿수 규칙 통일", False),
        ("- 완료조건: KPI/테이블/차트 툴팁 포맷 일관성 확보", False),
        ("", False),
        ("2.2 Sprint P1 - 기능 완성", True),
        ("[QNT-201] Risk Alert Drill-down 패널 구현", True),
        ("- 목적: 경고를 실행 가능한 액션으로 전환", False),
        ("- 구현: 원인팩터, 기여종목 Top N, 영향도, 권장액션 카드", False),
        ("- API: /risk/alerts/{id}/detail", False),
        ("- 완료조건: Alert 클릭 시 상세 정보 1초 이내 렌더", False),
        ("", False),
        ("[QNT-202] 데이터 신뢰성 메타 표준화", True),
        ("- 목적: 모든 핵심 수치에 source, as-of, delay_sec, confidence 제공", False),
        ("- 완료조건: KPI/Market/Fair Value/Risk 전 영역 적용", False),
        ("", False),
        ("[QNT-203] 결측/오류 상태 UX 강화", True),
        ("- 목적: 빈 화면 방지, last-known-good 데이터 기반 fallback 제공", False),
        ("- 완료조건: 네트워크 오류/부분 실패에서도 레이아웃 안정 유지", False),
        ("", False),
        ("2.3 Sprint P2 - 고도화", True),
        ("[QNT-301] 스트레스 시나리오 패널", True),
        ("- 금리/환율/지수 충격 시 포트폴리오 PnL/VaR 변화 예측", False),
        ("", False),
        ("[QNT-302] 리포트 내보내기", True),
        ("- PDF/CSV 내보내기(포지션, 섹터, Fair Value, 리스크)", False),
        ("", False),
        ("[QNT-303] 개인화 대시보드 설정", True),
        ("- 사용자별 위젯 고정, 경보 임계치 저장, watchlist", False),
        ("", False),
        ("3. QA/릴리즈 게이트", True),
        ("- 게이트 1: P0 FIX 검증(R2) PASS", False),
        ("- 게이트 2: 회귀 스모크(NAV/KPI/HLD/FV/RSK) PASS", False),
        ("- 게이트 3: 신규 High 버그 0건", False),
        ("- 게이트 4: 운영 체크리스트 승인(QA Lead, FE Lead, PM)", False),
        ("", False),
        ("4. 책임 및 협업", True),
        ("- Quant: 계산식/리스크 모델 기준 확정", False),
        ("- Backend: API 계약 및 메타데이터 표준 적용", False),
        ("- Frontend: 표시 규칙, Drill-down UX, 반응형/접근성 보강", False),
        ("- QA: 전수 테스트 및 릴리즈 게이트 판정", False),
        ("", False),
        ("부록 A. 버그 매핑", True),
        ("- BUG-001 -> QNT-101", False),
        ("- BUG-002 -> QNT-102", False),
        ("- BUG-003 -> QNT-201", False),
    ]

    body = "".join(paragraph(text, bold=bold) for text, bold in lines)
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
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/>'
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
  <dc:title>Quant System Proposal and Development Backlog</dc:title>
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
