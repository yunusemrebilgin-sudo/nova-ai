import unittest
from unittest.mock import patch

import expected_return_v2


def complete_features(**overrides):
    features = {
        "atr_pct": 3.0,
        "volatility20": 2.5,
        "close": 105.0,
        "ema20": 100.0,
        "ema50": 95.0,
        "ema20_distance_pct": 2.0,
        "adx14": 30.0,
        "rsi14": 55.0,
        "rsi_direction": 1.0,
        "macd": 2.0,
        "macd_signal": 1.0,
        "macd_histogram": 0.8,
        "macd_histogram_direction": 0.2,
        "momentum10": 4.0,
        "momentum_change": 1.0,
        "return_1d_pct": 1.0,
        "return_3d_pct": 3.0,
        "return_5d_pct": 5.0,
        "volume_ratio": 1.30,
        "support": 95.0,
        "resistance": 110.0,
        "resistance_distance_pct": 4.76,
        "previous_20_close_resistance": 104.0,
        "breakout_confirmed": False,
        "nova_score": 80.0,
        "confidence": 80.0,
        "entry_timing_score": 85.0,
        "entry_timing_classification": "GİRİŞ UYGUN",
        "price_series_length": 60,
        "selected_horizon": "10-30 gün",
        "horizon_mapping": expected_return_v2.resolve_expected_return_horizon("10-30 gün"),
        "missing_data": [],
        "critical_missing_data": [],
    }
    features.update(overrides)
    return features


