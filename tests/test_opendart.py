from __future__ import annotations

import io
import unittest
import zipfile

from app.models import Security
from app.providers.opendart import OpenDartProvider


class StubHttpClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls: list[dict[str, str]] = []

    def get_json(self, url: str, params: dict[str, str] | None = None) -> dict:
        self.calls.append(params or {})
        return self.responses[len(self.calls) - 1]


class CorpCodeHttpClient:
    def __init__(self, corp_xml_rows: list[tuple[str, str]], statements: list[dict]) -> None:
        self.statements = statements
        self.json_calls: list[dict[str, str]] = []
        self.bytes_calls: list[dict[str, str]] = []
        xml = "<result>" + "".join(
            f"<list><corp_code>{corp}</corp_code><stock_code>{stock}</stock_code></list>"
            for stock, corp in corp_xml_rows
        ) + "</result>"
        zipped = io.BytesIO()
        with zipfile.ZipFile(zipped, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("CORPCODE.xml", xml)
        self._payload = zipped.getvalue()

    def get_bytes(self, url: str, params: dict[str, str] | None = None) -> bytes:
        self.bytes_calls.append(params or {})
        return self._payload

    def get_json(self, url: str, params: dict[str, str] | None = None) -> dict:
        self.json_calls.append(params or {})
        return self.statements[len(self.json_calls) - 1]


class OpenDartProviderTests(unittest.TestCase):
    def test_retries_with_ofs_when_cfs_has_no_data(self) -> None:
        http = StubHttpClient(
            responses=[
                {"status": "013", "message": "No data"},
                {
                    "status": "000",
                    "list": [
                        {"account_nm": "매출액(영업수익)", "thstrm_amount": "1000000000"},
                        {"account_nm": "영업이익(손실)", "thstrm_amount": "120000000"},
                        {"account_nm": "당기순손익", "thstrm_amount": "90000000"},
                        {"account_nm": "자본총계", "thstrm_amount": "700000000"},
                    ],
                },
            ]
        )
        provider = OpenDartProvider(api_key="test-key", http_client=http)

        row = provider.fetch_annual_financials(
            Security(ticker="005930", market="KOSPI", corp_code="00126380"),
            2024,
        )

        self.assertEqual(len(http.calls), 2)
        self.assertEqual(http.calls[0]["fs_div"], "CFS")
        self.assertEqual(http.calls[1]["fs_div"], "OFS")
        self.assertEqual(row.revenue, 1_000_000_000)
        self.assertEqual(row.operating_income, 120_000_000)
        self.assertEqual(row.net_income, 90_000_000)
        self.assertEqual(row.equity, 700_000_000)

    def test_maps_metrics_by_ifrs_account_id(self) -> None:
        http = StubHttpClient(
            responses=[
                {
                    "status": "000",
                    "list": [
                        {
                            "account_nm": "Revenue from contracts",
                            "account_id": "ifrs-full_Revenue",
                            "thstrm_amount": "1200",
                        },
                        {
                            "account_nm": "Profit (loss)",
                            "account_id": "ifrs-full_ProfitLoss",
                            "thstrm_amount": "300",
                        },
                        {
                            "account_nm": "Assets",
                            "account_id": "ifrs-full_Assets",
                            "thstrm_amount": "9000",
                        },
                    ],
                }
            ]
        )
        provider = OpenDartProvider(api_key="test-key", http_client=http)

        row = provider.fetch_annual_financials(
            Security(ticker="A000", market="KOSPI", corp_code="12345678"),
            2023,
        )

        self.assertEqual(row.revenue, 1200)
        self.assertEqual(row.net_income, 300)
        self.assertEqual(row.assets, 9000)

    def test_resolves_missing_corp_code_from_ticker(self) -> None:
        http = CorpCodeHttpClient(
            corp_xml_rows=[("005930", "00126380")],
            statements=[
                {
                    "status": "000",
                    "list": [
                        {"account_nm": "매출액", "thstrm_amount": "1000"},
                        {"account_nm": "영업이익", "thstrm_amount": "200"},
                        {"account_nm": "당기순이익", "thstrm_amount": "150"},
                    ],
                }
            ],
        )
        provider = OpenDartProvider(api_key="test-key", http_client=http)

        row = provider.fetch_annual_financials(Security(ticker="005930", market="KOSPI"), 2024)

        self.assertEqual(row.revenue, 1000)
        self.assertEqual(len(http.bytes_calls), 1)
        self.assertEqual(http.json_calls[0]["corp_code"], "00126380")

    def test_caches_corp_code_download(self) -> None:
        http = CorpCodeHttpClient(
            corp_xml_rows=[("005930", "00126380")],
            statements=[
                {"status": "000", "list": [{"account_nm": "매출액", "thstrm_amount": "1000"}]},
                {"status": "000", "list": [{"account_nm": "매출액", "thstrm_amount": "1100"}]},
            ],
        )
        provider = OpenDartProvider(api_key="test-key", http_client=http)
        security = Security(ticker="005930", market="KOSPI")

        provider.fetch_annual_financials(security, 2024)
        provider.fetch_annual_financials(security, 2023)

        self.assertEqual(len(http.bytes_calls), 1)
        self.assertEqual(http.json_calls[0]["corp_code"], "00126380")
        self.assertEqual(http.json_calls[1]["corp_code"], "00126380")


if __name__ == "__main__":
    unittest.main()
