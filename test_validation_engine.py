import unittest
from unittest.mock import patch

import validation_engine


def current_row(**overrides):
    row = {
        "Hisse": "TEST.IS",
        "Son Fiyat": 100.0,
        "Beklenen Getiri %": 8.0,
        "Nova Score": 75.0,
        "AI Güven Endeksi": 75.0,
        "Alım Uygunluğu %": 75.0,
        "Sat Riski %": 40.0,
        "Sonuç": "🟢 Güçlü Alım",
        "Beklenen Taşıma Süresi": "10-20 işlem günü",
        "Trend": "Pozitif",
        "RSI": 55.0,
        "MACD": 1.0,
        "Volatilite": 2.5,
        "Hacim Oranı": 1.3,
        "Destek": 95.0,
        "Direnç": 110.0,
        "_market_data_time": "2026-07-16T18:00:00+03:00",
    }
    row.update(overrides)
    return row


def entry_result(**overrides):
    result = {
        "score": 75,
        "classification": "KADEMELİ GİRİŞ",
        "positive_contributions": [],
        "negative_contributions": [],
        "warnings": [],
        "missing_data": [],
        "features": {},
    }
    result.update(overrides)
    return result


def expected_result(**overrides):
    result = {
        "conservative_expected_return": 6.0,
        "main_expected_return": 8.0,
        "optimistic_expected_return": 10.0,
        "model_confidence": 75.0,
        "directional_quality_score": 75.0,
        "movement_capacity": 5.0,
        "entry_timing_adjustment": 0.5,
        "resistance_adjustment": 0.0,
        "risk_penalty": 1.0,
        "uncertainty": 2.0,
        "limiting_factors": [],
        "missing_data": [],
        "features": {"atr_pct": 3.0, "price_series_length": 60},
    }
    result.update(overrides)
    return result


def critical_result(**overrides):
    result = {
        "earliest_reasonable_day": 10,
        "main_day": 14,
        "window_start": 12,
        "window_end": 18,
        "late_day": 20,
        "reachability": True,
        "critical_day_model_confidence": 75.0,
        "accelerators": [],
        "delays": [],
        "limiting_factors": [],
        "missing_data": [],
        "status": "ANA PENCERE",
        "features": {},
    }
    result.update(overrides)
    return result


def evaluate(row=None, entry=None, expected=None, critical=None):
    return validation_engine.evaluate_validation_engine(
        row or current_row(),
        "10-30 gün",
        entry_timing_result=entry or entry_result(),
        expected_return_result=expected or expected_result(),
        critical_day_result=critical or critical_result(),
    )


