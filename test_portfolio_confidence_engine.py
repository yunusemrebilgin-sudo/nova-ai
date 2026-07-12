from datetime import date, datetime, timezone
import math
import unittest

from portfolio import HORIZON_CORRELATION_RULES, PCI_WEIGHTS, calculate_portfolio_confidence


NOW = datetime(2026, 7, 12, tzinfo=timezone.utc)
END = date(2026, 7, 11)


def prices_from_returns(returns):
    values = [100.0]
    for value in returns:
        values.append(values[-1] * (1.0 + value))
    return values


def return_series(length=320, phase=0, scale=0.008):
    return [
        scale * math.sin((index + phase) * 0.37)
        + scale * 0.45 * math.cos((index + phase * 3) * 0.19)
        for index in range(length)
    ]


def reference_universe(count=25):
    return [
        {
            "sell_risk": 20.0 + index * 2.0,
            "volatility": 1.0 + index * 0.12,
            "downside_deviation": 0.7 + index * 0.09,
            "expected_return": -2.0 + index * 1.1,
        }
        for index in range(count)
    ]


def portfolio(stocks=None, sectors=None, weights=None):
    stocks = stocks or ["AAA", "BBB", "CCC", "DDD"]
    sectors = sectors or ["Bank", "Energy", "Food", "Tech"]
    weights = weights or [0.25] * len(stocks)
    return {"stocks": stocks, "sectors": sectors, "weights": weights}


def metrics(stocks=None):
    stocks = stocks or ["AAA", "BBB", "CCC", "DDD"]
    return {
        stock: {
            "ai_confidence": 72.123456 + index * 3.17,
            "sell_risk": 30.0 + index * 4.0,
            "volatility": 1.4 + index * 0.15,
            "downside_deviation": 0.9 + index * 0.12,
            "expected_return": 8.3 + index * 1.4,
            "news_impact": -99 + index,
        }
        for index, stock in enumerate(stocks)
    }


def price_map(stocks=None, length=320):
    stocks = stocks or ["AAA", "BBB", "CCC", "DDD"]
    return {
        stock: prices_from_returns(return_series(length, phase=index * 7))
        for index, stock in enumerate(stocks)
    }


