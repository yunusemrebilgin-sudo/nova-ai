from datetime import date, datetime, timezone
import math
import unittest

from portfolio import (
    HORIZON_MOMENTUM_PERIODS,
    SECTOR_SCORE_WEIGHTS,
    calculate_sector_engine,
    calculate_sector_metrics,
    validate_sector_score_weights,
)


NOW = datetime(2026, 7, 12, tzinfo=timezone.utc)
END_DATE = date(2026, 7, 11)


def candidate(
    symbol: str,
    *,
    sector: str = "Bankacılık",
    nova=80.0,
    ai=75.0,
    trend="Pozitif",
    news=2.0,
) -> dict[str, object]:
    return {
        "Hisse": symbol,
        "sector": sector,
        "Nova Score": nova,
        "AI Güven Endeksi": ai,
        "Alım Uygunluğu %": 70.0,
        "Trend": trend,
        "Sonuç": "AL için güçlü aday",
        "Haber Etkisi %": news,
    }


def prices(length: int = 300, daily_growth: float = 0.001) -> list[float]:
    return [100.0 * ((1.0 + daily_growth) ** index) for index in range(length)]


class SectorEngineTests(unittest.TestCase):
    def calculate(self, rows, price_map, horizon="monthly"):
        return calculate_sector_metrics(
            "Bankacılık",
            rows,
            price_map,
            horizon,
            calculation_timestamp=NOW,
            data_end_date=END_DATE,
        )

    def test_valid_multi_stock_sector(self) -> None:
        rows = [candidate("AAA.IS"), candidate("BBB.IS", nova=70, ai=80)]
        result = self.calculate(rows, {"AAA.IS": prices(), "BBB.IS": prices()})
        self.assertEqual(result.status, "valid")
        self.assertEqual(result.constituent_count, 2)
        self.assertEqual(result.valid_constituent_count, 2)
        self.assertIsNotNone(result.sector_score)

    def test_single_stock_sector(self) -> None:
        result = self.calculate([candidate("AAA.IS")], {"AAA.IS": prices()})
        self.assertEqual(result.status, "valid")
        self.assertEqual(result.constituent_count, 1)

    def test_missing_sector_name_is_rejected(self) -> None:
        results = calculate_sector_engine(
            [candidate("AAA.IS", sector="")],
            {"AAA.IS": prices()},
            "monthly",
            calculation_timestamp=NOW,
            data_end_date=END_DATE,
        )
        self.assertEqual(results[0].status, "rejected")
        self.assertTrue(results[0].rejection_reasons)

    def test_one_missing_ai_uses_documented_penalty(self) -> None:
        rows = [candidate("AAA.IS", ai=80), candidate("BBB.IS", ai=None)]
        result = self.calculate(rows, {"AAA.IS": prices(), "BBB.IS": prices()})
        self.assertEqual(result.status, "valid_with_warnings")
        self.assertEqual(result.average_ai_confidence, 72.0)
        self.assertIn("MISSING_AI_CONFIDENCE", self.warning_codes(result))

    def test_multiple_missing_ai_is_rejected(self) -> None:
        rows = [candidate("AAA.IS", ai=None), candidate("BBB.IS", ai=None)]
        result = self.calculate(rows, {"AAA.IS": prices(), "BBB.IS": prices()})
        self.assertEqual(result.status, "rejected")
        self.assertIsNone(result.sector_score)

    def test_missing_nova_is_warned_and_excluded(self) -> None:
        rows = [candidate("AAA.IS", nova=80), candidate("BBB.IS", nova=None)]
        result = self.calculate(rows, {"AAA.IS": prices(), "BBB.IS": prices()})
        self.assertEqual(result.average_nova_score, 80.0)
        self.assertIn("MISSING_NOVA_SCORE", self.warning_codes(result))

    def test_missing_news_does_not_stop_calculation(self) -> None:
        row = candidate("AAA.IS", news=None)
        result = self.calculate([row], {"AAA.IS": prices()})
        self.assertEqual(result.status, "valid_with_warnings")
        self.assertIsNone(result.sector_news_impact)
        self.assertIn("MISSING_NEWS_IMPACT", self.warning_codes(result))

    def test_insufficient_price_history_is_rejected(self) -> None:
        result = self.calculate([candidate("AAA.IS")], {"AAA.IS": [100.0]})
        self.assertEqual(result.status, "rejected")
        self.assertIsNone(result.sector_momentum)
        self.assertIn("INSUFFICIENT_PRICE_HISTORY", self.warning_codes(result))

    def test_nan_and_infinity_do_not_reach_scores(self) -> None:
        rows = [
            candidate("AAA.IS", nova=math.nan, ai=80),
            candidate("BBB.IS", nova=80, ai=math.inf),
        ]
        result = self.calculate(rows, {"AAA.IS": prices(), "BBB.IS": prices()})
        self.assertEqual(result.status, "valid_with_warnings")
        for value in result.metrics.values():
            self.assertTrue(math.isfinite(value))

    def test_all_subscores_and_final_score_are_bounded(self) -> None:
        result = self.calculate(
            [candidate("AAA.IS", nova=100, ai=100)],
            {"AAA.IS": prices(daily_growth=0.20)},
        )
        for value in result.metrics.values():
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 100.0)

    def test_sector_score_formula(self) -> None:
        result = self.calculate([candidate("AAA.IS")], {"AAA.IS": prices()})
        expected = (
            result.sector_strength * SECTOR_SCORE_WEIGHTS["sector_strength"]
            + result.sector_momentum * SECTOR_SCORE_WEIGHTS["sector_momentum"]
            + result.sector_trend * SECTOR_SCORE_WEIGHTS["sector_trend"]
            + result.average_ai_confidence
            * SECTOR_SCORE_WEIGHTS["average_ai_confidence"]
        )
        self.assertAlmostEqual(result.sector_score, expected)
        validate_sector_score_weights()

    def test_all_six_horizons(self) -> None:
        for horizon in HORIZON_MOMENTUM_PERIODS:
            with self.subTest(horizon=horizon):
                result = self.calculate(
                    [candidate("AAA.IS")], {"AAA.IS": prices()}, horizon
                )
                self.assertEqual(result.horizon, horizon)
                self.assertIsNotNone(result.sector_momentum)

    def test_news_impact_is_not_in_sector_score(self) -> None:
        low_news = self.calculate(
            [candidate("AAA.IS", news=-10)], {"AAA.IS": prices()}
        )
        high_news = self.calculate(
            [candidate("AAA.IS", news=10)], {"AAA.IS": prices()}
        )
        self.assertNotEqual(low_news.sector_news_impact, high_news.sector_news_impact)
        self.assertEqual(low_news.sector_score, high_news.sector_score)

    @staticmethod
    def warning_codes(result) -> set[str]:
        return {warning["warning_code"] for warning in result.warnings}


if __name__ == "__main__":
    unittest.main()