class ValidationEngineTests(unittest.TestCase):
    def test_close_current_and_lab_results_have_high_consistency(self):
        result = evaluate()
        self.assertEqual(result["comparison"]["expected_return_difference_class"], "Yakın")
        self.assertTrue(result["comparison"]["window_overlap"])
        self.assertGreaterEqual(result["model_consistency_score"], 85)
        self.assertEqual(result["model_consistency_classification"], "YÜKSEK TUTARLILIK")

    def test_strong_stock_with_low_entry_score_creates_conflict(self):
        result = evaluate(entry=entry_result(score=40, classification="GİRİŞ ZAYIF"))
        conflict_ids = {item["id"] for item in result["conflicts"]}
        self.assertIn("strong_stock_bad_entry", conflict_ids)
        self.assertEqual(result["summary"]["decision"], "GÜÇLÜ ADAY — GİRİŞ KAÇMIŞ OLABİLİR")

    def test_current_return_more_than_five_points_above_v2_is_critical_difference(self):
        result = evaluate(
            row=current_row(**{"Beklenen Getiri %": 12.0}),
            expected=expected_result(main_expected_return=5.0),
        )
        self.assertEqual(result["comparison"]["expected_return_difference"], -7.0)
        self.assertEqual(result["comparison"]["expected_return_difference_class"], "Kritik Fark")
        self.assertIn("current_return_above_v2", {item["id"] for item in result["conflicts"]})
        penalty_keys = {item["key"] for item in result["debug"]["score_penalties"]}
        self.assertNotIn("expected_return_gap", penalty_keys)

    def test_positive_v2_with_unreachable_critical_day_is_horizon_mismatch(self):
        result = evaluate(
            critical=critical_result(
                earliest_reasonable_day=None,
                main_day=None,
                window_start=None,
                window_end=None,
                late_day=None,
                reachability=False,
                status="VADE İÇİNDE ERİŞİLEMEZ",
            )
        )
        self.assertIn("positive_return_unreachable", {item["id"] for item in result["conflicts"]})
        self.assertEqual(result["summary"]["decision"], "VADEYLE UYUMSUZ")

    def test_positive_models_and_high_entry_are_suitable_candidate(self):
        result = evaluate(entry=entry_result(score=85, classification="GİRİŞ UYGUN"))
        self.assertEqual(result["summary"]["decision"], "UYGUN ADAY — GİRİŞ UYGUN")

    def test_entry_score_between_fifty_and_sixty_four_waits_for_confirmation(self):
        result = evaluate(entry=entry_result(score=60, classification="BEKLE / TEYİT GEREKİYOR"))
        self.assertEqual(result["summary"]["decision"], "UYGUN ADAY — TEYİT BEKLE")
        self.assertIn("current_buy_lab_wait", {item["id"] for item in result["conflicts"]})

    def test_remaining_conflict_rules_are_detected(self):
        low_confidence = evaluate(expected=expected_result(main_expected_return=8.0, model_confidence=40.0))
        self.assertIn("high_return_low_confidence", {item["id"] for item in low_confidence["conflicts"]})

        narrow_window = evaluate(
            expected=expected_result(uncertainty=4.0),
            critical=critical_result(window_start=12, window_end=14),
        )
        self.assertIn("narrow_window_high_uncertainty", {item["id"] for item in narrow_window["conflicts"]})

        lab_positive = evaluate(
            row=current_row(**{"Sonuç": "🟡 Takip Et", "Alım Uygunluğu %": 40.0}),
            entry=entry_result(score=85, classification="GİRİŞ UYGUN"),
        )
        self.assertIn("lab_positive_current_cautious", {item["id"] for item in lab_positive["conflicts"]})

    def test_nonpositive_v2_is_weak_technical_expectation(self):
        result = evaluate(
            entry=entry_result(score=85, classification="GİRİŞ UYGUN"),
            expected=expected_result(main_expected_return=0.0, conservative_expected_return=-2.0),
            critical=critical_result(
                earliest_reasonable_day=None,
                main_day=None,
                window_start=None,
                window_end=None,
                late_day=None,
                reachability=None,
                status="SAYISAL SONUÇ ÜRETİLEMEDİ",
            ),
        )
        self.assertEqual(result["summary"]["decision"], "TEKNİK BEKLENTİ ZAYIF")
        self.assertIn("good_entry_nonpositive_return", {item["id"] for item in result["conflicts"]})

    def test_critical_missing_data_is_uncertain_and_reduces_score(self):
        result = evaluate(
            entry=entry_result(score=None, classification=None, missing_data=["Entry Timing Score"]),
            expected=expected_result(
                main_expected_return=None,
                conservative_expected_return=None,
                optimistic_expected_return=None,
                features={"atr_pct": None, "price_series_length": 10},
                missing_data=["ATR%"],
            ),
            critical=critical_result(
                earliest_reasonable_day=None,
                main_day=None,
                window_start=None,
                window_end=None,
                late_day=None,
                reachability=None,
                status="SAYISAL SONUÇ ÜRETİLEMEDİ",
                missing_data=["ATR%"],
            ),
        )
        self.assertEqual(result["summary"]["decision"], "MODEL BELİRSİZ")
        self.assertIn("critical_data_missing", {item["id"] for item in result["conflicts"]})
        self.assertLess(result["model_consistency_score"], 100)

    def test_overlapping_windows_have_no_mismatch_penalty(self):
        result = evaluate()
        self.assertTrue(result["comparison"]["window_overlap"])
        self.assertNotIn("window_no_overlap", {item["id"] for item in result["conflicts"]})
        self.assertNotIn("window_no_overlap", {item["key"] for item in result["debug"]["score_penalties"]})

    def test_nonoverlapping_windows_create_one_conflict_and_one_penalty(self):
        result = evaluate(
            critical=critical_result(main_day=24, window_start=22, window_end=26, late_day=28)
        )
        conflicts = [item for item in result["conflicts"] if item["id"] == "window_no_overlap"]
        penalties = [item for item in result["debug"]["score_penalties"] if "window_no_overlap" in item["key"]]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(len(penalties), 1)
        self.assertEqual(penalties[0]["points"], -15)

    def test_critical_missing_reason_is_not_penalized_twice(self):
        result = evaluate(
            entry=entry_result(score=None, classification=None),
            expected=expected_result(main_expected_return=None, features={"atr_pct": None, "price_series_length": 10}),
            critical=critical_result(reachability=None, main_day=None, window_start=None, window_end=None),
        )
        missing_penalties = [
            item for item in result["debug"]["score_penalties"]
            if "critical_data_missing" in item["key"] or item["key"] == "critical_missing_data"
        ]
        self.assertEqual(len(missing_penalties), 1)
        self.assertEqual(missing_penalties[0]["points"], -25)
        self.assertTrue(result["debug"]["critical_missing_absorbed_by_conflict"])

    def test_model_consistency_score_is_clamped_to_zero_and_one_hundred(self):
        features = evaluate()["features"]
        comparison = validation_engine.compare_current_and_lab_models(features)
        conflicts = [
            {"id": f"critical_{index}", "severity": "KRİTİK", "title": "Kritik", "description": "", "current_value": None, "lab_value": None}
            for index in range(6)
        ]
        score = validation_engine.calculate_validation_score(features, comparison, conflicts)
        self.assertEqual(score["score"], 0)
        self.assertGreaterEqual(score["score"], 0)
        self.assertLessEqual(score["score"], 100)

    def test_summary_priority_chain(self):
        uncertain = evaluate(
            entry=entry_result(score=None, classification=None),
            expected=expected_result(main_expected_return=None, features={"atr_pct": None, "price_series_length": 5}),
            critical=critical_result(reachability=False, main_day=None, window_start=None, window_end=None),
        )
        self.assertEqual(uncertain["summary"]["decision"], "MODEL BELİRSİZ")

        mismatch = evaluate(critical=critical_result(reachability=False, main_day=None, window_start=None, window_end=None))
        self.assertEqual(mismatch["summary"]["decision"], "VADEYLE UYUMSUZ")

        weak = evaluate(expected=expected_result(main_expected_return=-1.0))
        self.assertEqual(weak["summary"]["decision"], "TEKNİK BEKLENTİ ZAYIF")

    def test_unparseable_month_window_is_missing_not_nonoverlap(self):
        result = evaluate(row=current_row(**{"Beklenen Taşıma Süresi": "1-2 ay"}))
        self.assertIsNone(result["comparison"]["window_overlap"])
        self.assertNotIn("window_no_overlap", {item["id"] for item in result["conflicts"]})
        self.assertIn("Mevcut kritik pencere sayısal işlem gününe çevrilemedi", result["missing_data"])

    def test_user2_cannot_render_yebora_lab(self):
        import app

        with patch.object(app, "current_auth_user", return_value="user2"), patch.object(app.st, "container") as container:
            app.render_yebora_lab()
        container.assert_not_called()


if __name__ == "__main__":
    unittest.main()