class PortfolioConfidenceEngineTests(unittest.TestCase):
    def calculate(self, candidate=None, stock_metrics=None, prices=None, universe=None, horizon="daily"):
        candidate = candidate or portfolio()
        stocks = candidate["stocks"]
        return calculate_portfolio_confidence(
            candidate,
            horizon,
            stock_metrics or metrics(stocks),
            {},
            prices or price_map(stocks),
            universe or reference_universe(),
            calculation_timestamp=NOW,
            data_end_date=END,
        )

    def test_balanced_four_stock_four_sector_portfolio(self):
        result = self.calculate()
        self.assertIn(result.status, {"valid", "valid_with_warnings"})
        self.assertEqual(len(result.sector_weights), 4)
        self.assertIsNotNone(result.portfolio_confidence_index)

    def test_balanced_five_stock_three_sector_portfolio(self):
        stocks = ["A", "B", "C", "D", "E"]
        result = self.calculate(portfolio(stocks, ["X", "X", "Y", "Z", "Z"], [0.2] * 5), metrics(stocks), price_map(stocks))
        self.assertLessEqual(result.maximum_sector_weight, 0.4)
        self.assertIsNotNone(result.portfolio_confidence_index)

    def test_single_sector_concentration_is_rejected(self):
        result = self.calculate(portfolio(sectors=["X"] * 4))
        self.assertEqual(result.status, "rejected")

    def test_sector_weight_above_fifty_percent_is_rejected(self):
        result = self.calculate(portfolio(sectors=["X", "X", "X", "Y"], weights=[0.2, 0.2, 0.2, 0.4]))
        self.assertEqual(result.status, "rejected")

    def test_high_average_correlation_lowers_cb(self):
        shared = prices_from_returns(return_series())
        high = self.calculate(prices={stock: shared for stock in portfolio()["stocks"]})
        low = self.calculate()
        self.assertLess(high.correlation_balance_score, low.correlation_balance_score)

    def test_one_extreme_pair_is_counted(self):
        values = price_map()
        values["BBB"] = values["AAA"]
        result = self.calculate(prices=values)
        self.assertGreaterEqual(result.extreme_correlation_pair_count, 1)

    def test_multiple_high_pairs_are_counted(self):
        shared = prices_from_returns(return_series())
        result = self.calculate(prices={stock: shared for stock in portfolio()["stocks"]})
        self.assertGreater(result.high_correlation_pair_count, 1)

    def test_stress_period_correlation_increase_warns(self):
        stocks = portfolio()["stocks"]
        series = {stock: return_series(320, phase=index * 9) for index, stock in enumerate(stocks)}
        for index in range(100, 125):
            common = -0.025 + 0.003 * math.sin(index)
            for stock in stocks:
                series[stock][index] = common
        result = self.calculate(prices={stock: prices_from_returns(values) for stock, values in series.items()})
        self.assertIn("DIVERSIFICATION_WEAKENS_UNDER_STRESS", self.warning_codes(result))

    def test_balanced_risk_contributions(self):
        stock_data = metrics()
        for row in stock_data.values():
            row.update(sell_risk=40, volatility=2, downside_deviation=1.5)
        result = self.calculate(stock_metrics=stock_data)
        contributions = result.explanation_facts["risk_contributions"].values()
        self.assertAlmostEqual(max(contributions), min(contributions))

    def test_single_stock_dominant_risk_contribution(self):
        candidate = portfolio(weights=[0.7, 0.1, 0.1, 0.1])
        result = self.calculate(candidate=candidate)
        self.assertGreater(result.maximum_risk_contribution, 0.5)
        self.assertIn("DOMINANT_RISK_CONTRIBUTION", self.warning_codes(result))

    def test_balanced_expected_returns(self):
        stock_data = metrics()
        for index, row in enumerate(stock_data.values()):
            row["expected_return"] = 9.0 + index * 0.2
        result = self.calculate(stock_metrics=stock_data)
        self.assertGreater(result.expected_return_summary["return_balance_score"], 80)

    def test_expected_return_outlier_is_winsorized_for_quality(self):
        normal = self.calculate()
        stock_data = metrics()
        stock_data["AAA"]["expected_return"] = 10000.0
        outlier = self.calculate(stock_metrics=stock_data)
        self.assertLess(outlier.expected_return_balance_score, normal.expected_return_balance_score)

    def test_all_negative_expected_returns_warn_and_cap_ebs(self):
        stock_data = metrics()
        for index, row in enumerate(stock_data.values()):
            row["expected_return"] = -1.0 - index
        result = self.calculate(stock_metrics=stock_data)
        self.assertIn("ALL_EXPECTED_RETURNS_NON_POSITIVE", self.warning_codes(result))
        self.assertLessEqual(result.expected_return_summary["return_balance_score"], 40)

    def test_one_missing_ai_gets_eight_point_penalty(self):
        stock_data = metrics()
        stock_data["AAA"]["ai_confidence"] = None
        result = self.calculate(stock_metrics=stock_data)
        self.assertEqual(result.explanation_facts["penalties"]["average_ai_confidence"], [8.0])

    def test_one_small_missing_sector_is_unclassified(self):
        result = self.calculate(portfolio(sectors=["", "B", "C", "D"]))
        self.assertEqual(result.sector_weights["Unclassified"], 0.25)
        self.assertIn("MISSING_SECTOR", self.warning_codes(result))

    def test_missing_sell_risk_uses_risk_fallback(self):
        self.assert_risk_fallback("sell_risk")

    def test_missing_volatility_uses_risk_fallback(self):
        self.assert_risk_fallback("volatility")

    def test_missing_downside_deviation_uses_risk_fallback(self):
        self.assert_risk_fallback("downside_deviation")

    def test_missing_correlation_is_rejected(self):
        values = price_map()
        values["AAA"] = [100.0] * 321
        result = self.calculate(prices=values)
        self.assertEqual(result.status, "rejected")

    def test_nan_and_infinity_are_rejected_or_substituted(self):
        stock_data = metrics()
        stock_data["AAA"]["ai_confidence"] = math.nan
        stock_data["BBB"]["ai_confidence"] = math.inf
        result = self.calculate(stock_metrics=stock_data)
        self.assertEqual(result.status, "rejected")
        self.assertIsNone(result.portfolio_confidence_index)

    def test_pci_uses_exact_five_component_formula(self):
        result = self.calculate()
        raw = result.explanation_facts["component_scores_raw"]
        expected = sum(raw[name] * PCI_WEIGHTS[name] for name in PCI_WEIGHTS)
        self.assertAlmostEqual(result.explanation_facts["raw_portfolio_confidence_index"], expected)
        self.assertEqual(len(raw), 5)

    def test_final_pci_is_bounded(self):
        result = self.calculate()
        self.assertGreaterEqual(result.portfolio_confidence_index, 0)
        self.assertLessEqual(result.portfolio_confidence_index, 100)

    def test_raw_calculation_is_preserved_before_output_rounding(self):
        result = self.calculate()
        raw = result.explanation_facts["raw_portfolio_confidence_index"]
        self.assertEqual(result.portfolio_confidence_index, round(raw, 4))
        self.assertNotEqual(raw, round(raw, 1))

    def test_all_six_horizons(self):
        for horizon in HORIZON_CORRELATION_RULES:
            with self.subTest(horizon=horizon):
                result = self.calculate(horizon=horizon)
                self.assertEqual(result.horizon, horizon)
                self.assertIsNotNone(result.portfolio_confidence_index)

    def test_news_impact_does_not_change_pci(self):
        first_metrics = metrics()
        second_metrics = metrics()
        for row in first_metrics.values():
            row["news_impact"] = -1000
        for row in second_metrics.values():
            row["news_impact"] = 1000
        self.assertEqual(self.calculate(stock_metrics=first_metrics).portfolio_confidence_index, self.calculate(stock_metrics=second_metrics).portfolio_confidence_index)

    def test_part_one_and_part_two_contracts_remain_available(self):
        from portfolio import SectorMetrics, validate_pci_weights, validate_sector_score_weights
        validate_pci_weights()
        validate_sector_score_weights()
        self.assertTrue(SectorMetrics)

    def assert_risk_fallback(self, field):
        stock_data = metrics()
        stock_data["AAA"][field] = None
        result = self.calculate(stock_metrics=stock_data)
        self.assertIn("INCOMPLETE_RISK_INPUT", self.warning_codes(result))
        self.assertIsNotNone(result.risk_distribution_score)

    @staticmethod
    def warning_codes(result):
        return {warning["warning_code"] for warning in result.warnings}


if __name__ == "__main__":
    unittest.main()
