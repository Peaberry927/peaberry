from __future__ import annotations

import unittest

from app.models import Security
from app.providers.naver import NaverFinanceProvider


class StubNaverHttp:
    def __init__(self, html: str) -> None:
        self.html = html

    def get_text(self, url: str, params: dict[str, str] | None = None) -> str:
        return self.html


class NaverProviderTests(unittest.TestCase):
    def test_fetch_annual_metrics_parses_estimated_columns(self) -> None:
        html = """
        <table class="tb_type1 tb_num tb_type1_ifrs">
          <thead>
            <tr><th>주요재무정보</th></tr>
            <tr>
              <th>2023.12</th>
              <th>2024.12</th>
              <th>2025.12</th>
              <th>2026.12<em>(E)</em></th>
              <th>2025.03</th>
            </tr>
          </thead>
          <tbody>
            <tr><th>매출액</th><td>100</td><td>110</td><td>120</td><td>130</td><td>10</td></tr>
            <tr><th>영업이익</th><td>10</td><td>11</td><td>12</td><td>13</td><td>1</td></tr>
            <tr><th>당기순이익</th><td>7</td><td>8</td><td>9</td><td>10</td><td>1</td></tr>
            <tr><th>EPS(원)</th><td>700</td><td>800</td><td>900</td><td>1000</td><td>100</td></tr>
            <tr><th>PER(배)</th><td>9</td><td>8</td><td>7</td><td>6</td><td>5</td></tr>
            <tr><th>BPS(원)</th><td>2000</td><td>2100</td><td>2200</td><td>2300</td><td>200</td></tr>
            <tr><th>PBR(배)</th><td>3</td><td>2.8</td><td>2.6</td><td>2.5</td><td>2.4</td></tr>
          </tbody>
        </table>
        """
        provider = NaverFinanceProvider(http_client=StubNaverHttp(html))
        rows = provider.fetch_annual_metrics(Security(ticker="005930", market="KOSPI"))

        self.assertEqual([row.year for row in rows], [2023, 2024, 2025, 2026])
        self.assertTrue(rows[-1].is_estimate)
        self.assertEqual(rows[0].revenue, 100 * 100_000_000)
        self.assertEqual(rows[-1].eps, 1000)
        self.assertEqual(rows[-1].per, 6)

    def test_fetch_valuation_fields_includes_consensus_values(self) -> None:
        html = """
        <div><em id="_per">10.5</em><em id="_pbr">1.2</em></div>
        <table><tr><th>EPS</th><td>1,234</td></tr><tr><th>BPS</th><td>11,111</td></tr></table>
        <div><em id="_cns_per">8.7</em><em id="_cns_eps">20,000</em></div>
        """
        provider = NaverFinanceProvider(http_client=StubNaverHttp(html))
        fields = provider.fetch_valuation_fields(Security(ticker="005930", market="KOSPI"))

        self.assertEqual(fields.per, 10.5)
        self.assertEqual(fields.pbr, 1.2)
        self.assertEqual(fields.eps, 1234)
        self.assertEqual(fields.bps, 11111)
        self.assertEqual(fields.estimated_per, 8.7)
        self.assertEqual(fields.estimated_eps, 20000)


if __name__ == "__main__":
    unittest.main()
