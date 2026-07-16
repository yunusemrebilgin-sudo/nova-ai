import unittest
from unittest.mock import patch

import critical_day_v2
import entry_timing
import expected_return_v2


def complete_features(**overrides):
    features = {
        "selected_horizon": "10-30 gün",
        "critical_day_horizon": critical_day_v2.normalize_critical_day_horizon("10-30 gün"),
        "atr_pct": 4.0,
        "volatility20": 2.0,
        "adx14": 30.0,
        "ema20": 105.0,
        "ema50": 100.0,
        "momentum10": 4.0,
        "momentum_change": 1.0,
        "rsi14": 55.0,
        "rsi_direction": 1.0,
        "macd_histogram": 0.5,
        "macd_histogram_direction": 0.2,
        "return_1d_pct": 1.0,
        "return_3d_pct": 3.0,
        "return_5d_pct": 5.0,
        "entry_timing_score": 85.0,
        "entry_timing_classification": "GİRİŞ UYGUN",
        "conservative_expected_return": 15.0,
        "main_expected_return": 20.0,
        "optimistic_expected_return": 25.0,
        "expected_return_model_confidence": 80.0,
        "directional_quality_score": 85.0,
        "movement_capacity": 5.8,
        "risk_penalty": 1.0,
        "uncertainty": 2.0,
        "confidence": 80.0,
        "resistance": 110.0,
        "resistance_distance_pct": 5.0,
        "breakout_confirmed": True,
        "volume_ratio": 1.3,
        "price_series_length": 60,
        "missing_data": [],
    }
    features.update(overrides)
    return features


