import copy
import inspect
import math
import unittest

import portfolio as portfolio_module
from portfolio import module_status, optimize_portfolio_candidates


def candidate(
    candidate_id,
    pci=70.0,
    cb=60.0,
    rd=60.0,
    sb=60.0,
    aic=60.0,
    max_corr=0.4,
    expected=10.0,
    risk=40.0,
    status="ok",
):
    facts = {
        "raw_portfolio_confidence_index": pci,
        "component_scores_raw": {
            "correlation_balance": cb,
            "risk_distribution": rd,
            "sector_balance": sb,
            "average_ai_confidence": aic,
            "expected_return_balance": 60.0,
        },
        "weighted_risk_score": risk,
        "risk_contributions": {"AAA": 0.25, "BBB": 0.25, "CCC": 0.25, "DDD": 0.25},
    }
    return {
        "status": status,
        "candidate_id": candidate_id,
        "symbols": ["AAA", "BBB", "CCC", "DDD"],
        "asset_count": 4,
        "weights": {"AAA": 0.25, "BBB": 0.25, "CCC": 0.25, "DDD": 0.25},
        "sector_weights": {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25},
        "facts": facts,
        "pci": {
            "portfolio_confidence_index": round(pci, 4) if isinstance(pci, float) and math.isfinite(pci) else pci,
            "correlation_balance_score": cb,
            "risk_distribution_score": rd,
            "sector_balance_score": sb,
            "average_ai_confidence": aic,
            "average_correlation": 0.22,
            "maximum_pair_correlation": max_corr,
            "maximum_sector_weight": 0.25,
            "expected_return_summary": {"weighted_mean": expected},
            "explanation_facts": facts,
        },
    }


def generation(candidates, status="ok"):
    return {"status": status, "candidates": candidates}


class PortfolioOptimizerTests(unittest.TestCase):
    def test_empty_candidate_list(self):
        result = optimize_portfolio_candidates(generation([]))
        self.assertEqual(result["status"], "empty")

    def test_invalid_top_n(self):
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                optimize_portfolio_candidates(generation([]), top_n=value)

    def test_pci_descending_order(self):
        result = optimize_portfolio_candidates(generation([candidate("low", 60), candidate("high", 80), candidate("mid", 70)]))
        self.assertEqual(self.ids(result), ["high", "mid", "low"])

    def test_binding_tie_break_sequence(self):
        values = [
            candidate("id-z", cb=70, rd=70, sb=70, aic=70, max_corr=0.2),
            candidate("cb", cb=80),
            candidate("rd", cb=70, rd=80),
            candidate("sb", cb=70, rd=70, sb=80),
            candidate("aic", cb=70, rd=70, sb=70, aic=80),
            candidate("corr", cb=70, rd=70, sb=70, aic=70, max_corr=0.1),
            candidate("id-a", cb=70, rd=70, sb=70, aic=70, max_corr=0.2),
        ]
        result = optimize_portfolio_candidates(generation(values))
        self.assertEqual(self.ids(result), ["cb", "rd", "sb", "aic", "corr", "id-a", "id-z"])
        self.assertFalse(result["ranked_candidates"][0]["ranking_facts"]["fallback_used"])

    def test_filters_are_applied(self):
        values = [candidate("pci", pci=50), candidate("risk", risk=90), candidate("return", expected=1), candidate("pass", pci=80, risk=20, expected=15)]
        result = optimize_portfolio_candidates(generation(values), min_pci=60, max_risk_score=50, min_expected_return=5)
        self.assertEqual(self.ids(result), ["pass"])
        codes = {reason["code"] for item in result["filtered_candidates"] for reason in item["reasons"]}
        self.assertTrue({"MIN_PCI_FILTER", "MAX_RISK_FILTER", "MIN_EXPECTED_RETURN_FILTER"}.issubset(codes))

    def test_duplicate_candidate_id_is_reported(self):
        result = optimize_portfolio_candidates(generation([candidate("dup", 80), candidate("dup", 70), candidate("ok", 60)]))
        self.assertEqual(self.ids(result), ["ok"])
        self.assertEqual(result["ranking_summary"]["duplicate_candidate_id_count"], 1)

    def test_rejected_candidate_is_excluded(self):
        result = optimize_portfolio_candidates(generation([candidate("bad", status="rejected"), candidate("good")]))
        self.assertEqual(self.ids(result), ["good"])

    def test_nan_and_infinity_pci_are_excluded(self):
        result = optimize_portfolio_candidates(generation([candidate("nan", math.nan), candidate("inf", math.inf), candidate("good", 70)]))
        self.assertEqual(self.ids(result), ["good"])

    def test_top_n_limit(self):
        result = optimize_portfolio_candidates(generation([candidate("a", 90), candidate("b", 80), candidate("c", 70)]), top_n=2)
        self.assertEqual(self.ids(result), ["a", "b"])

    def test_fewer_candidates_than_top_n(self):
        result = optimize_portfolio_candidates(generation([candidate("a"), candidate("b")]), top_n=20)
        self.assertEqual(len(result["ranked_candidates"]), 2)

    def test_input_is_not_mutated(self):
        source = generation([candidate("a"), candidate("b")])
        before = copy.deepcopy(source)
        optimize_portfolio_candidates(source)
        self.assertEqual(source, before)

    def test_same_input_is_deterministic(self):
        source = generation([candidate("b"), candidate("a")])
        self.assertEqual(optimize_portfolio_candidates(source), optimize_portfolio_candidates(source))

    def test_input_order_does_not_change_ranking(self):
        values = [candidate("a", 60), candidate("b", 80), candidate("c", 70)]
        self.assertEqual(self.ids(optimize_portfolio_candidates(generation(values))), self.ids(optimize_portfolio_candidates(generation(list(reversed(values))))))

    def test_structured_warning_and_filter_reason(self):
        result = optimize_portfolio_candidates(generation([candidate("bad", status="rejected")], status="rejected"))
        self.assertEqual(set(result["warnings"][0]), {"code", "message", "scope", "details"})
        self.assertEqual(set(result["filtered_candidates"][0]), {"candidate_id", "reasons"})
        self.assertEqual(set(result["filtered_candidates"][0]["reasons"][0]), {"code", "message", "scope", "details"})

    def test_optimizer_numbers_are_at_most_four_decimals(self):
        result = optimize_portfolio_candidates(generation([candidate("a", pci=70.123456, expected=10.123456, risk=40.123456)]))
        for value in result["ranked_candidates"][0]["optimizer_metrics"].values():
            if isinstance(value, float):
                self.assertEqual(value, round(value, 4))

    def test_module_status_is_unchanged(self):
        self.assertEqual(module_status(), "Portföy modülü gelecek sürümlerde aktif olacak.")

    def test_no_streamlit_yfinance_or_market_scan(self):
        source = inspect.getsource(portfolio_module.optimize_portfolio_candidates)
        self.assertNotIn("streamlit", source)
        self.assertNotIn("yfinance", source)
        self.assertNotIn("scan_smart_market", source)
        self.assertNotIn("download", source)

    @staticmethod
    def ids(result):
        return [item["candidate_id"] for item in result["ranked_candidates"]]


if __name__ == "__main__":
    unittest.main()
