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
            "nova_score": 80, "confidence": 85, "indicators": {"rsi": 55}, "sector": "Enerji", "market_state": "Pozitif",
            "critical_window_start": 3, "critical_window_end": 5}


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

    def test_smart_scanner_record_rejects_null_critical_window(self):
        invalid = snapshot()
        invalid["critical_window_start"] = None
        invalid["critical_window_end"] = None
        with self.assertRaises(ValueError):
            inception.add_record([], invalid, "Smart Scanner", NOW)

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
        self.assertEqual(updated["initial"]["critical_window_start"], 3)
        self.assertEqual(updated["initial"]["critical_window_end"], 5)
        self.assertEqual(updated["dynamic"]["expected_return"], 3.3)

    def test_trading_day_counter(self):
        self.assertEqual(inception.trading_days("2026-07-10T12:00:00+03:00", datetime(2026, 7, 14)), 2)

    def test_elapsed_days_uses_actual_market_frame_sessions(self):
        market_sessions = frame()
        market_sessions.index = pd.to_datetime(["2026-07-14", "2026-07-17"])
        updated = inception.update_record(
            inception.create_record(snapshot(), "Dashboard", NOW),
            scan_row(),
            market_sessions,
            (NOW + timedelta(days=3)).replace(hour=19),
        )
        self.assertEqual(updated["dynamic"]["elapsed_days"], 1)

    def test_friday_after_close_counts_completed_monday_as_first_session(self):
        added = datetime(2026, 7, 10, 19, 0, tzinfo=app.app_timezone())
        raw = frame(); raw.index = pd.to_datetime(["2026-07-10", "2026-07-13"])
        updated = inception.update_record(
            inception.create_record(snapshot(), "Dashboard", added), scan_row(), raw,
            datetime(2026, 7, 13, 18, 5, tzinfo=app.app_timezone()),
        )
        self.assertEqual(updated["dynamic"]["elapsed_days"], 1)

    def test_saturday_add_counts_completed_monday_as_first_session(self):
        added = datetime(2026, 7, 11, 12, 0, tzinfo=app.app_timezone())
        raw = frame(); raw.index = pd.to_datetime(["2026-07-10", "2026-07-13"])
        updated = inception.update_record(
            inception.create_record(snapshot(), "Dashboard", added), scan_row(), raw,
            datetime(2026, 7, 13, 18, 5, tzinfo=app.app_timezone()),
        )
        self.assertEqual(updated["dynamic"]["elapsed_days"], 1)

    def test_first_session_after_holiday_counts_as_one(self):
        added = datetime(2026, 7, 15, 12, 0, tzinfo=app.app_timezone())
        raw = frame(); raw.index = pd.to_datetime(["2026-07-14", "2026-07-16"])
        updated = inception.update_record(
            inception.create_record(snapshot(), "Dashboard", added), scan_row(), raw,
            datetime(2026, 7, 16, 18, 5, tzinfo=app.app_timezone()),
        )
        self.assertEqual(updated["dynamic"]["elapsed_days"], 1)

    def test_only_starting_session_remains_zero(self):
        added = datetime(2026, 7, 14, 19, 0, tzinfo=app.app_timezone())
        raw = frame().iloc[:1]
        updated = inception.update_record(
            inception.create_record(snapshot(), "Dashboard", added), scan_row(), raw, added,
        )
        self.assertEqual(updated["dynamic"]["elapsed_days"], 0)

    def test_open_current_session_bar_is_not_counted(self):
        added = datetime(2026, 7, 14, 19, 0, tzinfo=app.app_timezone())
        raw = frame(); raw.index = pd.to_datetime(["2026-07-14", "2026-07-15"])
        updated = inception.update_record(
            inception.create_record(snapshot(), "Dashboard", added), scan_row(), raw,
            datetime(2026, 7, 15, 12, 0, tzinfo=app.app_timezone()),
        )
        self.assertEqual(updated["dynamic"]["elapsed_days"], 0)

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

    def test_same_day_daily_bar_is_not_excluded_by_added_time(self):
        added_at = NOW.replace(hour=23, minute=7)
        records = [inception.create_record(snapshot(), "Smart Scanner", added_at)]
        same_day_frame = frame().iloc[:1]
        with patch("app.nova_scanner._scan_row", return_value=scan_row()):
            updated, success, _ = app.update_inception_records(records, added_at, Mock(return_value=same_day_frame))
        self.assertTrue(success)
        self.assertEqual(updated[0]["dynamic"]["expected_return"], 4.2)

    def test_scanner_table_uses_component_event_for_row_add(self):
        source = inspect.getsource(app.render_nova_bist_table)
        self.assertNotIn("scanner_add_batch", source)
        self.assertIn("data-add-symbol", source)
        self.assertIn("SCANNER_TABLE_COMPONENT(", source)
        self.assertIn("render_scanner_watchlist_add([str(result.add)]", source)

    def test_scanner_main_tables_enable_inception_without_separate_list(self):
        source = inspect.getsource(app.render_smart_scanner_page)
        self.assertIn('table_key="smart_scanner_top10"', source)
        self.assertIn('table_key="smart_scanner_full"', source)
        self.assertNotIn("Inception’a Hisse Ekle", source)
        self.assertNotIn("smart_scanner_row_add_", source)

    def test_scanner_batch_add_reuses_complete_results_before_safe_refresh(self):
        source = inspect.getsource(app.render_scanner_watchlist_add)
        self.assertIn('st.session_state.get("smart_scanner_results"', source)
        self.assertLess(source.index("smart_scanner_follow_badge(scan_row"), source.index("download_price_data"))
        self.assertEqual(source.count("save_current_user_pro_data()"), 1)

    def test_scanner_coarse_horizon_normalizes_to_dashboard_horizon(self):
        self.assertEqual(app.normalize_follow_window_horizon("1-5 gün"), "Günlük işlem")

    def test_shared_engine_preserves_daily_volatility_split(self):
        base = {"MOMENTUM10": 0, "EMA20": 100, "EMA50": 99, "Close": 101, "ADX14": 20}
        with patch("app.follow_window_visual", return_value=(40, 20)):
            low = app.build_follow_window_badge(horizon="1-5 gün", latest=pd.Series({**base, "VOLATILITY20": 2}), score=60, confidence=70, expected_return=6, sell_probability=40)
            high = app.build_follow_window_badge(horizon="Günlük işlem", latest=pd.Series({**base, "VOLATILITY20": 5}), score=60, confidence=70, expected_return=6, sell_probability=40)
        self.assertEqual(low["expected_holding_period"], "1-5 işlem günü")
        self.assertEqual(high["expected_holding_period"], "1-3 işlem günü")

    def test_live_five_symbol_windows_match_inception_snapshots(self):
        cases = {
            "EKGYO.IS": (2.0, (36, 13), (2, 3), "2-3. işlem günü"),
            "KRDMA.IS": (2.0, (34, 13), (2, 3), "2-3. işlem günü"),
            "EREGL.IS": (2.0, (37, 12), (2, 3), "2-3. işlem günü"),
            "ISGYO.IS": (5.0, (44, 22), (2, 2), "2. işlem günü"),
            "ASTOR.IS": (5.0, (41, 19), (2, 2), "2. işlem günü"),
        }
        for symbol, (volatility, visual, window, text) in cases.items():
            latest = pd.Series({"VOLATILITY20": volatility, "MOMENTUM10": 0, "EMA20": 100, "EMA50": 99, "Close": 101, "ADX14": 20})
            with patch("app.follow_window_visual", return_value=visual):
                badge = app.build_follow_window_badge(horizon="1-5 gün", latest=latest, score=70, confidence=70, expected_return=6, sell_probability=40)
            self.assertEqual((badge["critical_window_start"], badge["critical_window_end"]), window, symbol)
            self.assertEqual(badge["badge_text"], text, symbol)
            item = snapshot(symbol); item["expected_holding_period"] = badge["expected_holding_period"]
            item["critical_window_start"], item["critical_window_end"] = window
            record = inception.create_record(item, "Smart Scanner", NOW)
            record["dynamic"] = {"elapsed_days": 0}
            self.assertEqual(app.inception_critical_day_state(record)["badge_text"], text, symbol)

    def test_dashboard_holding_period_uses_scanner_calculator(self):
        latest = pd.Series({"VOLATILITY20": 2.0})
        with patch("app.nova_analytics.expected_holding_period", return_value="1-5 işlem günü") as calculator:
            self.assertEqual(app.expected_holding_period(latest, "Günlük işlem"), "1-5 işlem günü")
        calculator.assert_called_once_with(latest, "Günlük işlem")

    def test_scanner_missing_holding_period_uses_shared_calculator(self):
        row = {"Volatilite": 2.0, "Nova Score": 70, "AI Güven Endeksi": 70, "Beklenen Getiri %": 6, "Sat Riski %": 40,
               "_follow_momentum10": 0, "_follow_ema20": 100, "_follow_ema50": 99, "_follow_close": 101, "_follow_adx14": 20}
        with patch("app.follow_window_visual", return_value=(40, 20)):
            badge = app.smart_scanner_follow_badge(row, "1-5 gün")
        self.assertEqual((badge["critical_window_start"], badge["critical_window_end"]), (3, 3))

    def test_scanner_add_is_blocked_when_window_cannot_be_resolved(self):
        self.assertIsNone(app.smart_scanner_follow_badge({}, "Günlük işlem"))
        source = inspect.getsource(app.render_scanner_watchlist_add)
        self.assertLess(source.index("if follow_badge is None"), source.index("nova_inception.add_record"))
        self.assertIn("Inception kaydı oluşturulmadı", source)

    def test_failed_update_preserves_old_records(self):
        records = [inception.create_record(snapshot(), "Dashboard", NOW)]
        updated, success, _ = app.update_inception_records(records, NOW, Mock(return_value=pd.DataFrame()))
        self.assertFalse(success); self.assertIs(updated, records)

    def test_old_wrong_scanner_snapshot_is_migrated_per_symbol(self):
        record = inception.create_record(snapshot("EKGYO.IS"), "Smart Scanner", NOW)
        record["initial"]["critical_window_start"] = 3
        record["initial"]["critical_window_end"] = 3
        row = {**scan_row(), "Volatilite": 2.0, "Sat Riski %": 40,
               "_follow_momentum10": 0, "_follow_ema20": 100, "_follow_ema50": 99,
               "_follow_close": 101, "_follow_adx14": 20}
        with patch("app.nova_scanner._scan_row", return_value=row), patch("app.follow_window_visual", return_value=(36, 13)):
            updated, success, _ = app.update_inception_records([record], NOW.replace(hour=19), Mock(return_value=frame()))
        self.assertTrue(success)
        self.assertEqual((updated[0]["initial"]["critical_window_start"], updated[0]["initial"]["critical_window_end"]), (2, 3))

    def test_migration_missing_market_data_preserves_record(self):
        record = inception.create_record(snapshot("EKGYO.IS"), "Smart Scanner", NOW)
        updated, success, _ = app.update_inception_records([record], NOW, Mock(return_value=pd.DataFrame()))
        self.assertFalse(success)
        self.assertIs(updated[0], record)

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

    def test_dashboard_navigation_uses_callbacks_not_post_widget_state_mutation(self):
        source = inspect.getsource(app.render_dashboard_page)
        self.assertIn("on_click=navigate_to_page", source)
        self.assertNotIn("st.session_state.selected_page =", source)

    def test_inception_uses_compact_tracking_strips_not_dataframe(self):
        page_source = inspect.getsource(app.render_inception_page)
        strip_source = inspect.getsource(app.render_inception_tracking_strips)
        self.assertNotIn("st.dataframe(", page_source)
        self.assertIn("render_inception_tracking_strips", page_source)
        self.assertIn("nova-inception-track-strip", strip_source)
        self.assertIn("dedent(", strip_source)
        self.assertIn("grid-template-columns:18% 40%", strip_source)
        self.assertIn("@media(max-width:760px)", strip_source)

    def test_inception_missing_values_render_as_dash(self):
        self.assertEqual(app._inception_display_number(None), "—")
        self.assertEqual(app._inception_display_percent(None), "—")

    def test_inception_sorting_and_summary_options_are_present(self):
        source = inspect.getsource(app.render_inception_page)
        for label in ("Hedefe en yakın", "En yüksek gerçekleşen getiri", "En düşük gerçekleşen getiri", "Sembol"):
            self.assertIn(label, source)
        self.assertIn("Hedefe Ulaşan", source)

    def test_inception_critical_day_states_and_pulse_scope(self):
        record = inception.create_record(snapshot(), "Dashboard", NOW)
        expected = {
            0: ("3-5. işlem günü", "neutral", False),
            1: ("2-4. işlem günü", "warning", False),
            2: ("YARIN", "tomorrow", False),
            3: ("BUGÜN", "active", True),
            4: ("AKTİF", "active", False),
            5: ("SON GÜN", "last", True),
            6: ("GEÇTİ", "passed", False),
        }
        for elapsed, state in expected.items():
            record["dynamic"] = {"elapsed_days": elapsed}
            result = app.inception_critical_day_state(record)
            self.assertEqual((result["label"], result["tone"], result["pulse"]), state)

    def test_each_inception_record_uses_its_own_elapsed_day_and_window(self):
        first = inception.create_record(snapshot("EKGYO.IS"), "Dashboard", NOW)
        second_snapshot = snapshot("EREGL.IS")
        second_snapshot["critical_window_start"] = 4
        second_snapshot["critical_window_end"] = 6
        second = inception.create_record(second_snapshot, "Dashboard", NOW)
        first["dynamic"] = {"elapsed_days": 1}
        second["dynamic"] = {"elapsed_days": 1}
        self.assertEqual(app.inception_critical_day_state(first)["label"], "2-4. işlem günü")
        self.assertEqual(app.inception_critical_day_state(second)["label"], "3-5. işlem günü")

    def test_inception_critical_day_missing_snapshot_is_dash(self):
        record = inception.create_record(snapshot(), "Dashboard", NOW)
        record["initial"].pop("critical_window_start")
        self.assertEqual(app.inception_critical_day_state(record)["label"], "—")

    def test_inception_critical_css_is_accessible_and_mobile_safe(self):
        source = inspect.getsource(app.render_inception_tracking_strips)
        self.assertIn("animation:novaCriticalPulse .8s", source)
        self.assertIn("animation:novaTodayCriticalPulse .8s", source)
        self.assertIn("box-shadow:0 0 23.4px currentColor", source)
        self.assertIn(".nova-inception-critical.active.pulse", source)
        self.assertIn("prefers-reduced-motion:reduce", source)
        self.assertNotIn("minmax(300px", source)
        self.assertNotIn("minmax(370px", source)
        self.assertIn("nova-inception-detail", source)
        self.assertIn('<details class="nova-inception-track-strip">', source)

    def test_inception_add_flows_capture_critical_window_snapshot(self):
        dashboard_source = inspect.getsource(app.render_dashboard_page)
        scanner_source = inspect.getsource(app.render_scanner_watchlist_add)
        self.assertIn('"critical_window_start"', dashboard_source)
        self.assertIn('"critical_window_end"', dashboard_source)
        self.assertIn('snapshot["critical_window_start"]', scanner_source)
        self.assertIn('snapshot["critical_window_end"]', scanner_source)


if __name__ == "__main__":
    unittest.main()
