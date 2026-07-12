import copy
import inspect
import unittest
from unittest.mock import patch

import app
import portfolio


class FakeUI:
    def __init__(self):
        self.info_messages = []
        self.markdown_calls = []

    def info(self, message):
        self.info_messages.append(message)

    def markdown(self, body, **kwargs):
        self.markdown_calls.append((body, kwargs))


def ranked_item():
    facts = {"dominant_sector": "Teknoloji", "highest_risk_contribution_stock": "AAA"}
    return {
        "rank": 1,
        "candidate_id": "candidate-1",
        "symbols": ["AAA", "BBB", "CCC", "DDD"],
        "weights": {"AAA": 0.25, "BBB": 0.25, "CCC": 0.25, "DDD": 0.25},
        "optimizer_metrics": {
            "portfolio_confidence_index": 78.5,
            "weighted_expected_return": 11.2,
            "weighted_risk_score": 37.4,
            "average_correlation": 0.24,
            "maximum_pair_correlation": 0.42,
        },
        "pci": {"explanation_facts": facts, "warnings": []},
    }


class PortfolioResultsServiceTests(unittest.TestCase):
    def test_service_uses_part_four_and_part_five(self):
        generation = {"status": "ok", "candidates": [], "rejected_candidates": [], "input_summary": {}, "generation_summary": {}, "warnings": [], "validation_errors": []}
        optimization = {"status": "empty", "ranked_candidates": [], "filtered_candidates": [], "ranking_summary": {}, "warnings": [], "validation_errors": []}
        with patch("portfolio.generate_portfolio_candidates", return_value=generation) as generate, patch("portfolio.optimize_portfolio_candidates", return_value=optimization) as optimize:
            portfolio.build_ranked_portfolio_results([], "daily")
        generate.assert_called_once()
        optimize.assert_called_once_with(generation, top_n=20, min_pci=None, max_risk_score=None, min_expected_return=None)

    def test_service_does_not_scan_or_download(self):
        source = inspect.getsource(portfolio.build_ranked_portfolio_results)
        for forbidden in ("yfinance", "download_price_data(", "scan_smart_market(", "streamlit"):
            self.assertNotIn(forbidden, source)

    def test_top_twenty_cap(self):
        generation = {"status": "ok", "candidates": [], "rejected_candidates": [], "input_summary": {}, "generation_summary": {}, "warnings": [], "validation_errors": []}
        optimization = {"status": "empty", "ranked_candidates": [], "filtered_candidates": [], "ranking_summary": {}, "warnings": [], "validation_errors": []}
        with patch("portfolio.generate_portfolio_candidates", return_value=generation), patch("portfolio.optimize_portfolio_candidates", return_value=optimization) as optimize:
            portfolio.build_ranked_portfolio_results([], "daily", top_n=100)
        self.assertEqual(optimize.call_args.kwargs["top_n"], 20)

    def test_filter_parameters_are_forwarded(self):
        generation = {"status": "ok", "candidates": [], "rejected_candidates": [], "input_summary": {}, "generation_summary": {}, "warnings": [], "validation_errors": []}
        optimization = {"status": "empty", "ranked_candidates": [], "filtered_candidates": [], "ranking_summary": {}, "warnings": [], "validation_errors": []}
        with patch("portfolio.generate_portfolio_candidates", return_value=generation), patch("portfolio.optimize_portfolio_candidates", return_value=optimization) as optimize:
            portfolio.build_ranked_portfolio_results([], "daily", min_pci=60, max_risk_score=50, min_expected_return=5)
        self.assertEqual(optimize.call_args.kwargs, {"top_n": 20, "min_pci": 60, "max_risk_score": 50, "min_expected_return": 5})

    def test_empty_scanner_results(self):
        result = portfolio.build_ranked_portfolio_results([], "daily")
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["ranked_candidates"], [])

    def test_invalid_scanner_results(self):
        result = portfolio.build_ranked_portfolio_results(None, "daily")
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["validation_errors"][0]["code"], "INVALID_SCANNER_RESULTS")

    def test_warning_and_rejection_summaries_are_preserved(self):
        generation = {"status": "ok", "candidates": [], "rejected_candidates": [{"x": 1}], "input_summary": {"x": 1}, "generation_summary": {"pci_rejected_count": 2}, "warnings": [{"code": "G"}], "validation_errors": [{"code": "GV"}]}
        optimization = {"status": "empty", "ranked_candidates": [], "filtered_candidates": [{"x": 2}], "ranking_summary": {"x": 2}, "warnings": [{"code": "O"}], "validation_errors": [{"code": "OV"}]}
        with patch("portfolio.generate_portfolio_candidates", return_value=generation), patch("portfolio.optimize_portfolio_candidates", return_value=optimization):
            result = portfolio.build_ranked_portfolio_results([], "daily")
        self.assertEqual([item["code"] for item in result["warnings"]], ["G", "O"])
        self.assertEqual(result["rejection_summary"], {"input_or_sector_rejections": 1, "optimizer_filtered_count": 1, "pci_rejected_count": 2})

    def test_input_is_not_mutated(self):
        source = [{"symbol": "AAA"}]
        before = copy.deepcopy(source)
        portfolio.build_ranked_portfolio_results(source, "daily", portfolio_size=4)
        self.assertEqual(source, before)

    def test_deterministic_result(self):
        source = [{"symbol": "AAA"}]
        self.assertEqual(portfolio.build_ranked_portfolio_results(source, "daily"), portfolio.build_ranked_portfolio_results(source, "daily"))

    def test_ui_empty_result_behavior(self):
        ui = FakeUI()
        rendered = app.render_portfolio_ranked_results({"ranked_candidates": []}, ui)
        self.assertFalse(rendered)
        self.assertTrue(ui.info_messages)

    def test_ui_valid_result_behavior(self):
        ui = FakeUI()
        rendered = app.render_portfolio_ranked_results({"ranked_candidates": [ranked_item()]}, ui)
        self.assertTrue(rendered)
        self.assertEqual(len(ui.markdown_calls), 1)
        self.assertIn("AAA", ui.markdown_calls[0][0])


if __name__ == "__main__":
    unittest.main()
