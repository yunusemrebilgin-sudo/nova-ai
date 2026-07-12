import copy
import inspect
import math
import unittest

import portfolio as portfolio_module
from portfolio import (
    build_candidate_id,
    equal_weight_scenario,
    generate_portfolio_candidates,
    module_status,
)


def price_series(phase=0, length=321):
    values = [100.0]
    for index in range(length - 1):
        change = 0.006 * math.sin((index + phase) * 0.31) + 0.003 * math.cos((index + phase * 2) * 0.17)
        values.append(values[-1] * (1.0 + change))
    return values


def row(symbol, sector=None, phase=0, **overrides):
    result = {
        "symbol": symbol,
        "sector": sector if sector is not None else f"Sector-{symbol}",
        "ai_confidence": 70.123456 + phase,
        "expected_return": 8.234567 + phase,
        "risk_score": 30.0 + phase,
        "volatility": 1.2 + phase * 0.05,
        "downside_deviation": 0.8 + phase * 0.04,
        "price_series": price_series(phase),
        "eligible": True,
        "news_impact": phase * 10,
    }
    result.update(overrides)
    return result


def rows(count=6):
    return [row(chr(65 + index) * 3, phase=index) for index in range(count)]


def universe(count=25):
    return [
        {
            "sell_risk": 20 + index * 2,
            "volatility": 1 + index * 0.1,
            "downside_deviation": 0.6 + index * 0.08,
            "expected_return": -2 + index,
        }
        for index in range(count)
    ]


