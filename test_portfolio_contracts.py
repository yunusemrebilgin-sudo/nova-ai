import math
import unittest

from portfolio import (
    MissingDataAction,
    PCI_WEIGHTS,
    classify_missing_data,
    validate_horizon,
    validate_pci_weights,
    validate_required_fields,
    validate_score,
    validate_weight_sum,
)


class PortfolioContractValidationTests(unittest.TestCase):
    def test_valid_pci_weights(self) -> None:
        validate_pci_weights(PCI_WEIGHTS)

    def test_invalid_pci_weight_total(self) -> None:
        invalid = dict(PCI_WEIGHTS)
        invalid["expected_return_balance"] = 0.10
        with self.assertRaises(ValueError):
            validate_pci_weights(invalid)

    def test_score_above_100(self) -> None:
        with self.assertRaises(ValueError):
            validate_score(100.01)

    def test_negative_score(self) -> None:
        with self.assertRaises(ValueError):
            validate_score(-0.01)

    def test_nan_and_infinity_are_invalid(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_score(value)

    def test_invalid_portfolio_weight_total(self) -> None:
        with self.assertRaises(ValueError):
            validate_weight_sum((0.25, 0.25, 0.25))

    def test_invalid_horizon(self) -> None:
        with self.assertRaises(ValueError):
            validate_horizon("biweekly")

    def test_missing_critical_field(self) -> None:
        with self.assertRaisesRegex(ValueError, "portfolio_id"):
            validate_required_fields(
                {"portfolio_id": None, "horizon": "daily"},
                ("portfolio_id", "horizon"),
            )

    def test_critical_missing_data_maps_to_reject(self) -> None:
        result = classify_missing_data(
            "CRITICAL",
            warning_code="MISSING_AI_CONFIDENCE",
            affected_field="average_ai_confidence",
            explanation="Critical portfolio evidence is unavailable.",
        )
        self.assertEqual(result.action, MissingDataAction.REJECT)


if __name__ == "__main__":
    unittest.main()
