import inspect
import math
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pandas as pd

import app
import scanner


def price_frame(last_close_adjustment: float = 0.0) -> pd.DataFrame:
    length = 100
    close = [100 + index * 0.2 + math.sin(index) * 1.5 for index in range(length)]
    close[-1] += last_close_adjustment
    return pd.DataFrame(
        {
            "Open": close,
            "High": [value + 1.0 for value in close],
            "Low": [value - 1.0 for value in close],
            "Close": close,
            "Volume": [1_000_000 + index * 1_000 for index in range(length)],
        },
        index=pd.date_range("2026-01-01", periods=length, freq="D"),
    )


class SmartScannerRefreshTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 7, 14, 12, 0, tzinfo=app.app_timezone())

    @patch("scanner.news.news_impact_percent", return_value=0.0)
    @patch("scanner.download_price_data")
    def test_first_successful_scan_calculates_expected_return(self, download, _news):
        download.return_value = price_frame()
        with patch("scanner.analytics.expected_return", wraps=scanner.analytics.expected_return) as expected:
            table, failed, timed_out, count = scanner.scan_smart_market(
                (("TEST.IS", "Test"),), scan_id="scan-1"
            )
        self.assertFalse(table.empty)
        self.assertEqual((failed, timed_out, count), ([], False, 1))
        expected.assert_called_once()

    @patch("scanner.news.news_impact_percent", return_value=0.0)
    @patch("scanner.download_price_data")
    def test_same_symbol_and_horizon_recalculate_after_new_scan(self, download, _news):
        download.side_effect = [price_frame(), price_frame(8.0)]
        with patch("scanner.analytics.expected_return", side_effect=[7.1, 3.4]) as expected:
            first = scanner.scan_smart_market((("TEST.IS", "Test"),), "1-5 gün", scan_id="scan-1")[0]
            second = scanner.scan_smart_market((("TEST.IS", "Test"),), "1-5 gün", scan_id="scan-2")[0]
        self.assertEqual(expected.call_count, 2)
        self.assertEqual(first.iloc[0]["Beklenen Getiri %"], 7.1)
        self.assertEqual(second.iloc[0]["Beklenen Getiri %"], 3.4)

    def test_scan_symbol_has_no_stale_row_cache(self):
        self.assertFalse(hasattr(scanner.scan_smart_symbol, "clear"))
        self.assertNotIn("@st.cache_data", inspect.getsource(scanner.scan_smart_symbol))

    @patch("scanner.news.news_impact_percent", return_value=0.0)
    @patch("scanner.download_price_data")
    def test_one_download_per_symbol_inside_one_scan(self, download, _news):
        download.return_value = price_frame()
        scanner.scan_smart_market((("AAA.IS", "A"), ("BBB.IS", "B")), scan_id="one-scan")
        self.assertEqual(download.call_count, 2)
        self.assertEqual({call.args[1] for call in download.call_args_list}, {"one-scan"})

    def test_market_data_time_comes_from_price_frame_index(self):
        result = scanner._scan_row("TEST.IS", "Test", price_frame())
        self.assertEqual(result["_market_data_time"], pd.Timestamp("2026-04-10").isoformat())

    def test_same_data_is_deterministic(self):
        with patch("scanner.news.news_impact_percent", return_value=0.0):
            first = scanner._scan_row("TEST.IS", "Test", price_frame())
            second = scanner._scan_row("TEST.IS", "Test", price_frame())
        self.assertEqual(first["Beklenen Getiri %"], second["Beklenen Getiri %"])

    def test_cooldown_blocks_before_five_minutes_and_rounds_up(self):
        last = self.now - timedelta(seconds=1)
        self.assertEqual(app.smart_scan_cooldown_minutes(last, self.now), 5)
        last = self.now - timedelta(minutes=4, seconds=1)
        self.assertEqual(app.smart_scan_cooldown_minutes(last, self.now), 1)

    def test_cooldown_allows_after_five_minutes(self):
        self.assertEqual(app.smart_scan_cooldown_minutes(self.now - timedelta(minutes=5), self.now), 0)

    def test_success_updates_results_and_all_time_metadata(self):
        state = {}
        table = pd.DataFrame([{"Beklenen Getiri %": 4.2, "_market_data_time": "2026-07-14T00:00:00"}])
        stored = app.store_successful_smart_scan(state, table, [], 1, "1-5 gün", self.now)
        self.assertTrue(stored)
        self.assertIs(state["smart_scanner_results"], table)
        self.assertEqual(state["smart_scanner_last_success_at"], self.now.isoformat())
        self.assertEqual(state["smart_scanner_market_data_time"], "2026-07-14T00:00:00")
        self.assertEqual(state["smart_scanner_result_status"], "current")

    def test_failed_scan_preserves_old_result_without_new_time(self):
        old_table = pd.DataFrame([{"Beklenen Getiri %": 7.1}])
        state = {"smart_scanner_results": old_table, "smart_scanner_last_success_at": "old-time"}
        app.mark_smart_scan_failed(state)
        self.assertIs(state["smart_scanner_results"], old_table)
        self.assertEqual(state["smart_scanner_last_success_at"], "old-time")
        self.assertEqual(state["smart_scanner_result_status"], "preserved")

    def test_empty_scan_does_not_start_cooldown(self):
        state = {}
        stored = app.store_successful_smart_scan(state, pd.DataFrame(), [], 0, "1-5 gün", self.now)
        self.assertFalse(stored)
        self.assertNotIn("smart_scanner_last_success_at", state)

    def test_partial_timed_out_scan_is_not_successful(self):
        table = pd.DataFrame([{"Beklenen Getiri %": 4.2}])
        self.assertFalse(app.smart_scan_result_is_successful(table, timed_out=True))
        self.assertTrue(app.smart_scan_result_is_successful(table, timed_out=False))

    def test_filtering_and_scope_values_do_not_start_cooldown(self):
        state = {}
        table = pd.DataFrame([{
            "Trend": "Pozitif", "MACD": 1.0, "Nova Score": 80, "AI Güven Endeksi": 70,
            "EMA20 > EMA50": True, "RSI": 55, "Hacim Oranı": 1.2, "Volatilite": 2.0,
        }])
        scanner.apply_filters(table, "Tümü", "Tümü", 0, 0, False, "Tümü", (0, 100), 0.0, 15.0)
        _ = app.SMART_SCAN_MODES["Hızlı Tarama: İlk 50 hisse"]
        self.assertNotIn("smart_scanner_last_success_at", state)

    def test_render_path_only_scans_inside_button_guard(self):
        source = inspect.getsource(app.render_smart_scanner_page)
        button_guard = source.index("if scan_requested:")
        scan_call = source.index("run_smart_market_scan(", button_guard)
        results_read = source.index('st.session_state.get("smart_scanner_results"', scan_call)
        self.assertLess(button_guard, scan_call)
        self.assertLess(scan_call, results_read)

    def test_old_scanner_signature_clears_stale_caches_before_retry(self):
        old_market_scan = Mock(side_effect=[TypeError("unexpected keyword argument 'scan_id'"), (pd.DataFrame(), [], False, 0)])
        old_symbol_cache = Mock()
        old_download_cache = Mock()
        with patch.object(app.nova_scanner, "scan_smart_market", old_market_scan), \
             patch.object(app.nova_scanner, "scan_smart_symbol", old_symbol_cache), \
             patch.object(app.nova_scanner, "download_price_data", old_download_cache):
            app.run_smart_market_scan(tuple(), "1-5 gün", scan_id="fresh-scan")
        old_symbol_cache.clear.assert_called_once()
        old_download_cache.clear.assert_called_once()
        self.assertEqual(old_market_scan.call_count, 2)


if __name__ == "__main__":
    unittest.main()
