import unittest

import entry_timing


def base_features(**overrides):
    values = {
        "close": 102.0, "ema20": 100.0, "ema50": 96.0, "adx14": 30.0,
        "momentum10": 4.0, "previous_momentum10": 2.0,
        "macd": 2.0, "macd_signal": 1.2, "macd_histogram": 0.8,
        "previous_macd_histogram": 0.4, "rsi14": 55.0, "rsi_direction": 1.0,
        "volume_ratio": 1.25, "ema20_distance_pct": 2.0,
        "resistance_distance_pct": 5.0, "bollinger_upper_distance_pct": 3.0,
        "return_1d_pct": 1.0, "return_3d_pct": 3.0, "return_5d_pct": 5.0,
        "volatility20": 2.0, "atr_pct": 2.0, "breakout_confirmed": False,
    }
    values.update(overrides)
    return values


class EntryTimingTests(unittest.TestCase):
    def test_balanced_rise_and_positive_momentum_scores_high(self):
        result = entry_timing.calculate_entry_timing_score(base_features())
        self.assertGreaterEqual(result["score"], 80)

    def test_sharp_three_and_five_day_rise_gets_late_entry_penalty(self):
        normal = entry_timing.calculate_entry_timing_score(base_features())
        late = entry_timing.calculate_entry_timing_score(base_features(return_3d_pct=9, return_5d_pct=13))
        self.assertLess(late["score"], normal["score"])
        self.assertIn("Sert yükseliş sonrası geç giriş riski", late["warnings"])

    def test_rsi_above_75_gets_both_overbought_penalties(self):
        result = entry_timing.calculate_entry_timing_score(base_features(rsi14=76))
        labels = [item["label"] for item in result["negative_contributions"]]
        self.assertIn("RSI 70 ve üzerinde", labels)
        self.assertIn("RSI 75 ve üzerinde ilave ceza", labels)

    def test_near_resistance_with_weak_volume_is_risky(self):
        result = entry_timing.calculate_entry_timing_score(
            base_features(resistance_distance_pct=1.0, volume_ratio=0.8)
        )
        labels = [item["label"] for item in result["negative_contributions"]]
        self.assertIn("Dirence çok yakın ve kırılım teyidi yok", labels)
        self.assertIn("Direnç altında hacim zayıf", labels)

    def test_weakening_momentum_reduces_score(self):
        strong = entry_timing.calculate_entry_timing_score(base_features())
        weak = entry_timing.calculate_entry_timing_score(
            base_features(momentum10=2, previous_momentum10=4, macd_histogram=0.2,
                          previous_macd_histogram=0.7)
        )
        self.assertLess(weak["score"], strong["score"])
        self.assertIn("Momentum yoruluyor", weak["warnings"])

    def test_missing_data_returns_limited_evaluation_without_error(self):
        result = entry_timing.evaluate_entry_timing({})
        self.assertIn("Eksik veri nedeniyle sınırlı değerlendirme", result["warnings"])
        self.assertTrue(result["missing_data"])

    def test_score_is_clamped_to_zero_and_one_hundred(self):
        high = entry_timing.calculate_entry_timing_score(base_features())
        low = entry_timing.calculate_entry_timing_score(
            base_features(return_1d_pct=8, return_3d_pct=12, return_5d_pct=18,
                          ema20_distance_pct=12, rsi14=78, resistance_distance_pct=1,
                          volume_ratio=0.7, momentum10=1, previous_momentum10=5,
                          macd_histogram=-1, previous_macd_histogram=1,
                          rsi_direction=-2, volatility20=8, atr_pct=6)
        )
        self.assertLessEqual(high["score"], 100)
        self.assertGreaterEqual(low["score"], 0)

    def test_breakout_uses_previous_20_closes_and_excludes_current_bar(self):
        prior_closes = [90.0 + index * 0.5 for index in range(20)]
        row = {
            "_portfolio_price_series": [*prior_closes, 105.0],
            "_follow_close": 105.0,
            "Direnç": 106.0,
            "Hacim Oranı": 1.20,
        }
        features = entry_timing.build_entry_timing_features(row)
        self.assertEqual(features["previous_20_close_resistance"], max(prior_closes))
        self.assertNotIn("breakout_resistance", features)
        self.assertTrue(features["breakout_confirmed"])

    def test_continuous_rise_produces_rsi_one_hundred(self):
        row = {"_portfolio_price_series": [float(value) for value in range(1, 31)]}
        features = entry_timing.build_entry_timing_features(row)
        self.assertEqual(features["rsi14"], 100.0)
        self.assertEqual(features["previous_rsi14"], 100.0)

    def test_missing_multi_day_returns_are_reported(self):
        features = entry_timing.build_entry_timing_features(
            {"_portfolio_price_series": [100.0, 101.0]}
        )
        self.assertNotIn("1 günlük getiri", features["missing_data"])
        self.assertIn("2 günlük getiri", features["missing_data"])
        self.assertIn("3 günlük getiri", features["missing_data"])
        self.assertIn("5 günlük getiri", features["missing_data"])
        self.assertIn("Bollinger üst bant", features["missing_data"])
        self.assertIn("RSI geçmişi", features["missing_data"])


if __name__ == "__main__":
    unittest.main()
