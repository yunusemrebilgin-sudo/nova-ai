import inspect
import math
import unittest

import pandas as pd

import app
import scanner


class PortfolioReleaseTests(unittest.TestCase):
    def test_scanner_carries_existing_price_evidence(self):
        length = 100
        frame = pd.DataFrame({
            "Open": [100 + i * 0.1 for i in range(length)],
            "High": [101 + i * 0.1 for i in range(length)],
            "Low": [99 + i * 0.1 for i in range(length)],
            "Close": [100 + i * 0.1 + math.sin(i) for i in range(length)],
            "Volume": [1_000_000 + i * 100 for i in range(length)],
        })
        result = scanner._scan_row("TEST.IS", "Test", frame)
        self.assertIsNotNone(result)
        self.assertEqual(result["_portfolio_price_series"], frame["Close"].astype(float).tolist())

    def test_portfolio_adapter_uses_embedded_evidence_only(self):
        table = pd.DataFrame([{
            "Hisse": "TEST.IS", "AI Güven Endeksi": 70, "Beklenen Getiri %": 8,
            "Sat Riski %": 30, "Volatilite": 2,
            "_portfolio_price_series": [100.0, 99.0, 101.0],
        }])
        prepared = app.prepare_portfolio_scanner_candidates(table, {"TEST.IS": "Teknoloji"})
        self.assertEqual(prepared[0]["price_series"], [100.0, 99.0, 101.0])
        self.assertIsNotNone(prepared[0]["downside_deviation"])

    def test_portfolio_page_does_not_download_or_rescan(self):
        source = inspect.getsource(app.render_portfolios_page)
        self.assertNotIn("download_price_data", source)
        self.assertNotIn("scan_smart_market", source)
        self.assertNotIn("yf.download", source)

    def test_nonfinite_metrics_render_as_dash(self):
        self.assertEqual(app._portfolio_display_number(None), "-")
        self.assertEqual(app._portfolio_display_number(math.nan), "-")
        self.assertEqual(app._portfolio_display_number(math.inf), "-")

    def test_release_copy_has_no_advice_or_guarantee_language(self):
        source = inspect.getsource(app.render_portfolios_page) + inspect.getsource(app.render_portfolio_ranked_results)
        for forbidden in ("kesin kazanç", "önerilen portföy", "garantili"):
            self.assertNotIn(forbidden, source.casefold())

    def test_cards_use_responsive_grid_and_long_text_wrapping(self):
        source = inspect.getsource(app.render_portfolio_ranked_results)
        self.assertIn("auto-fit", source)
        self.assertIn("overflow-wrap:anywhere", source)


if __name__ == "__main__":
    unittest.main()
