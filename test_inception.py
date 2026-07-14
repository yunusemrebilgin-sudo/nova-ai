import inspect
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pandas as pd

import app
import inception
import user_store


NOW = datetime(2026, 7, 14, 12, 0, tzinfo=app.app_timezone())


def snapshot(symbol="ASTOR.IS", expected=7.1):
    return {"symbol": symbol, "horizon": "1-5 gün", "price": 100, "market_data_time": "2026-07-14",
            "expected_return": expected, "target_1": 110, "target_2": 115, "stop_loss": 94,
            "nova_score": 80, "confidence": 85, "indicators": {"rsi": 55}, "sector": "Enerji", "market_state": "Pozitif"}


def frame(high=108, low=96, close=105):
    return pd.DataFrame({"Open": [100, 102], "High": [102, high], "Low": [99, low], "Close": [101, close], "Volume": [1000, 1200]},
                        index=pd.to_datetime(["2026-07-14", "2026-07-15"]))


def scan_row(expected=4.2):
    return {"Son Fiyat": 105, "Beklenen Getiri %": expected, "Direnç": 111, "Trend": "Pozitif", "Nova Score": 82,
            "AI Güven Endeksi": 87, "_market_data_time": "2026-07-15T00:00:00"}


class InceptionTests(unittest.TestCase):
    def test_dashboard_record_can_be_added(self):
        active, added = inception.add_record([], snapshot(), "Dashboard", NOW)
        self.assertTrue(added); self.assertEqual(active[0]["source"], "Dashboard")

    def test_scanner_record_can_be_added(self):
        active, _ = inception.add_record([], snapshot(), "Smart Scanner", NOW)
        self.assertEqual(active[0]["source"], "Smart Scanner")

    def test_duplicate_active_symbol_is_rejected(self):
        active, _ = inception.add_record([], snapshot(), "Dashboard", NOW)
        same, added = inception.add_record(active, snapshot(), "Smart Scanner", NOW)
        self.assertFalse(added); self.assertIs(same, active)

    def test_completed_symbol_can_be_added_again(self):
        active, _ = inception.add_record([], snapshot(), "Dashboard", NOW)
        completed = inception.complete_record(active[0], "test", NOW)
        new_active, added = inception.add_record([], snapshot(), "Dashboard", NOW + timedelta(days=1))
        self.assertTrue(added); self.assertNotEqual(completed["id"], new_active[0]["id"])

    def test_initial_values_are_immutable_during_update(self):
        record = inception.create_record(snapshot(), "Dashboard", NOW)
        updated = inception.update_record(record, scan_row(3.3), frame(), NOW + timedelta(days=1))
        self.assertEqual(updated["initial"]["expected_return"], 7.1)
        self.assertEqual(updated["initial"]["target_1"], 110)
        self.assertEqual(updated["initial"]["stop_loss"], 94)
        self.assertEqual(updated["dynamic"]["expected_return"], 3.3)

    def test_trading_day_counter(self):
        self.assertEqual(inception.trading_days("2026-07-10T12:00:00+03:00", datetime(2026, 7, 14)), 2)

    def test_target_progress_and_max_adverse(self):
        updated = inception.update_record(inception.create_record(snapshot(), "Dashboard", NOW), scan_row(), frame(low=90), NOW + timedelta(days=1))
        self.assertEqual(updated["dynamic"]["target_progress_pct"], 50.0)
        self.assertEqual(updated["dynamic"]["max_adverse_pct"], -10.0)

    def test_ohlc_detects_target_and_stop(self):
        updated = inception.update_record(inception.create_record(snapshot(), "Dashboard", NOW), scan_row(), frame(high=112, low=92), NOW)
        self.assertTrue(updated["dynamic"]["target_touched"]); self.assertTrue(updated["dynamic"]["stop_touched"])
        self.assertIn("sıralama belirsiz", updated["dynamic"]["touch_order"])

    def test_completed_record_enters_report_metrics(self):
        record = inception.update_record(inception.create_record(snapshot(), "Dashboard", NOW), scan_row(), frame(), NOW)
        completed = inception.complete_record(record, "Kullanıcı tamamladı", NOW)
        self.assertEqual(inception.report_metrics([completed])["total"], 1)

    def test_automatic_completion_reasons(self):
        record = inception.update_record(inception.create_record(snapshot(), "Dashboard", NOW), scan_row(), frame(high=112, low=97), NOW)
        self.assertEqual(inception.automatic_completion_reason(record), "İlk hedef gerçekleşti")
        record["dynamic"].update({"target_touched": False, "stop_touched": False, "remaining_days": 0})
        self.assertEqual(inception.automatic_completion_reason(record), "Vade sona erdi")

    def test_confidence_horizon_and_source_grouping(self):
        record = inception.complete_record(inception.update_record(inception.create_record(snapshot(), "Dashboard", NOW), scan_row(), frame(), NOW), "x", NOW)
        self.assertEqual(inception.group_metrics([record], lambda r: r["horizon"])[0]["Grup"], "1-5 gün")
        self.assertEqual(inception.group_metrics([record], lambda r: r["source"])[0]["Grup"], "Dashboard")

    def test_five_minute_update_control(self):
        meta = [{"kind": "update", "last_success_at": NOW.isoformat()}]
        self.assertFalse(app.inception_update_due(meta, NOW + timedelta(minutes=4, seconds=59)))
        self.assertTrue(app.inception_update_due(meta, NOW + timedelta(minutes=5)))

    def test_update_downloads_once_per_active_symbol_and_never_scans_market(self):
        records = [inception.create_record(snapshot("AAA.IS"), "Dashboard", NOW), inception.create_record(snapshot("BBB.IS"), "Dashboard", NOW)]
        downloader = Mock(return_value=frame())
        with patch("app.nova_scanner._scan_row", return_value=scan_row()):
            updated, success, _ = app.update_inception_records(records, NOW + timedelta(days=1), downloader)
        self.assertTrue(success); self.assertEqual(len(updated), 2); self.assertEqual(downloader.call_count, 2)
        self.assertNotIn("scan_smart_market", inspect.getsource(app.update_inception_records))

    def test_failed_update_preserves_old_records(self):
        records = [inception.create_record(snapshot(), "Dashboard", NOW)]
        updated, success, _ = app.update_inception_records(records, NOW, Mock(return_value=pd.DataFrame()))
        self.assertFalse(success); self.assertIs(updated, records)

    def test_old_supabase_snapshot_gets_safe_inception_defaults(self):
        response = Mock(); response.json.return_value = [{"open_positions": [], "closed_trades": [], "ai_watchlist": [{"symbol": "ASTOR.IS"}]}]
        with patch.object(user_store, "supabase_enabled", return_value=True), patch.object(user_store, "_rest", return_value=response):
            loaded = user_store.load_user_portfolio_data("kullanici1")
        self.assertEqual(loaded["ai_watchlist"], [{"symbol": "ASTOR.IS"}])
        self.assertEqual(loaded["inception_active"], []); self.assertEqual(loaded["inception_history"], [])

    def test_protected_modules_do_not_reference_inception_engine(self):
        self.assertNotIn("nova_inception", inspect.getsource(app.render_portfolios_page))
        self.assertNotIn("nova_inception", inspect.getsource(app.render_yeb_pro_page))

    def test_dashboard_old_watchlist_tab_is_replaced(self):
        source = inspect.getsource(app.render_dashboard_page)
        self.assertIn("Inception / Analiz Raporu", source)
        self.assertNotIn("render_pro_ai_watchlist(", source)


if __name__ == "__main__":
    unittest.main()