class CriticalDayV2Tests(unittest.TestCase):
    def test_strong_trend_and_entry_produce_earlier_main_day(self):
        strong = critical_day_v2.calculate_critical_day_window_v2(complete_features())
        weak = critical_day_v2.calculate_critical_day_window_v2(
            complete_features(
                entry_timing_score=40.0,
                momentum_change=-1.0,
                macd_histogram=-0.2,
                macd_histogram_direction=-0.1,
                breakout_confirmed=False,
                volume_ratio=0.9,
                resistance_distance_pct=1.0,
            )
        )
        self.assertLess(strong["main_day"], weak["main_day"])

    def test_weak_entry_and_resistance_create_visible_delay(self):
        result = critical_day_v2.calculate_critical_day_window_v2(
            complete_features(entry_timing_score=40.0, breakout_confirmed=False, resistance_distance_pct=1.0)
        )
        labels = [item["label"] for item in result["delays"]]
        self.assertIn("Entry Timing Score 35-49", labels)
        self.assertIn("Ana direnç altında ve breakout teyidi yok", labels)
        self.assertGreater(result["debug"]["adjustments"]["delay_days"], 0)

    def test_high_volatility_reduces_capacity_and_widens_window(self):
        calm = critical_day_v2.calculate_critical_day_window_v2(complete_features(volatility20=2.0))
        volatile = critical_day_v2.calculate_critical_day_window_v2(complete_features(volatility20=7.0))
        self.assertLess(volatile["daily_directional_capacity"], calm["daily_directional_capacity"])
        self.assertGreater(volatile["window_half_width"], calm["window_half_width"])

    def test_positive_reachable_target_produces_complete_window(self):
        result = critical_day_v2.calculate_critical_day_window_v2(complete_features())
        self.assertTrue(result["reachability"])
        for key in ("earliest_reasonable_day", "main_day", "window_start", "window_end", "late_day"):
            self.assertIsNotNone(result[key])

    def test_target_beyond_horizon_is_not_forced_to_maximum_day(self):
        result = critical_day_v2.calculate_critical_day_window_v2(
            complete_features(atr_pct=0.5, main_expected_return=35.0, conservative_expected_return=30.0)
        )
        maximum = result["features"]["critical_day_horizon"]["maximum_trading_day"] if "features" in result else 30
        self.assertFalse(result["reachability"])
        self.assertIsNone(result["main_day"])
        self.assertIsNone(result["window_start"])
        self.assertGreater(result["adjusted_reach_day"], maximum)

    def test_nonpositive_main_expectation_produces_no_numeric_window(self):
        result = critical_day_v2.calculate_critical_day_window_v2(
            complete_features(main_expected_return=0.0, conservative_expected_return=-2.0, optimistic_expected_return=2.0)
        )
        self.assertIsNone(result["reachability"])
        self.assertIsNone(result["main_day"])
        self.assertEqual(result["status"], "SAYISAL SONUÇ ÜRETİLEMEDİ")
        self.assertIn("Pozitif hedef için uygun teknik beklenti yok", result["warnings"])

    def test_missing_atr_produces_no_numeric_result_without_error(self):
        result = critical_day_v2.calculate_critical_day_window_v2(
            complete_features(atr_pct=None, missing_data=["ATR%"])
        )
        self.assertIsNone(result["daily_directional_capacity"])
        self.assertIsNone(result["main_day"])
        self.assertIn("ATR% eksik olduğu için sayısal kritik gün üretilemedi", result["warnings"])

    def test_nonpositive_conservative_expectation_uses_horizon_minimum(self):
        result = critical_day_v2.calculate_critical_day_window_v2(
            complete_features(conservative_expected_return=0.0)
        )
        self.assertEqual(result["earliest_reasonable_day"], 10)

    def test_day_order_is_logically_preserved(self):
        result = critical_day_v2.calculate_critical_day_window_v2(complete_features())
        minimum = result["debug"]["normalized_horizon"]["minimum_trading_day"]
        maximum = result["debug"]["normalized_horizon"]["maximum_trading_day"]
        self.assertLessEqual(minimum, result["earliest_reasonable_day"])
        self.assertLessEqual(result["earliest_reasonable_day"], result["window_start"])
        self.assertLessEqual(result["window_start"], result["main_day"])
        self.assertLessEqual(result["main_day"], result["window_end"])
        self.assertLessEqual(result["window_end"], result["late_day"])
        self.assertLessEqual(result["late_day"], maximum)

    def test_earliest_day_is_clamped_to_window_start(self):
        horizon = critical_day_v2.normalize_critical_day_horizon("5-10 gün")
        result = critical_day_v2.calculate_critical_day_window_v2(
            complete_features(
                selected_horizon="5-10 gün",
                critical_day_horizon=horizon,
                atr_pct=2.0,
                directional_quality_score=50.0,
                entry_timing_score=65.0,
                volatility20=2.0,
                adx14=20.0,
                momentum_change=0.0,
                macd_histogram_direction=0.0,
                breakout_confirmed=False,
                volume_ratio=1.0,
                conservative_expected_return=9.0,
                main_expected_return=10.0,
            )
        )
        self.assertTrue(result["reachability"])
        self.assertEqual(result["window_start"], 8)
        self.assertEqual(result["earliest_reasonable_day"], result["window_start"])

    def test_all_generated_days_respect_trading_day_bounds(self):
        for horizon in critical_day_v2.HORIZON_TRADING_DAY_BOUNDS:
            with self.subTest(horizon=horizon):
                mapping = critical_day_v2.normalize_critical_day_horizon(horizon)
                result = critical_day_v2.calculate_critical_day_window_v2(
                    complete_features(selected_horizon=horizon, critical_day_horizon=mapping)
                )
                minimum, maximum = mapping["minimum_trading_day"], mapping["maximum_trading_day"]
                self.assertTrue(result["reachability"])
                for key in ("earliest_reasonable_day", "main_day", "window_start", "window_end", "late_day"):
                    self.assertGreaterEqual(result[key], minimum)
                    self.assertLessEqual(result[key], maximum)

    def test_month_horizons_use_defined_trading_day_bounds(self):
        one_two = critical_day_v2.normalize_critical_day_horizon("1-2 ay")
        two_four = critical_day_v2.normalize_critical_day_horizon("2-4 ay")
        self.assertEqual((one_two["minimum_trading_day"], one_two["maximum_trading_day"]), (20, 40))
        self.assertEqual((two_four["minimum_trading_day"], two_four["maximum_trading_day"]), (40, 80))
        self.assertEqual(
            critical_day_v2.normalize_critical_day_horizon("Orta vade")["canonical"],
            "1-2 ay",
        )

    def test_more_missing_inputs_lower_critical_day_confidence(self):
        complete = critical_day_v2.calculate_critical_day_window_v2(complete_features())
        incomplete = critical_day_v2.calculate_critical_day_window_v2(
            complete_features(
                price_series_length=20,
                momentum_change=None,
                macd_histogram_direction=None,
                volatility20=None,
                entry_timing_score=None,
                resistance=None,
            )
        )
        self.assertLess(incomplete["critical_day_model_confidence"], complete["critical_day_model_confidence"])

    def test_upstream_engine_contracts_remain_available(self):
        self.assertTrue(callable(entry_timing.evaluate_entry_timing))
        self.assertTrue(callable(expected_return_v2.evaluate_expected_return_v2))
        self.assertTrue(callable(critical_day_v2.evaluate_critical_day_v2))

    def test_user2_cannot_render_yebora_lab(self):
        import app

        with patch.object(app, "current_auth_user", return_value="user2"), patch.object(app.st, "container") as container:
            app.render_yebora_lab()
        container.assert_not_called()


if __name__ == "__main__":
    unittest.main()