class PortfolioCandidateEngineTests(unittest.TestCase):
    def generate(self, values=None, **kwargs):
        return generate_portfolio_candidates(
            rows() if values is None else values,
            kwargs.pop("horizon", "daily"),
            reference_universe=kwargs.pop("reference_universe", universe()),
            **kwargs,
        )

    def test_empty_candidate_list(self):
        result = self.generate([], min_assets=3, max_assets=3)
        self.assertEqual(result["status"], "invalid")

    def test_invalid_min_assets(self):
        with self.assertRaises(ValueError):
            self.generate(min_assets=1, max_assets=3)

    def test_max_assets_smaller_than_min_assets(self):
        with self.assertRaises(ValueError):
            self.generate(min_assets=5, max_assets=4)

    def test_size_above_candidate_count_generates_none(self):
        result = self.generate(rows(3), min_assets=4, max_assets=5)
        self.assertEqual(result["status"], "invalid")

    def test_duplicate_symbols_are_reported_and_excluded(self):
        values = rows(4) + [row("AAA", sector="Other")]
        result = self.generate(values, min_assets=3, max_assets=3)
        self.assertGreater(result["input_summary"]["duplicate_input_count"], 0)
        self.assertTrue(any("Duplicate" in reason for item in result["rejected_candidates"] for reason in item["rejection_reasons"]))

    def test_empty_symbol_is_rejected(self):
        values = rows(4) + [row("")]
        result = self.generate(values, min_assets=3, max_assets=3)
        self.assertTrue(any(item["rejection_stage"] == "input_validation" for item in result["rejected_candidates"]))

    def test_input_is_not_mutated(self):
        values = rows(4)
        before = copy.deepcopy(values)
        self.generate(values, min_assets=4, max_assets=4)
        self.assertEqual(values, before)

    def test_equal_weights_sum_to_one(self):
        raw, display = equal_weight_scenario(["A", "B", "C", "D"])
        self.assertAlmostEqual(sum(raw), 1.0)
        self.assertEqual(sum(display.values()), 1.0)

    def test_three_asset_remainder_is_deterministic(self):
        _, display = equal_weight_scenario(["A", "B", "C"])
        self.assertEqual(display, {"A": 0.3334, "B": 0.3333, "C": 0.3333})

    def test_same_input_is_deterministic(self):
        first = self.generate(rows(5), min_assets=3, max_assets=3)
        second = self.generate(rows(5), min_assets=3, max_assets=3)
        self.assertEqual(self.ids(first), self.ids(second))

    def test_input_order_does_not_change_logical_set(self):
        values = rows(5)
        first = self.generate(values, min_assets=3, max_assets=3)
        second = self.generate(list(reversed(values)), min_assets=3, max_assets=3)
        self.assertEqual(self.ids(first), self.ids(second))

    def test_combinations_are_unique(self):
        result = self.generate(rows(5), min_assets=3, max_assets=3)
        symbol_sets = [tuple(item["symbols"]) for item in result["candidates"]]
        self.assertEqual(len(symbol_sets), len(set(symbol_sets)))

    def test_symbol_never_repeats_inside_combination(self):
        result = self.generate(rows(5), min_assets=3, max_assets=3)
        self.assertTrue(all(len(item["symbols"]) == len(set(item["symbols"])) for item in result["candidates"]))

    def test_symbols_are_canonical(self):
        result = self.generate(list(reversed(rows(5))), min_assets=3, max_assets=3)
        self.assertTrue(all(item["symbols"] == sorted(item["symbols"]) for item in result["candidates"]))

    def test_candidate_id_is_deterministic(self):
        self.assertEqual(build_candidate_id(["A", "B"], [0.5, 0.5], "daily"), build_candidate_id(["A", "B"], [0.5, 0.5], "daily"))

    def test_candidate_id_changes_with_weight_or_horizon(self):
        base = build_candidate_id(["A", "B"], [0.5, 0.5], "daily")
        self.assertNotEqual(base, build_candidate_id(["A", "B"], [0.4, 0.6], "daily"))
        self.assertNotEqual(base, build_candidate_id(["A", "B"], [0.5, 0.5], "weekly"))

    def test_sector_above_fifty_percent_is_rejected(self):
        values = [row("A", "X"), row("B", "X", 1), row("C", "X", 2), row("D", "Y", 3)]
        result = self.generate(values, min_assets=4, max_assets=4)
        self.assertEqual(result["generation_summary"]["sector_precheck_rejected_count"], 1)

    def test_two_sector_candidate_is_not_precheck_rejected(self):
        values = [row("A", "X"), row("B", "X", 1), row("C", "Y", 2), row("D", "Y", 3)]
        result = self.generate(values, min_assets=4, max_assets=4)
        self.assertEqual(result["generation_summary"]["sector_precheck_rejected_count"], 0)
        self.assertEqual(result["generation_summary"]["valid_combination_count"], 1)

    def test_one_small_missing_sector_is_left_to_pci(self):
        values = [row("A", ""), row("B", "B", 1), row("C", "C", 2), row("D", "D", 3)]
        result = self.generate(values, min_assets=4, max_assets=4)
        self.assertEqual(result["generation_summary"]["sector_precheck_rejected_count"], 0)
        self.assertIn("Unclassified", result["candidates"][0]["sector_weights"])

    def test_multiple_missing_sectors_are_rejected(self):
        values = [row("A", ""), row("B", "", 1), row("C", "C", 2), row("D", "D", 3)]
        result = self.generate(values, min_assets=4, max_assets=4)
        self.assertEqual(result["generation_summary"]["sector_precheck_rejected_count"], 1)

    def test_pci_rejected_result_is_not_valid_candidate(self):
        result = self.generate(rows(4), min_assets=4, max_assets=4, reference_universe=universe(5))
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["generation_summary"]["pci_rejected_count"], 1)

    def test_pci_rejection_reasons_are_preserved(self):
        result = self.generate(rows(4), min_assets=4, max_assets=4, reference_universe=universe(5))
        rejected = [item for item in result["rejected_candidates"] if item["rejection_stage"] == "pci"]
        self.assertTrue(rejected[0]["rejection_reasons"])

    def test_valid_pci_is_stored(self):
        result = self.generate(rows(4), min_assets=4, max_assets=4)
        self.assertIn("portfolio_confidence_index", result["candidates"][0]["pci"])

    def test_news_impact_does_not_change_pci(self):
        first = rows(4)
        second = copy.deepcopy(first)
        for item in first:
            item["news_impact"] = -999
        for item in second:
            item["news_impact"] = 999
        self.assertEqual(self.generate(first, min_assets=4, max_assets=4)["candidates"][0]["pci"]["portfolio_confidence_index"], self.generate(second, min_assets=4, max_assets=4)["candidates"][0]["pci"]["portfolio_confidence_index"])

    def test_nan_critical_input_does_not_reach_candidate(self):
        values = rows(4)
        values[0]["ai_confidence"] = math.nan
        result = self.generate(values, min_assets=3, max_assets=3)
        self.assertTrue(all("AAA" not in item["symbols"] for item in result["candidates"]))

    def test_infinity_critical_input_does_not_reach_candidate(self):
        values = rows(4)
        values[0]["expected_return"] = math.inf
        result = self.generate(values, min_assets=3, max_assets=3)
        self.assertTrue(all("AAA" not in item["symbols"] for item in result["candidates"]))

    def test_max_combinations_limit_is_applied(self):
        result = self.generate(rows(6), min_assets=3, max_assets=5, max_combinations=4)
        self.assertEqual(result["generation_summary"]["generated_combination_count"], 4)

    def test_limit_warning_is_returned(self):
        result = self.generate(rows(6), min_assets=3, max_assets=5, max_combinations=4)
        self.assertIn("COMBINATION_LIMIT_REACHED", {item["code"] for item in result["warnings"]})

    def test_theoretical_and_generated_counts(self):
        result = self.generate(rows(5), min_assets=3, max_assets=4, max_combinations=3)
        self.assertEqual(result["generation_summary"]["theoretical_combination_count"], 15)
        self.assertEqual(result["generation_summary"]["generated_combination_count"], 3)

    def test_counts_by_asset_size(self):
        result = self.generate(rows(5), min_assets=3, max_assets=4)
        self.assertEqual(result["generation_summary"]["generated_combination_count"], 15)
        self.assertEqual(result["generation_summary"]["combination_counts_by_asset_size"], {3: 10, 4: 5})

    def test_three_four_and_five_asset_generation(self):
        result = self.generate(rows(5), min_assets=3, max_assets=5)
        self.assertEqual(set(result["generation_summary"]["combination_counts_by_asset_size"]), {3, 4, 5})

    def test_no_valid_combination_status(self):
        result = self.generate(rows(4), min_assets=4, max_assets=4, reference_universe=universe(5))
        self.assertEqual(result["status"], "rejected")

    def test_structured_warning_format(self):
        result = self.generate(rows(6), min_assets=3, max_assets=5, max_combinations=1)
        warning = result["warnings"][0]
        self.assertEqual(set(warning), {"code", "message", "scope", "details"})

    def test_structured_rejection_format(self):
        values = rows(4) + [row("")]
        rejection = self.generate(values, min_assets=4, max_assets=4)["rejected_candidates"][0]
        self.assertEqual(set(rejection), {"candidate_id", "symbols", "weights", "rejection_stage", "rejection_reasons"})

    def test_output_numbers_use_at_most_four_decimals(self):
        result = self.generate(rows(4), min_assets=4, max_assets=4)
        for value in result["candidates"][0]["weights"].values():
            self.assertEqual(value, round(value, 4))

    def test_module_status_is_unchanged(self):
        self.assertEqual(module_status(), "Portföy modülü gelecek sürümlerde aktif olacak.")

    def test_no_streamlit_dependency_added(self):
        source = inspect.getsource(portfolio_module)
        self.assertNotIn("import streamlit", source)

    def test_no_download_or_market_scan_call(self):
        source = inspect.getsource(generate_portfolio_candidates)
        self.assertNotIn("yfinance", source)
        self.assertNotIn("download", source)
        self.assertNotIn("scan_smart_market", source)

    @staticmethod
    def ids(result):
        return [item["candidate_id"] for item in result["candidates"]]


if __name__ == "__main__":
    unittest.main()