class ExpectedReturnV2Tests(unittest.TestCase):
    def test_strong_trend_balanced_momentum_and_entry_produce_high_positive_return(self):
        result = expected_return_v2.calculate_expected_return_v2(complete_features())
        self.assertGreater(result["main_expected_return"], 6.0)
        self.assertGreaterEqual(result["directional_quality_score"], 80)

    def test_late_entry_and_high_rsi_reduce_expected_return(self):
        balanced = expected_return_v2.calculate_expected_return_v2(complete_features())
        late = expected_return_v2.calculate_expected_return_v2(
            complete_features(
                rsi14=78.0,
                return_1d_pct=7.0,
                return_3d_pct=9.0,
                return_5d_pct=13.0,
                ema20_distance_pct=9.0,
            )
        )
        self.assertLess(late["main_expected_return"], balanced["main_expected_return"])
        self.assertEqual(late["debug"]["entry_timing"]["late_entry_penalty"], -5.0)

    def test_near_resistance_without_breakout_limits_return(self):
        result = expected_return_v2.calculate_expected_return_v2(
            complete_features(resistance_distance_pct=1.0, breakout_confirmed=False)
        )
        self.assertEqual(result["resistance_adjustment"], -1.0)
        self.assertIn("Ana dirence %1.5'ten az mesafe var ve breakout teyidi yok", result["limiting_factors"])

    def test_confirmed_close_breakout_gets_limited_contribution(self):
        result = expected_return_v2.calculate_expected_return_v2(
            complete_features(breakout_confirmed=True, resistance_distance_pct=0.5)
        )
        self.assertEqual(result["resistance_adjustment"], 1.5)
        self.assertLessEqual(result["resistance_adjustment"], expected_return_v2.MAX_RESISTANCE_ADJUSTMENT)

    def test_negative_trend_and_weak_momentum_can_produce_negative_return(self):
        result = expected_return_v2.calculate_expected_return_v2(
            complete_features(
                atr_pct=0.5,
                volatility20=7.0,
                close=90.0,
                ema20=100.0,
                ema50=105.0,
                ema20_distance_pct=-10.0,
                adx14=10.0,
                rsi14=76.0,
                macd=-2.0,
                macd_signal=-1.0,
                macd_histogram=-0.5,
                macd_histogram_direction=-0.2,
                momentum10=-5.0,
                momentum_change=-2.0,
                volume_ratio=0.6,
                confidence=40.0,
                entry_timing_score=20.0,
                resistance_distance_pct=1.0,
            )
        )
        self.assertLess(result["main_expected_return"], 0.0)

    def test_missing_atr_produces_no_numeric_expected_return(self):
        result = expected_return_v2.calculate_expected_return_v2(
            complete_features(atr_pct=None, missing_data=["ATR%"], critical_missing_data=["ATR%"])
        )
        self.assertIsNone(result["main_expected_return"])
        self.assertIsNone(result["conservative_expected_return"])
        self.assertIn("ATR% eksik olduğu için sayısal beklenen getiri üretilemedi", result["warnings"])

    def test_more_missing_data_lowers_confidence_and_widens_range(self):
        complete = expected_return_v2.calculate_expected_return_v2(complete_features())
        incomplete = expected_return_v2.calculate_expected_return_v2(
            complete_features(
                rsi_direction=None,
                momentum_change=None,
                macd_histogram_direction=None,
                resistance=None,
                volume_ratio=None,
                price_series_length=20,
                missing_data=["RSI yönü", "Momentum değişimi", "MACD Histogram yönü", "Ana direnç", "Volume Ratio"],
                critical_missing_data=[
                    "RSI yönü",
                    "Momentum değişimi",
                    "MACD Histogram yönü",
                    "Ana direnç",
                    "Volume Ratio",
                    "En az 30 kapanışlık fiyat geçmişi",
                ],
            )
        )
        self.assertLess(incomplete["model_confidence"], complete["model_confidence"])
        self.assertGreater(incomplete["uncertainty"], complete["uncertainty"])

    def test_conservative_main_optimistic_order_is_preserved(self):
        result = expected_return_v2.calculate_expected_return_v2(complete_features())
        self.assertLessEqual(result["conservative_expected_return"], result["main_expected_return"])
        self.assertLessEqual(result["main_expected_return"], result["optimistic_expected_return"])

    def test_all_numeric_results_stay_inside_bounds(self):
        for atr_pct in (0.1, 3.0, 100.0):
            with self.subTest(atr_pct=atr_pct):
                result = expected_return_v2.calculate_expected_return_v2(complete_features(atr_pct=atr_pct))
                for key in ("conservative_expected_return", "main_expected_return", "optimistic_expected_return"):
                    self.assertGreaterEqual(result[key], -10.0)
                    self.assertLessEqual(result[key], 35.0)

    def test_horizon_mappings_and_fallback(self):
        expected = {
            "1-5 gün": ("1-5 gün", 0.90),
            "5-10 gün": ("5-10 gün", 1.15),
            "10-30 gün": ("10-30 gün", 1.45),
            "1-2 ay": ("1-2 ay", 1.80),
            "2-4 ay": ("2-4 ay", 2.20),
            "Günlük işlem": ("1-5 gün", 0.90),
            "Kısa vade": ("10-30 gün", 1.45),
            "Orta vade": ("1-2 ay", 1.80),
            "Uzun vade": ("2-4 ay", 2.20),
        }
        for requested, (canonical, multiplier) in expected.items():
            with self.subTest(requested=requested):
                mapping = expected_return_v2.resolve_expected_return_horizon(requested)
                self.assertEqual(mapping["canonical"], canonical)
                self.assertEqual(mapping["multiplier"], multiplier)
                self.assertFalse(mapping["fallback_used"])
        fallback = expected_return_v2.resolve_expected_return_horizon("Bilinmeyen vade")
        self.assertEqual(fallback["canonical"], "10-30 gün")
        self.assertTrue(fallback["fallback_used"])
        self.assertIsNotNone(fallback["fallback_message"])

    def test_feature_builder_reuses_scanner_row_and_entry_timing_result(self):
        timing = {
            "score": 72,
            "classification": "KADEMELİ GİRİŞ",
            "features": {
                "close": 101.0,
                "atr_pct": 2.0,
                "volatility20": 3.0,
                "resistance": 105.0,
                "volume_ratio": 1.2,
                "macd_histogram": 0.4,
                "previous_macd_histogram": 0.2,
            },
        }
        row = {
            "Beklenen Getiri %": 8.5,
            "_portfolio_price_series": list(range(60, 101)),
            "_market_data_time": "2026-07-16T18:00:00+03:00",
        }
        features = expected_return_v2.build_expected_return_v2_features(row, "Kısa vade", timing)
        self.assertEqual(features["entry_timing_score"], 72.0)
        self.assertEqual(features["current_expected_return"], 8.5)
        self.assertEqual(features["price_series_length"], 41)
        self.assertEqual(features["horizon_mapping"]["canonical"], "10-30 gün")

    def test_user2_cannot_render_yebora_lab(self):
        import app

        with patch.object(app, "current_auth_user", return_value="user2"), patch.object(app.st, "container") as container:
            app.render_yebora_lab()
        container.assert_not_called()


if __name__ == "__main__":
    unittest.main()
