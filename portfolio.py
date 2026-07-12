"""Portfolio data contracts and validation primitives.

This module intentionally contains no portfolio scoring, optimization, sector
calculation, or UI behavior.  The structures below form the additive Part 1
contract for later portfolio-system stages.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
import hashlib
import itertools
import math
from typing import Any, Iterable, Mapping, Sequence


# The existing public behavior is retained unchanged.
def module_status() -> str:
    return "Portföy modülü gelecek sürümlerde aktif olacak."


PCI_WEIGHTS: dict[str, float] = {
    "average_ai_confidence": 0.25,
    "sector_balance": 0.20,
    "correlation_balance": 0.20,
    "risk_distribution": 0.20,
    "expected_return_balance": 0.15,
}

SECTOR_SCORE_WEIGHTS: dict[str, float] = {
    "sector_strength": 0.30,
    "sector_momentum": 0.25,
    "sector_trend": 0.25,
    "average_ai_confidence": 0.20,
}

SECTOR_STRENGTH_WEIGHTS: dict[str, float] = {
    "average_nova_score": 0.30,
    "average_ai_confidence": 0.30,
    "average_signal_strength": 0.20,
    "positive_candidate_ratio": 0.20,
}

MIN_PORTFOLIO_STOCKS = 4
MAX_PORTFOLIO_STOCKS = 6
MIN_PORTFOLIO_SECTORS = 3
MAX_PORTFOLIO_SECTORS = 4
MAX_STOCKS_PER_SECTOR = 2
DEFAULT_SAME_SECTOR_CORRELATION_LIMIT = 0.45
OVERRIDE_SAME_SECTOR_CORRELATION_LIMIT = 0.55
HIGH_CORRELATION_THRESHOLD = 0.65
EXTREME_CORRELATION_THRESHOLD = 0.80
MAX_SECTOR_WEIGHT = 0.50
MAX_SECOND_STOCK_SECTOR_WEIGHT = 0.40

VALID_HORIZONS = frozenset(
    {"daily", "weekly", "monthly", "quarterly", "6-month", "yearly"}
)
VALID_PORTFOLIO_STATUSES = frozenset(
    {"valid", "valid_with_warnings", "rejected"}
)
WEIGHT_SUM_TOLERANCE = 1e-9

HORIZON_MOMENTUM_PERIODS: Mapping[str, int] = {
    "daily": 1,
    "weekly": 5,
    "monthly": 21,
    "quarterly": 63,
    "6-month": 126,
    "yearly": 252,
}

# A return at this magnitude maps to either edge of the 0-100 momentum scale.
HORIZON_MOMENTUM_SCALES: Mapping[str, float] = {
    "daily": 0.02,
    "weekly": 0.05,
    "monthly": 0.10,
    "quarterly": 0.20,
    "6-month": 0.35,
    "yearly": 0.50,
}


class MissingDataSeverity(str, Enum):
    """Binding missing-data severity levels from appendix section 6."""

    CRITICAL = "CRITICAL"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class MissingDataAction(str, Enum):
    REJECT = "reject"
    WARNING_WITH_SCORE_PENALTY = "warning_with_score_penalty"
    WARNING_ONLY = "warning_only"


MISSING_DATA_ACTIONS: Mapping[MissingDataSeverity, MissingDataAction] = {
    MissingDataSeverity.CRITICAL: MissingDataAction.REJECT,
    MissingDataSeverity.MEDIUM: MissingDataAction.WARNING_WITH_SCORE_PENALTY,
    MissingDataSeverity.LOW: MissingDataAction.WARNING_ONLY,
}


@dataclass(frozen=True)
class MissingDataClassification:
    severity: MissingDataSeverity
    action: MissingDataAction
    warning_code: str
    affected_field: str
    explanation: str


@dataclass(frozen=True)
class SectorMetrics:
    sector: str
    horizon: str
    calculation_timestamp: datetime
    data_end_date: date
    metrics: Mapping[str, float] = field(default_factory=dict)
    warnings: tuple[Mapping[str, Any], ...] = ()
    sector_name: str = ""
    constituent_count: int = 0
    valid_constituent_count: int = 0
    sector_strength: float | None = None
    sector_momentum: float | None = None
    sector_trend: float | None = None
    sector_news_impact: float | None = None
    average_nova_score: float | None = None
    average_ai_confidence: float | None = None
    sector_score: float | None = None
    status: str = "incomplete"
    rejection_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PortfolioCandidate:
    portfolio_id: str
    horizon: str
    stocks: tuple[str, ...]
    sectors: tuple[str, ...]
    weights: tuple[float, ...]
    status: str
    calculation_timestamp: datetime
    data_end_date: date
    warnings: tuple[Mapping[str, Any], ...] = ()
    rejection_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PortfolioConfidenceResult:
    portfolio_confidence_index: float | None
    average_ai_confidence: float | None
    sector_balance_score: float | None
    correlation_balance_score: float | None
    risk_distribution_score: float | None
    expected_return_balance_score: float | None
    average_correlation: float | None
    maximum_pair_correlation: float | None
    high_correlation_pair_count: int
    extreme_correlation_pair_count: int
    stress_correlation: float | None
    sector_weights: Mapping[str, float]
    maximum_sector_weight: float | None
    maximum_risk_contribution: float | None
    explanation_facts: Mapping[str, Any]
    warnings: tuple[Mapping[str, Any], ...] = ()
    expected_return_summary: Mapping[str, Any] = field(default_factory=dict)
    rejection_reasons: tuple[str, ...] = ()
    status: str = "valid"
    horizon: str = "daily"
    calculation_timestamp: datetime | None = None
    data_end_date: date | None = None


@dataclass(frozen=True)
class PortfolioReportResult:
    portfolio_id: str
    numeric_summary: Mapping[str, Any]
    narrative_summary: str
    strongest_component: str
    weakest_component: str
    sector_analysis: Mapping[str, Any]
    correlation_analysis: Mapping[str, Any]
    risk_analysis: Mapping[str, Any]
    expected_return_analysis: Mapping[str, Any]
    warnings: tuple[Mapping[str, Any], ...] = ()


def validate_finite_number(value: Any, *, field_name: str = "value") -> float:
    """Return a finite numeric value or raise a field-specific ValueError."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite number")
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise ValueError(f"{field_name} must be a finite number")
    return numeric_value


def validate_score(value: Any, *, field_name: str = "score") -> float:
    """Validate a normalized inclusive 0-100 score without clamping it."""

    score = validate_finite_number(value, field_name=field_name)
    if not 0.0 <= score <= 100.0:
        raise ValueError(f"{field_name} must be between 0 and 100")
    return score


def validate_weight_sum(
    weights: Sequence[float] | Mapping[str, float],
    *,
    tolerance: float = WEIGHT_SUM_TOLERANCE,
    field_name: str = "weights",
) -> None:
    """Validate finite, non-negative weights whose total is exactly 1.0."""

    values = list(weights.values()) if isinstance(weights, Mapping) else list(weights)
    if not values:
        raise ValueError(f"{field_name} must not be empty")
    numeric_values = [
        validate_finite_number(value, field_name=field_name) for value in values
    ]
    if any(value < 0.0 for value in numeric_values):
        raise ValueError(f"{field_name} must contain only non-negative values")
    if not math.isclose(sum(numeric_values), 1.0, rel_tol=0.0, abs_tol=tolerance):
        raise ValueError(f"{field_name} must sum to 1.0")


def validate_pci_weights(weights: Mapping[str, float] = PCI_WEIGHTS) -> None:
    """Validate the centralized five-component PCI weight configuration."""

    if set(weights) != set(PCI_WEIGHTS):
        raise ValueError("PCI weights must contain exactly the five permanent components")
    validate_weight_sum(weights, field_name="PCI weights")


def validate_sector_score_weights(
    weights: Mapping[str, float] = SECTOR_SCORE_WEIGHTS,
) -> None:
    if set(weights) != set(SECTOR_SCORE_WEIGHTS):
        raise ValueError("Sector score weights must contain exactly four components")
    validate_weight_sum(weights, field_name="sector score weights")


def validate_required_fields(
    data: Mapping[str, Any], required_fields: Sequence[str]
) -> None:
    """Reject absent fields and fields explicitly set to None."""

    missing = [name for name in required_fields if name not in data or data[name] is None]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(sorted(missing))}")


def validate_horizon(horizon: str) -> str:
    if horizon not in VALID_HORIZONS:
        raise ValueError(
            f"horizon must be one of: {', '.join(sorted(VALID_HORIZONS))}"
        )
    return horizon


def classify_missing_data(
    severity: MissingDataSeverity | str,
    *,
    warning_code: str,
    affected_field: str,
    explanation: str,
) -> MissingDataClassification:
    """Create a deterministic classification; no penalty is calculated here."""

    try:
        normalized_severity = MissingDataSeverity(severity)
    except ValueError as exc:
        raise ValueError(f"Unknown missing-data severity: {severity}") from exc
    return MissingDataClassification(
        severity=normalized_severity,
        action=MISSING_DATA_ACTIONS[normalized_severity],
        warning_code=warning_code,
        affected_field=affected_field,
        explanation=explanation,
    )


def _warning(
    severity: MissingDataSeverity,
    code: str,
    affected_field: str,
    explanation: str,
    *,
    fallback_used: str | None = None,
) -> Mapping[str, Any]:
    result: dict[str, Any] = {
        "severity": severity.value,
        "warning_code": code,
        "affected_field": affected_field,
        "explanation": explanation,
    }
    if fallback_used is not None:
        result["fallback_used"] = fallback_used
    return result


def _first_present(row: Mapping[str, Any], names: Sequence[str]) -> Any:
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return None


def _valid_score_or_none(value: Any) -> float | None:
    try:
        return validate_score(value)
    except ValueError:
        return None


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _clamp_score(value: float) -> float:
    return min(100.0, max(0.0, value))


def _percentile(sorted_values: Sequence[float], percentile: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] + fraction * (
        sorted_values[upper] - sorted_values[lower]
    )


def _winsorized_mean(values: Sequence[float]) -> float:
    ordered = sorted(values)
    lower = _percentile(ordered, 0.10)
    upper = _percentile(ordered, 0.90)
    return _mean([min(upper, max(lower, value)) for value in values])


def _close_values(price_data: Any) -> list[float]:
    """Extract finite closes from a DataFrame-like object or plain sequence."""

    source = price_data
    if hasattr(price_data, "columns") and "Close" in price_data.columns:
        source = price_data["Close"]
    if hasattr(source, "tolist"):
        source = source.tolist()
    try:
        values = list(source)
    except TypeError:
        return []
    result = []
    for value in values:
        try:
            result.append(validate_finite_number(value, field_name="Close"))
        except ValueError:
            continue
    return result


def _symbol(row: Mapping[str, Any]) -> str:
    value = _first_present(row, ("symbol", "Hisse", "ticker"))
    return str(value).strip() if value is not None else ""


def _sector(row: Mapping[str, Any]) -> str:
    value = _first_present(row, ("sector", "Sektör", "Sector"))
    return str(value).strip() if value is not None else ""


def _trend_score(rows: Sequence[Mapping[str, Any]]) -> tuple[float | None, int]:
    scores: list[float] = []
    for row in rows:
        trend = _first_present(row, ("Trend", "trend"))
        if isinstance(trend, str):
            normalized = trend.strip().casefold()
            if normalized in {"pozitif", "positive", "yükseliş", "yukselis"}:
                scores.append(100.0)
            elif normalized in {"nötr", "notr", "neutral"}:
                scores.append(50.0)
            elif normalized in {"negatif", "negative", "düşüş", "dusus"}:
                scores.append(0.0)
        elif (score := _valid_score_or_none(trend)) is not None:
            scores.append(score)
    return (_mean(scores), len(scores)) if scores else (None, 0)


def _signal_strength(row: Mapping[str, Any]) -> float | None:
    direct = _first_present(
        row,
        ("signal_strength", "Sinyal Gücü", "Alım Uygunluğu %", "buy_suitability"),
    )
    score = _valid_score_or_none(direct)
    if score is not None:
        return score
    label = _first_present(row, ("Sonuç", "Sinyal", "signal"))
    if not isinstance(label, str):
        return None
    normalized = label.casefold()
    if "güçlü" in normalized or "strong" in normalized:
        return 100.0
    if "al" in normalized or "positive" in normalized:
        return 75.0
    if "izle" in normalized or "neutral" in normalized:
        return 50.0
    if "sat" in normalized or "negative" in normalized:
        return 0.0
    return None


def _candidate_is_positive(row: Mapping[str, Any]) -> bool:
    trend = _first_present(row, ("Trend", "trend"))
    label = _first_present(row, ("Sonuç", "Sinyal", "signal"))
    return (
        isinstance(trend, str) and trend.strip().casefold() in {"pozitif", "positive"}
    ) or (isinstance(label, str) and ("al" in label.casefold() or "positive" in label.casefold()))


def calculate_sector_momentum(
    rows: Sequence[Mapping[str, Any]],
    price_data_by_symbol: Mapping[str, Any],
    horizon: str,
) -> tuple[float | None, int]:
    """Calculate equal-weight, outlier-limited sector momentum from reused prices."""

    validate_horizon(horizon)
    periods = HORIZON_MOMENTUM_PERIODS[horizon]
    returns: list[float] = []
    for row in rows:
        closes = _close_values(price_data_by_symbol.get(_symbol(row), ()))
        if len(closes) < periods + 1 or closes[-periods - 1] <= 0:
            continue
        stock_return = closes[-1] / closes[-periods - 1] - 1.0
        if math.isfinite(stock_return):
            returns.append(stock_return)
    if not returns:
        return None, 0
    sector_return = _winsorized_mean(returns)
    scale = HORIZON_MOMENTUM_SCALES[horizon]
    return _clamp_score(50.0 + 50.0 * sector_return / scale), len(returns)


def calculate_sector_metrics(
    sector_name: str,
    candidates: Iterable[Mapping[str, Any]],
    price_data_by_symbol: Mapping[str, Any],
    horizon: str,
    *,
    calculation_timestamp: datetime | None = None,
    data_end_date: date | None = None,
) -> SectorMetrics:
    """Build one sector result without scanning or downloading market data."""

    validate_horizon(horizon)
    timestamp = calculation_timestamp or datetime.now().astimezone()
    end_date = data_end_date or timestamp.date()
    normalized_sector = str(sector_name or "").strip()
    rows = list(candidates)
    warnings: list[Mapping[str, Any]] = []
    rejection_reasons: list[str] = []

    if not normalized_sector:
        rejection_reasons.append("Sector name is missing.")
        return SectorMetrics(
            sector="",
            sector_name="",
            horizon=horizon,
            calculation_timestamp=timestamp,
            data_end_date=end_date,
            constituent_count=len(rows),
            valid_constituent_count=0,
            status="rejected",
            warnings=(),
            rejection_reasons=tuple(rejection_reasons),
        )
    if not rows:
        rejection_reasons.append("Sector has no candidate constituents.")
        return SectorMetrics(
            sector=normalized_sector,
            sector_name=normalized_sector,
            horizon=horizon,
            calculation_timestamp=timestamp,
            data_end_date=end_date,
            constituent_count=0,
            valid_constituent_count=0,
            status="rejected",
            rejection_reasons=tuple(rejection_reasons),
        )

    nova_values = [
        score
        for row in rows
        if (score := _valid_score_or_none(_first_present(row, ("Nova Score", "Nova Skoru", "nova_score"))))
        is not None
    ]
    missing_nova = len(rows) - len(nova_values)
    if missing_nova:
        warnings.append(
            _warning(
                MissingDataSeverity.MEDIUM,
                "MISSING_NOVA_SCORE",
                "average_nova_score",
                f"{missing_nova} constituent(s) were excluded from the Nova average.",
                fallback_used="excluded invalid Nova values",
            )
        )
    if not nova_values:
        rejection_reasons.append("No valid Nova scores are available.")

    ai_values = [
        score
        for row in rows
        if (score := _valid_score_or_none(_first_present(row, ("AI Güven Endeksi", "AI Confidence", "ai_confidence"))))
        is not None
    ]
    missing_ai = len(rows) - len(ai_values)
    average_ai: float | None = None
    if missing_ai > 1 or not ai_values:
        rejection_reasons.append("More than one AI Confidence value is missing or invalid.")
    else:
        average_ai = _mean(ai_values)
        if missing_ai == 1:
            average_ai = _clamp_score(average_ai - 8.0)
            warnings.append(
                _warning(
                    MissingDataSeverity.MEDIUM,
                    "MISSING_AI_CONFIDENCE",
                    "average_ai_confidence",
                    "One missing AI Confidence used the valid-holding mean with an 8-point penalty.",
                    fallback_used="valid-holding mean minus 8 points",
                )
            )

    news_values = [
        value
        for row in rows
        if (value := _valid_score_or_none(
            _first_present(row, ("Haber Etkisi Skoru", "news_impact_score"))
        ))
        is not None
    ]
    # Scanner news impact is a signed percentage; map it only for explanation.
    for row in rows:
        signed_news = _first_present(row, ("Haber Etkisi %", "news_impact"))
        if signed_news is not None:
            try:
                news_values.append(
                    _clamp_score(50.0 + 5.0 * validate_finite_number(signed_news))
                )
            except ValueError:
                pass
    news_impact = _mean(news_values) if news_values else None
    if news_impact is None:
        warnings.append(
            _warning(
                MissingDataSeverity.LOW,
                "MISSING_NEWS_IMPACT",
                "sector_news_impact",
                "News Impact is unavailable; sector scoring continues without it.",
                fallback_used="none; News Impact excluded from sector score",
            )
        )

    momentum, momentum_count = calculate_sector_momentum(
        rows, price_data_by_symbol, horizon
    )
    if momentum_count < len(rows):
        warnings.append(
            _warning(
                MissingDataSeverity.MEDIUM,
                "INSUFFICIENT_PRICE_HISTORY",
                "sector_momentum",
                f"Momentum used {momentum_count} of {len(rows)} constituents.",
                fallback_used="excluded insufficient price histories",
            )
        )
    if momentum is None:
        rejection_reasons.append("No constituent has sufficient price history.")

    trend, trend_count = _trend_score(rows)
    if trend_count < len(rows):
        warnings.append(
            _warning(
                MissingDataSeverity.MEDIUM,
                "MISSING_TREND",
                "sector_trend",
                f"Trend used {trend_count} of {len(rows)} constituents.",
                fallback_used="excluded invalid trend values",
            )
        )
    if trend is None:
        rejection_reasons.append("No valid trend values are available.")

    signal_values = [value for row in rows if (value := _signal_strength(row)) is not None]
    average_nova = _mean(nova_values) if nova_values else None
    strength: float | None = None
    if average_nova is not None and average_ai is not None:
        average_signal = _mean(signal_values) if signal_values else 50.0
        if not signal_values:
            warnings.append(
                _warning(
                    MissingDataSeverity.LOW,
                    "MISSING_SIGNAL_STRENGTH",
                    "sector_strength",
                    "Signal strength is unavailable; the documented neutral strength input was used.",
                    fallback_used="50-point neutral signal input",
                )
            )
        positive_ratio = 100.0 * sum(_candidate_is_positive(row) for row in rows) / len(rows)
        strength = sum(
            (
                average_nova * SECTOR_STRENGTH_WEIGHTS["average_nova_score"],
                average_ai * SECTOR_STRENGTH_WEIGHTS["average_ai_confidence"],
                average_signal * SECTOR_STRENGTH_WEIGHTS["average_signal_strength"],
                positive_ratio * SECTOR_STRENGTH_WEIGHTS["positive_candidate_ratio"],
            )
        )
        strength = _clamp_score(strength)

    critical_components = (strength, momentum, trend, average_ai)
    sector_score = None
    if not rejection_reasons and all(value is not None for value in critical_components):
        sector_score = sum(
            validate_score(value, field_name=name) * SECTOR_SCORE_WEIGHTS[name]
            for name, value in zip(SECTOR_SCORE_WEIGHTS, critical_components)
        )
        sector_score = validate_score(sector_score, field_name="sector_score")

    status = "rejected" if rejection_reasons else ("valid_with_warnings" if warnings else "valid")
    valid_count = min(len(nova_values), len(ai_values), momentum_count, trend_count)
    metric_values = {
        name: value
        for name, value in {
            "sector_strength": strength,
            "sector_momentum": momentum,
            "sector_trend": trend,
            "sector_news_impact": news_impact,
            "average_nova_score": average_nova,
            "average_ai_confidence": average_ai,
            "sector_score": sector_score,
        }.items()
        if value is not None
    }
    return SectorMetrics(
        sector=normalized_sector,
        sector_name=normalized_sector,
        horizon=horizon,
        calculation_timestamp=timestamp,
        data_end_date=end_date,
        metrics=metric_values,
        constituent_count=len(rows),
        valid_constituent_count=valid_count,
        sector_strength=strength,
        sector_momentum=momentum,
        sector_trend=trend,
        sector_news_impact=news_impact,
        average_nova_score=average_nova,
        average_ai_confidence=average_ai,
        sector_score=sector_score,
        status=status,
        warnings=tuple(warnings),
        rejection_reasons=tuple(rejection_reasons),
    )


def calculate_sector_engine(
    candidates: Iterable[Mapping[str, Any]],
    price_data_by_symbol: Mapping[str, Any],
    horizon: str,
    *,
    calculation_timestamp: datetime | None = None,
    data_end_date: date | None = None,
) -> tuple[SectorMetrics, ...]:
    """Group existing scanner candidates and calculate one result per sector."""

    validate_horizon(horizon)
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in candidates:
        grouped.setdefault(_sector(row), []).append(row)
    return tuple(
        calculate_sector_metrics(
            sector_name,
            rows,
            price_data_by_symbol,
            horizon,
            calculation_timestamp=calculation_timestamp,
            data_end_date=data_end_date,
        )
        for sector_name, rows in sorted(grouped.items())
    )


HORIZON_CORRELATION_RULES: Mapping[str, tuple[int, int, int]] = {
    "daily": (80, 60, 20),
    "weekly": (160, 120, 30),
    "monthly": (80, 52, 12),
    "quarterly": (120, 104, 26),
    "6-month": (180, 156, 39),
    "yearly": (250, 208, 52),
}


def _interpolate_score(value: float, points: Sequence[tuple[float, float]]) -> float:
    value = max(0.0, value)
    if value <= points[0][0]:
        return points[0][1]
    for (left_x, left_y), (right_x, right_y) in zip(points, points[1:]):
        if value <= right_x:
            ratio = (value - left_x) / (right_x - left_x)
            return left_y + ratio * (right_y - left_y)
    return points[-1][1]


def _weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    return sum(value * weight for value, weight in zip(values, weights)) / sum(weights)


def _hhi_balance(values: Sequence[float]) -> float:
    if len(values) <= 1:
        return 0.0
    hhi = sum(value * value for value in values)
    ideal = 1.0 / len(values)
    return _clamp_score(100.0 * (1.0 - (hhi - ideal) / (1.0 - ideal)))


def _dominance_score(value: float) -> float:
    if value <= 0.30:
        return 100.0
    if value <= 0.40:
        return 100.0 - 40.0 * (value - 0.30) / 0.10
    if value <= 0.50:
        return 60.0 - 60.0 * (value - 0.40) / 0.10
    return 0.0


def _returns(prices: Any) -> list[float]:
    closes = _close_values(prices)
    return [
        closes[index] / closes[index - 1] - 1.0
        for index in range(1, len(closes))
        if closes[index - 1] > 0
    ]


def _correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    count = min(len(left), len(right))
    if count < 2:
        return None
    x, y = list(left[-count:]), list(right[-count:])
    mean_x, mean_y = _mean(x), _mean(y)
    dx, dy = [value - mean_x for value in x], [value - mean_y for value in y]
    denominator = math.sqrt(sum(value * value for value in dx) * sum(value * value for value in dy))
    if denominator <= 0.0:
        return None
    result = sum(a * b for a, b in zip(dx, dy)) / denominator
    return max(-1.0, min(1.0, result))


def _percentile_rank(universe: Sequence[float], value: float) -> float:
    ordered = sorted(universe)
    if len(ordered) == 1:
        return 50.0
    below = sum(item < value for item in ordered)
    equal = sum(item == value for item in ordered)
    return 100.0 * (below + 0.5 * equal) / len(ordered)


def _metric(row: Mapping[str, Any], aliases: Sequence[str]) -> float | None:
    return _valid_score_or_none(_first_present(row, aliases))


def _component_warning(
    warnings: list[Mapping[str, Any]], severity: MissingDataSeverity, code: str,
    component: str, explanation: str, penalty: float = 0.0, fallback: str | None = None,
) -> None:
    warning = dict(_warning(severity, code, component, explanation, fallback_used=fallback))
    warning["numerical_penalty"] = penalty
    warnings.append(warning)


def _candidate_parts(candidate: PortfolioCandidate | Mapping[str, Any]) -> tuple[list[str], list[str], list[float]]:
    if isinstance(candidate, PortfolioCandidate):
        stocks, sectors, weights = list(candidate.stocks), list(candidate.sectors), list(candidate.weights)
    else:
        validate_required_fields(candidate, ("stocks", "sectors", "weights"))
        stocks, sectors, weights = list(candidate["stocks"]), list(candidate["sectors"]), list(candidate["weights"])
    if not (len(stocks) == len(sectors) == len(weights)):
        raise ValueError("stocks, sectors, and weights must have equal lengths")
    validate_weight_sum(weights)
    return stocks, sectors, [validate_finite_number(value, field_name="weight") for value in weights]


def _round4(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def calculate_portfolio_confidence(
    candidate: PortfolioCandidate | Mapping[str, Any],
    horizon: str,
    stock_metrics: Mapping[str, Mapping[str, Any]],
    sector_metrics: Mapping[str, SectorMetrics | Mapping[str, Any]],
    price_data_by_symbol: Mapping[str, Any],
    reference_universe: Sequence[Mapping[str, Any]],
    *,
    calculation_timestamp: datetime | None = None,
    data_end_date: date | None = None,
) -> PortfolioConfidenceResult:
    """Calculate the binding five-component PCI from caller-provided evidence."""

    validate_horizon(horizon)
    stocks, sectors, weights = _candidate_parts(candidate)
    timestamp = calculation_timestamp or datetime.now().astimezone()
    end_date = data_end_date or timestamp.date()
    warnings: list[Mapping[str, Any]] = []
    rejection_reasons: list[str] = []
    penalties: dict[str, list[float]] = {name: [] for name in PCI_WEIGHTS}

    # AIC: one missing value uses the valid mean and receives the binding -8 penalty.
    ai_values = []
    for stock in stocks:
        row = stock_metrics.get(stock, {})
        metric_horizon = row.get("horizon")
        ai_values.append(
            None
            if metric_horizon is not None and metric_horizon != horizon
            else _metric(row, ("ai_confidence", "AI Güven Endeksi", "AI Confidence"))
        )
    valid_ai = [value for value in ai_values if value is not None]
    missing_ai = len(ai_values) - len(valid_ai)
    aic: float | None = None
    if missing_ai > 1 or not valid_ai:
        rejection_reasons.append("AIC: more than one AI Confidence value is missing or invalid.")
    else:
        filled_ai = [(_mean(valid_ai) if value is None else value) for value in ai_values]
        aic = _weighted_mean(filled_ai, weights)
        if missing_ai == 1:
            aic = _clamp_score(aic - 8.0)
            penalties["average_ai_confidence"].append(8.0)
            _component_warning(warnings, MissingDataSeverity.MEDIUM, "MISSING_AI_CONFIDENCE", "average_ai_confidence", "One missing AI Confidence used the valid-holding mean.", 8.0, "valid-holding mean")

    # SB: count, HHI, and dominant-sector subscores.
    normalized_sectors = [str(value or "").strip() for value in sectors]
    missing_sector_indices = [index for index, value in enumerate(normalized_sectors) if not value]
    sb_penalty = 0.0
    if len(missing_sector_indices) > 1 or any(weights[index] > 0.25 for index in missing_sector_indices):
        rejection_reasons.append("SB: critical sector data is missing.")
    else:
        if missing_sector_indices:
            normalized_sectors[missing_sector_indices[0]] = "Unclassified"
            sb_penalty += 12.0
            _component_warning(warnings, MissingDataSeverity.MEDIUM, "MISSING_SECTOR", "sector_balance", "One small unknown sector was assigned to Unclassified.", 12.0, "Unclassified")
    sector_weights: dict[str, float] = {}
    for sector, weight in zip(normalized_sectors, weights):
        if sector:
            sector_weights[sector] = sector_weights.get(sector, 0.0) + weight
    maximum_sector_weight = max(sector_weights.values(), default=0.0)
    if maximum_sector_weight > MAX_SECTOR_WEIGHT:
        rejection_reasons.append("SB: a sector exceeds the 50% hard concentration limit.")
    sector_count = len(sector_weights)
    sns = {1: 0.0, 2: 40.0, 3: 90.0, 4: 100.0}.get(sector_count, 90.0)
    if sector_count == 2:
        sb_penalty += 15.0
        _component_warning(warnings, MissingDataSeverity.MEDIUM, "TWO_SECTORS_ONLY", "sector_balance", "Only two sectors are represented.", 15.0)
    hcs = _hhi_balance(list(sector_weights.values()))
    dss = _dominance_score(maximum_sector_weight)
    sb = _clamp_score(0.35 * sns + 0.40 * hcs + 0.25 * dss - sb_penalty)
    penalties["sector_balance"].append(sb_penalty)

    # CB: align horizon returns, calculate pair facts, then find the worst basket window.
    minimum_observations, correlation_window, stress_window = HORIZON_CORRELATION_RULES[horizon]
    return_series = {stock: _returns(price_data_by_symbol.get(stock, ())) for stock in stocks}
    if any(len(series) < minimum_observations for series in return_series.values()):
        rejection_reasons.append("CB: minimum common observation requirement is not met.")
    common_count = min((len(series) for series in return_series.values()), default=0)
    aligned = {stock: series[-common_count:] for stock, series in return_series.items()} if common_count else {}
    normal = {stock: series[-correlation_window:] for stock, series in aligned.items()}
    pair_values: list[tuple[str, str, float]] = []
    for left_index, left in enumerate(stocks):
        for right in stocks[left_index + 1:]:
            value = _correlation(normal.get(left, ()), normal.get(right, ()))
            if value is None:
                rejection_reasons.append(f"CB: invalid correlation pair {left}-{right}.")
            else:
                pair_values.append((left, right, value))
    average_correlation = _mean([value for _, _, value in pair_values]) if pair_values else None
    maximum_pair = max((value for _, _, value in pair_values), default=None)
    high_count = sum(value >= HIGH_CORRELATION_THRESHOLD for _, _, value in pair_values)
    extreme_count = sum(value >= EXTREME_CORRELATION_THRESHOLD for _, _, value in pair_values)
    stress_correlation: float | None = None
    if common_count >= stress_window and aligned:
        basket = [_mean([aligned[stock][index] for stock in stocks]) for index in range(common_count)]
        worst_start = min(
            range(common_count - stress_window + 1),
            key=lambda start: math.prod(
                1.0 + value for value in basket[start:start + stress_window]
            ) - 1.0,
        )
        stress_pairs = []
        for left_index, left in enumerate(stocks):
            for right in stocks[left_index + 1:]:
                value = _correlation(aligned[left][worst_start:worst_start + stress_window], aligned[right][worst_start:worst_start + stress_window])
                if value is not None:
                    stress_pairs.append(value)
        stress_correlation = _mean(stress_pairs) if stress_pairs else None
    if stress_correlation is None:
        _component_warning(warnings, MissingDataSeverity.MEDIUM, "MISSING_STRESS_CORRELATION", "correlation_balance", "Stress correlation could not be calculated.", 5.0, "SCS=40")
        penalties["correlation_balance"].append(5.0)
    if average_correlation is not None and stress_correlation is not None and stress_correlation - average_correlation >= 0.20:
        _component_warning(warnings, MissingDataSeverity.LOW, "DIVERSIFICATION_WEAKENS_UNDER_STRESS", "correlation_balance", "Stres döneminde çeşitlendirme zayıflıyor.")
    if stress_correlation is not None and stress_correlation > HIGH_CORRELATION_THRESHOLD:
        _component_warning(warnings, MissingDataSeverity.LOW, "HIGH_STRESS_CORRELATION", "correlation_balance", "Stress-period correlation is above 0.65.")
    cb: float | None = None
    if average_correlation is not None and maximum_pair is not None:
        acs = _interpolate_score(average_correlation, ((0.25, 100), (0.45, 80), (0.65, 50), (0.80, 20), (1.0, 0)))
        mcs = _interpolate_score(maximum_pair, ((0.45, 100), (0.65, 70), (0.80, 30), (1.0, 0)))
        hps = _clamp_score(100.0 * (1.0 - high_count / len(pair_values)) - 10.0 * extreme_count)
        scs = 40.0 if stress_correlation is None else _interpolate_score(stress_correlation, ((0.25, 100), (0.45, 80), (0.65, 50), (0.80, 20), (1.0, 0)))
        if stress_correlation is not None and stress_correlation > 0.80:
            scs = min(scs, 20.0)
        cb = _clamp_score(0.40 * acs + 0.25 * mcs + 0.15 * hps + 0.20 * scs - sum(penalties["correlation_balance"]))

    # Same-horizon reference universe for RD and ERB percentiles.
    valid_reference = []
    for row in reference_universe:
        sell = _metric(row, ("sell_risk", "Sat Riski %"))
        volatility = _metric(row, ("volatility_percentile", "volatility", "Volatilite"))
        downside = _metric(row, ("downside_deviation_percentile", "downside_deviation"))
        expected = _first_present(row, ("expected_return", "Beklenen Getiri %"))
        try:
            expected_value = validate_finite_number(expected, field_name="expected_return")
        except ValueError:
            expected_value = None
        if None not in (sell, volatility, downside, expected_value):
            valid_reference.append((sell, volatility, downside, expected_value))
    universe_count = len(valid_reference)
    if universe_count < 10:
        rejection_reasons.append("RD/ERB: reference universe has fewer than 10 valid candidates.")
    universe_penalty = 8.0 if 10 <= universe_count < 20 else 0.0
    if universe_penalty:
        _component_warning(warnings, MissingDataSeverity.MEDIUM, "NARROW_REFERENCE_UNIVERSE", "risk_distribution", "Reference universe contains 10-19 candidates.", 8.0)
        _component_warning(warnings, MissingDataSeverity.MEDIUM, "NARROW_REFERENCE_UNIVERSE", "expected_return_balance", "Reference universe contains 10-19 candidates.", 8.0)

    rd: float | None = None
    maximum_risk_contribution: float | None = None
    weighted_risk_score: float | None = None
    risk_contributions: dict[str, float] = {}
    if valid_reference:
        reference_columns = list(zip(*valid_reference))
        risk_rows = []
        incomplete_holdings = 0
        for stock in stocks:
            row = stock_metrics.get(stock, {})
            raw = [_metric(row, aliases) for aliases in (("sell_risk", "Sat Riski %"), ("volatility_percentile", "volatility", "Volatilite"), ("downside_deviation_percentile", "downside_deviation"))]
            if any(value is None for value in raw):
                incomplete_holdings += 1
                raw = [_percentile(sorted(reference_columns[index]), 0.75) if value is None else value for index, value in enumerate(raw)]
            volatility_percentile = _percentile_rank(reference_columns[1], raw[1])
            downside_percentile = _percentile_rank(reference_columns[2], raw[2])
            risk_rows.append(
                0.45 * raw[0]
                + 0.30 * volatility_percentile
                + 0.25 * downside_percentile
            )
        if incomplete_holdings > 1:
            rejection_reasons.append("RD: more than one holding has incomplete risk inputs.")
        else:
            rd_penalty = universe_penalty + (10.0 if incomplete_holdings == 1 else 0.0)
            if incomplete_holdings == 1:
                _component_warning(warnings, MissingDataSeverity.MEDIUM, "INCOMPLETE_RISK_INPUT", "risk_distribution", "One holding used candidate-universe 75th-percentile risk substitution.", 10.0, "75th percentile")
            total_risk = sum(weight * risk for weight, risk in zip(weights, risk_rows))
            weighted_risk_score = total_risk
            contributions = [(weight * risk / total_risk if total_risk > 0 else weight) for weight, risk in zip(weights, risk_rows)]
            risk_contributions = dict(zip(stocks, contributions))
            maximum_risk_contribution = max(contributions)
            rbs = _hhi_balance(contributions)
            arq = _clamp_score(100.0 - total_risk)
            drs = _dominance_score(maximum_risk_contribution)
            if maximum_risk_contribution > 0.50:
                rd_penalty += 5.0
                _component_warning(warnings, MissingDataSeverity.MEDIUM, "DOMINANT_RISK_CONTRIBUTION", "risk_distribution", "Maximum risk contribution exceeds 50%.", 5.0)
            rd = _clamp_score(0.50 * rbs + 0.30 * arq + 0.20 * drs - rd_penalty)
            penalties["risk_distribution"].append(rd_penalty)

    erb: float | None = None
    expected_summary: dict[str, Any] = {}
    if valid_reference:
        universe_returns = [row[3] for row in valid_reference]
        ordered_returns = sorted(universe_returns)
        lower, upper = _percentile(ordered_returns, 0.05), _percentile(ordered_returns, 0.95)
        winsorized_universe = [min(upper, max(lower, value)) for value in universe_returns]
        holding_returns: list[float | None] = []
        for stock in stocks:
            value = _first_present(stock_metrics.get(stock, {}), ("expected_return", "Beklenen Getiri %"))
            try:
                holding_returns.append(validate_finite_number(value, field_name="expected_return"))
            except ValueError:
                holding_returns.append(None)
        missing_return = sum(value is None for value in holding_returns)
        if missing_return > 1:
            rejection_reasons.append("ERB: more than one expected return is missing.")
        else:
            erb_penalty = universe_penalty
            if missing_return == 1:
                fallback = min(0.0, _percentile(ordered_returns, 0.25))
                holding_returns = [fallback if value is None else value for value in holding_returns]
                erb_penalty += 10.0
                _component_warning(warnings, MissingDataSeverity.MEDIUM, "MISSING_EXPECTED_RETURN", "expected_return_balance", "One expected return used the conservative documented substitution.", 10.0, "lower of zero and universe 25th percentile")
            actual_returns = [float(value) for value in holding_returns]
            scoring_returns = [min(upper, max(lower, value)) for value in actual_returns]
            rqs = _weighted_mean([_percentile_rank(winsorized_universe, value) for value in scoring_returns], weights)
            mean_return = _weighted_mean(actual_returns, weights)
            variance = _mean([(value - _mean(actual_returns)) ** 2 for value in actual_returns])
            cv = math.sqrt(variance) / max(abs(_mean(actual_returns)), 1e-12)
            ebs = 100.0 * (1.0 - min(cv, 1.50) / 1.50)
            if mean_return <= 0:
                ebs = min(ebs, 40.0)
            contributions = [weight * max(value, 0.0) for weight, value in zip(weights, actual_returns)]
            total_positive = sum(contributions)
            rcs = 0.0 if total_positive == 0 else _hhi_balance([value / total_positive for value in contributions])
            if all(value <= 0 for value in actual_returns):
                _component_warning(warnings, MissingDataSeverity.LOW, "ALL_EXPECTED_RETURNS_NON_POSITIVE", "expected_return_balance", "All expected returns are non-positive; EBS is capped at 40.")
            erb = _clamp_score(0.45 * rqs + 0.35 * ebs + 0.20 * rcs - erb_penalty)
            penalties["expected_return_balance"].append(erb_penalty)
            expected_summary = {"weighted_mean": mean_return, "minimum": min(actual_returns), "maximum": max(actual_returns), "return_quality_score": rqs, "return_balance_score": ebs, "return_contribution_score": rcs}

    components = {"average_ai_confidence": aic, "sector_balance": sb, "correlation_balance": cb, "risk_distribution": rd, "expected_return_balance": erb}
    pci_raw: float | None = None
    if not rejection_reasons and all(value is not None for value in components.values()):
        pci_raw = _clamp_score(sum(float(components[name]) * PCI_WEIGHTS[name] for name in PCI_WEIGHTS))
    status = "rejected" if rejection_reasons else ("valid_with_warnings" if warnings else "valid")
    strongest = max(components, key=lambda key: components[key] if components[key] is not None else -1)
    weakest = min(components, key=lambda key: components[key] if components[key] is not None else 101)
    highest_pair = max(pair_values, key=lambda item: item[2]) if pair_values else None
    explanation_facts = {
        "raw_portfolio_confidence_index": pci_raw,
        "component_scores_raw": components,
        "strongest_component": strongest,
        "weakest_component": weakest,
        "highest_correlation_pair": highest_pair,
        "dominant_sector": max(sector_weights, key=sector_weights.get) if sector_weights else None,
        "highest_risk_contribution_stock": max(risk_contributions, key=risk_contributions.get) if risk_contributions else None,
        "risk_contributions": risk_contributions,
        "weighted_risk_score": weighted_risk_score,
        "penalties": penalties,
        "stress_diversification_warning": average_correlation is not None and stress_correlation is not None and stress_correlation - average_correlation >= 0.20,
    }
    return PortfolioConfidenceResult(
        portfolio_confidence_index=_round4(pci_raw), average_ai_confidence=_round4(aic), sector_balance_score=_round4(sb), correlation_balance_score=_round4(cb), risk_distribution_score=_round4(rd), expected_return_balance_score=_round4(erb),
        average_correlation=_round4(average_correlation), maximum_pair_correlation=_round4(maximum_pair), high_correlation_pair_count=high_count, extreme_correlation_pair_count=extreme_count, stress_correlation=_round4(stress_correlation), sector_weights={key: round(value, 4) for key, value in sector_weights.items()}, maximum_sector_weight=_round4(maximum_sector_weight), maximum_risk_contribution=_round4(maximum_risk_contribution), explanation_facts=explanation_facts, warnings=tuple(warnings), expected_return_summary={key: _round4(value) if isinstance(value, float) else value for key, value in expected_summary.items()}, rejection_reasons=tuple(rejection_reasons), status=status, horizon=horizon, calculation_timestamp=timestamp, data_end_date=end_date,
    )


def build_candidate_id(
    symbols: Sequence[str], weights: Sequence[float], horizon: str
) -> str:
    """Return a stable identity for one canonical weighted portfolio."""

    validate_horizon(horizon)
    if len(symbols) != len(weights):
        raise ValueError("symbols and weights must have equal lengths")
    payload = "|".join(
        [horizon]
        + [
            f"{symbol}:{validate_finite_number(weight, field_name='weight'):.12f}"
            for symbol, weight in zip(symbols, weights)
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def equal_weight_scenario(symbols: Sequence[str]) -> tuple[list[float], dict[str, float]]:
    """Return raw equal weights and deterministic four-decimal display weights."""

    canonical = list(symbols)
    if len(canonical) < 2 or canonical != sorted(canonical) or len(set(canonical)) != len(canonical):
        raise ValueError("symbols must be unique and in canonical order")
    raw = [1.0 / len(canonical)] * len(canonical)
    total_units = 10_000
    base_units = total_units // len(canonical)
    remainder = total_units - base_units * len(canonical)
    # Largest-remainder ties are resolved by canonical symbol order.
    units = [base_units + (1 if index < remainder else 0) for index in range(len(canonical))]
    display = {symbol: unit / total_units for symbol, unit in zip(canonical, units)}
    validate_weight_sum(raw)
    validate_weight_sum(display, tolerance=0.0)
    return raw, display


def _candidate_warning(code: str, message: str, scope: str, **details: Any) -> Mapping[str, Any]:
    return {"code": code, "message": message, "scope": scope, "details": details}


def _candidate_rejection(
    symbols: Sequence[str], weights: Mapping[str, float], stage: str,
    reasons: Sequence[str], candidate_id: str | None = None,
) -> Mapping[str, Any]:
    return {
        "candidate_id": candidate_id,
        "symbols": list(symbols),
        "weights": dict(weights),
        "rejection_stage": stage,
        "rejection_reasons": list(reasons),
    }


def _normalized_input_row(row: Mapping[str, Any]) -> dict[str, Any]:
    symbol = _symbol(row)
    sector = _sector(row)
    normalized = dict(row)
    normalized.update(
        {
            "symbol": symbol,
            "sector": sector,
            "ai_confidence": _first_present(row, ("ai_confidence", "AI Güven Endeksi", "AI Confidence")),
            "expected_return": _first_present(row, ("expected_return", "Beklenen Getiri %")),
            "sell_risk": _first_present(row, ("sell_risk", "risk_score", "Sat Riski %")),
            "volatility": _first_present(row, ("volatility", "Volatilite")),
            "downside_deviation": _first_present(row, ("downside_deviation", "Downside Deviation")),
            "price_series": _first_present(row, ("price_series", "prices", "Price Series")),
        }
    )
    return normalized


def _invalid_present_number(row: Mapping[str, Any], names: Sequence[str]) -> bool:
    value = _first_present(row, names)
    if value is None:
        return False
    try:
        validate_finite_number(value)
        return False
    except ValueError:
        return True


def _sector_precheck(
    rows: Sequence[Mapping[str, Any]], raw_weights: Sequence[float]
) -> list[str]:
    sectors = [str(row.get("sector") or "").strip() for row in rows]
    missing = [index for index, sector in enumerate(sectors) if not sector]
    if len(missing) > 1:
        return ["More than one sector is missing."]
    if missing and raw_weights[missing[0]] > 0.25:
        return ["Missing-sector weight exceeds 25%."]
    sector_weights: dict[str, float] = {}
    counts: dict[str, int] = {}
    for sector, weight in zip(sectors, raw_weights):
        key = sector or "Unclassified"
        sector_weights[key] = sector_weights.get(key, 0.0) + weight
        counts[key] = counts.get(key, 0) + 1
    if max(sector_weights.values(), default=0.0) > MAX_SECTOR_WEIGHT:
        return ["A sector exceeds the 50% hard concentration limit."]
    if len(sector_weights) > 2 and any(
        counts[sector] > 1 and weight > MAX_SECOND_STOCK_SECTOR_WEIGHT
        for sector, weight in sector_weights.items()
    ):
        return ["A repeated sector exceeds the 40% concentration limit."]
    return []


def generate_portfolio_candidates(
    candidates: Sequence[Mapping[str, Any]],
    horizon: str,
    *,
    min_assets: int = MIN_PORTFOLIO_STOCKS,
    max_assets: int = MAX_PORTFOLIO_STOCKS,
    max_combinations: int | None = None,
    reference_universe: Sequence[Mapping[str, Any]] | None = None,
    sector_metrics: Mapping[str, SectorMetrics | Mapping[str, Any]] | None = None,
    stock_metrics_by_symbol: Mapping[str, Mapping[str, Any]] | None = None,
    price_data_by_symbol: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Generate canonical equal-weight candidates and evaluate each through Part 3 PCI."""

    validate_horizon(horizon)
    if isinstance(min_assets, bool) or not isinstance(min_assets, int) or min_assets < 2:
        raise ValueError("min_assets must be an integer of at least 2")
    if isinstance(max_assets, bool) or not isinstance(max_assets, int) or max_assets < min_assets:
        raise ValueError("max_assets must be an integer not smaller than min_assets")
    if max_combinations is not None and (
        isinstance(max_combinations, bool)
        or not isinstance(max_combinations, int)
        or max_combinations < 1
    ):
        raise ValueError("max_combinations must be None or a positive integer")

    input_count = len(candidates)
    validation_errors: list[Mapping[str, Any]] = []
    warnings: list[Mapping[str, Any]] = []
    rejected: list[Mapping[str, Any]] = []
    if not candidates:
        validation_errors.append(
            _candidate_warning("EMPTY_CANDIDATE_LIST", "Candidate list is empty.", "input")
        )

    normalized_rows = [_normalized_input_row(row) for row in candidates]
    symbol_counts: dict[str, int] = {}
    for row in normalized_rows:
        if row["symbol"]:
            symbol_counts[row["symbol"]] = symbol_counts.get(row["symbol"], 0) + 1
    duplicate_symbols = {symbol for symbol, count in symbol_counts.items() if count > 1}
    eligible_rows: list[dict[str, Any]] = []
    invalid_input_count = 0
    duplicate_input_count = 0
    for row in normalized_rows:
        symbol = row["symbol"]
        reasons = []
        if not symbol:
            reasons.append("Symbol is missing or invalid.")
        if symbol in duplicate_symbols:
            reasons.append("Duplicate symbol was excluded deterministically.")
            duplicate_input_count += 1
        if row.get("eligible") is False:
            reasons.append("Candidate is explicitly ineligible.")
        for aliases, label in (
            (("ai_confidence", "AI Güven Endeksi"), "AI Confidence"),
            (("expected_return", "Beklenen Getiri %"), "expected return"),
            (("sell_risk", "risk_score", "Sat Riski %"), "risk score"),
        ):
            if _invalid_present_number(row, aliases):
                reasons.append(f"{label} contains a non-finite or non-numeric value.")
        if reasons:
            invalid_input_count += 1
            rejected.append(_candidate_rejection([symbol] if symbol else [], {}, "input_validation", reasons))
        else:
            eligible_rows.append(row)
    eligible_rows.sort(key=lambda row: row["symbol"])

    eligible_count = len(eligible_rows)
    effective_max = min(max_assets, eligible_count)
    sizes = list(range(min_assets, effective_max + 1)) if eligible_count >= min_assets else []
    theoretical_by_size = {size: math.comb(eligible_count, size) for size in sizes}
    theoretical_total = sum(theoretical_by_size.values())
    generated_by_size = {size: 0 for size in sizes}
    raw_generated = 0
    sector_rejected = 0
    pci_rejected = 0
    valid_candidates: list[Mapping[str, Any]] = []
    truncated = False

    supplied_metrics = stock_metrics_by_symbol or {}
    supplied_prices = price_data_by_symbol or {}
    pci_reference = list(reference_universe) if reference_universe is not None else normalized_rows
    sector_evidence = sector_metrics or {}

    for size in sizes:
        for combination in itertools.combinations(eligible_rows, size):
            if max_combinations is not None and raw_generated >= max_combinations:
                truncated = True
                break
            raw_generated += 1
            generated_by_size[size] += 1
            symbols = [row["symbol"] for row in combination]
            raw_weights, display_weights = equal_weight_scenario(symbols)
            candidate_id = build_candidate_id(symbols, raw_weights, horizon)
            sector_reasons = _sector_precheck(combination, raw_weights)
            if sector_reasons:
                sector_rejected += 1
                rejected.append(_candidate_rejection(symbols, display_weights, "sector_precheck", sector_reasons, candidate_id))
                continue
            sectors = [row["sector"] for row in combination]
            stock_metrics = {
                symbol: dict(supplied_metrics.get(symbol, row))
                for symbol, row in zip(symbols, combination)
            }
            prices = {}
            for symbol, row in zip(symbols, combination):
                if symbol in supplied_prices:
                    prices[symbol] = supplied_prices[symbol]
                else:
                    embedded_prices = row.get("price_series")
                    prices[symbol] = () if embedded_prices is None else embedded_prices
            pci = calculate_portfolio_confidence(
                {"stocks": symbols, "sectors": sectors, "weights": raw_weights},
                horizon,
                stock_metrics,
                sector_evidence,
                prices,
                pci_reference,
            )
            if pci.status == "rejected":
                pci_rejected += 1
                rejected.append(_candidate_rejection(symbols, display_weights, "pci", pci.rejection_reasons, candidate_id))
                continue
            pci_record = asdict(pci)
            candidate_warnings = [
                _candidate_warning(
                    str(item.get("warning_code", "PCI_WARNING")),
                    str(item.get("explanation", "PCI warning")),
                    "pci",
                    **dict(item),
                )
                for item in pci.warnings
            ]
            valid_candidates.append(
                {
                    "candidate_id": candidate_id,
                    "symbols": symbols,
                    "asset_count": size,
                    "weights": display_weights,
                    "weighting_method": "equal",
                    "sector_weights": dict(pci.sector_weights),
                    "pci": pci_record,
                    "warnings": candidate_warnings,
                    "facts": dict(pci.explanation_facts),
                }
            )
        if truncated:
            break

    if truncated:
        warnings.append(
            _candidate_warning(
                "COMBINATION_LIMIT_REACHED",
                "Canonical combination generation stopped at max_combinations.",
                "generation",
                max_combinations=max_combinations,
                theoretical_combinations=theoretical_total,
                generated_combinations=raw_generated,
            )
        )
    if eligible_count < min_assets and candidates:
        validation_errors.append(
            _candidate_warning(
                "INSUFFICIENT_ELIGIBLE_CANDIDATES",
                "Eligible candidate count is smaller than min_assets.",
                "generation",
                eligible_candidates=eligible_count,
                min_assets=min_assets,
            )
        )

    status = "invalid" if validation_errors else ("rejected" if not valid_candidates else "ok")
    return {
        "status": status,
        "candidates": valid_candidates,
        "rejected_candidates": rejected,
        "input_summary": {
            "input_candidate_count": input_count,
            "eligible_candidate_count": eligible_count,
            "duplicate_input_count": duplicate_input_count,
            "invalid_input_count": invalid_input_count,
        },
        "generation_summary": {
            "theoretical_combination_count": theoretical_total,
            "generated_combination_count": raw_generated,
            "sector_precheck_rejected_count": sector_rejected,
            "pci_rejected_count": pci_rejected,
            "valid_combination_count": len(valid_candidates),
            "combination_counts_by_asset_size": generated_by_size,
            "theoretical_counts_by_asset_size": theoretical_by_size,
            "weighting_method": "equal",
            "truncated": truncated,
        },
        "warnings": warnings,
        "validation_errors": validation_errors,
    }


OPTIMIZER_RANKING_POLICY = (
    "raw_pci_desc_then_cb_desc_rd_desc_sb_desc_aic_desc_"
    "maximum_pair_correlation_asc_candidate_id_asc"
)


def _optimizer_number(value: Any) -> float | None:
    try:
        return validate_finite_number(value)
    except ValueError:
        return None


def _first_optimizer_number(*values: Any, default: float) -> float:
    for value in values:
        numeric = _optimizer_number(value)
        if numeric is not None:
            return numeric
    return default


def _optimizer_filter_record(
    candidate_id: str | None, reasons: Sequence[Mapping[str, Any]]
) -> Mapping[str, Any]:
    return {"candidate_id": candidate_id, "reasons": list(reasons)}


def optimize_portfolio_candidates(
    generation_result: Mapping[str, Any],
    *,
    top_n: int = 20,
    min_pci: float | None = None,
    max_risk_score: float | None = None,
    min_expected_return: float | None = None,
) -> Mapping[str, Any]:
    """Filter and deterministically rank Part 4 candidates using docs/07."""

    if isinstance(top_n, bool) or not isinstance(top_n, int) or top_n < 1:
        raise ValueError("top_n must be a positive integer")
    if min_pci is not None:
        min_pci = validate_score(min_pci, field_name="min_pci")
    if max_risk_score is not None:
        max_risk_score = validate_score(max_risk_score, field_name="max_risk_score")
    if min_expected_return is not None:
        min_expected_return = validate_finite_number(
            min_expected_return, field_name="min_expected_return"
        )

    warnings: list[Mapping[str, Any]] = []
    validation_errors: list[Mapping[str, Any]] = []
    filtered: list[Mapping[str, Any]] = []
    raw_candidates = generation_result.get("candidates", ())
    if not isinstance(raw_candidates, Sequence) or isinstance(raw_candidates, (str, bytes)):
        validation_errors.append(
            _candidate_warning(
                "INVALID_CANDIDATE_COLLECTION",
                "Part 4 candidates must be a sequence.",
                "optimizer_input",
            )
        )
        raw_candidates = ()
    source_status = generation_result.get("status")
    if source_status not in (None, "ok"):
        warnings.append(
            _candidate_warning(
                "SOURCE_STATUS_NOT_OK",
                "Part 4 generation result status is not ok; only supplied valid candidates are considered.",
                "optimizer_input",
                source_status=source_status,
            )
        )

    ids = [candidate.get("candidate_id") for candidate in raw_candidates if isinstance(candidate, Mapping)]
    duplicate_ids = {candidate_id for candidate_id in ids if candidate_id and ids.count(candidate_id) > 1}
    accepted: list[tuple[Mapping[str, Any], Mapping[str, float], Mapping[str, Any]]] = []
    for candidate in raw_candidates:
        if not isinstance(candidate, Mapping):
            filtered.append(
                _optimizer_filter_record(
                    None,
                    [_candidate_warning("INVALID_CANDIDATE", "Candidate must be a mapping.", "candidate")],
                )
            )
            continue
        candidate_id = candidate.get("candidate_id")
        reasons: list[Mapping[str, Any]] = []
        if not isinstance(candidate_id, str) or not candidate_id:
            reasons.append(_candidate_warning("INVALID_CANDIDATE_ID", "candidate_id is missing or invalid.", "candidate"))
        elif candidate_id in duplicate_ids:
            reasons.append(_candidate_warning("DUPLICATE_CANDIDATE_ID", "All occurrences of a duplicate candidate_id were excluded deterministically.", "candidate", candidate_id=candidate_id))
        if candidate.get("status", "ok") != "ok":
            reasons.append(_candidate_warning("CANDIDATE_STATUS_NOT_OK", "Candidate status is not ok.", "candidate", status=candidate.get("status")))

        pci_record = candidate.get("pci")
        if not isinstance(pci_record, Mapping):
            pci_record = {}
            reasons.append(_candidate_warning("MISSING_PCI", "PCI record is missing.", "candidate"))
        pci = _optimizer_number(pci_record.get("portfolio_confidence_index"))
        if pci is None:
            reasons.append(_candidate_warning("INVALID_PCI", "PCI is missing, NaN, or infinite.", "candidate"))
        elif not 0.0 <= pci <= 100.0:
            reasons.append(_candidate_warning("INVALID_PCI_RANGE", "PCI is outside 0-100.", "candidate", pci=pci))

        facts = pci_record.get("explanation_facts", candidate.get("facts", {}))
        facts = facts if isinstance(facts, Mapping) else {}
        component_raw = facts.get("component_scores_raw", {})
        component_raw = component_raw if isinstance(component_raw, Mapping) else {}
        expected_summary = pci_record.get("expected_return_summary", {})
        expected_summary = expected_summary if isinstance(expected_summary, Mapping) else {}
        expected_return = _optimizer_number(expected_summary.get("weighted_mean"))
        risk_score = _optimizer_number(facts.get("weighted_risk_score"))

        if min_pci is not None and pci is not None and pci < min_pci:
            reasons.append(_candidate_warning("MIN_PCI_FILTER", "Candidate PCI is below min_pci.", "filter", actual=pci, threshold=min_pci))
        if max_risk_score is not None:
            if risk_score is None:
                reasons.append(_candidate_warning("MISSING_RISK_METRIC", "Weighted risk score is unavailable for max_risk_score filtering.", "filter"))
            elif risk_score > max_risk_score:
                reasons.append(_candidate_warning("MAX_RISK_FILTER", "Weighted risk score exceeds max_risk_score.", "filter", actual=risk_score, threshold=max_risk_score))
        if min_expected_return is not None:
            if expected_return is None:
                reasons.append(_candidate_warning("MISSING_EXPECTED_RETURN_METRIC", "Weighted expected return is unavailable for filtering.", "filter"))
            elif expected_return < min_expected_return:
                reasons.append(_candidate_warning("MIN_EXPECTED_RETURN_FILTER", "Weighted expected return is below the threshold.", "filter", actual=expected_return, threshold=min_expected_return))
        if reasons:
            filtered.append(_optimizer_filter_record(candidate_id if isinstance(candidate_id, str) else None, reasons))
            continue

        weights = candidate.get("weights", {})
        weights = weights if isinstance(weights, Mapping) else {}
        sector_weights = candidate.get("sector_weights", pci_record.get("sector_weights", {}))
        sector_weights = sector_weights if isinstance(sector_weights, Mapping) else {}
        contributions = facts.get("risk_contributions", {})
        contributions = contributions if isinstance(contributions, Mapping) else {}
        optimizer_metrics = {
            "portfolio_confidence_index": _round4(pci),
            "weighted_expected_return": _round4(expected_return),
            "weighted_risk_score": _round4(risk_score),
            "maximum_stock_weight": _round4(max((_optimizer_number(value) or 0.0 for value in weights.values()), default=0.0)),
            "maximum_sector_weight": _round4(_optimizer_number(pci_record.get("maximum_sector_weight"))),
            "average_correlation": _round4(_optimizer_number(pci_record.get("average_correlation"))),
            "maximum_pair_correlation": _round4(_optimizer_number(pci_record.get("maximum_pair_correlation"))),
            "risk_contribution_concentration": _round4(sum(float(value) ** 2 for value in contributions.values() if _optimizer_number(value) is not None)),
            "asset_count": int(candidate.get("asset_count", len(candidate.get("symbols", ())))),
        }
        ranking_values = {
            "raw_pci": _first_optimizer_number(facts.get("raw_portfolio_confidence_index"), pci, default=-1.0),
            "raw_cb": _first_optimizer_number(component_raw.get("correlation_balance"), pci_record.get("correlation_balance_score"), default=-1.0),
            "raw_rd": _first_optimizer_number(component_raw.get("risk_distribution"), pci_record.get("risk_distribution_score"), default=-1.0),
            "raw_sb": _first_optimizer_number(component_raw.get("sector_balance"), pci_record.get("sector_balance_score"), default=-1.0),
            "raw_aic": _first_optimizer_number(component_raw.get("average_ai_confidence"), pci_record.get("average_ai_confidence"), default=-1.0),
            "maximum_pair_correlation": optimizer_metrics["maximum_pair_correlation"] if optimizer_metrics["maximum_pair_correlation"] is not None else 1.0,
        }
        accepted.append((candidate, ranking_values, optimizer_metrics))

    accepted.sort(
        key=lambda item: (
            -item[1]["raw_pci"],
            -item[1]["raw_cb"],
            -item[1]["raw_rd"],
            -item[1]["raw_sb"],
            -item[1]["raw_aic"],
            item[1]["maximum_pair_correlation"],
            item[0]["candidate_id"],
        )
    )
    selected = accepted[:top_n]
    ranked = []
    for rank, (candidate, ranking_values, optimizer_metrics) in enumerate(selected, start=1):
        ranked.append(
            {
                "rank": rank,
                "candidate_id": candidate["candidate_id"],
                "symbols": list(candidate.get("symbols", ())),
                "weights": dict(candidate.get("weights", {})),
                "pci": dict(candidate.get("pci", {})),
                "optimizer_metrics": optimizer_metrics,
                "ranking_facts": {
                    "ranking_policy": OPTIMIZER_RANKING_POLICY,
                    "binding_source": "docs/07 ED-014",
                    "fallback_used": False,
                    **ranking_values,
                },
            }
        )

    status = "invalid" if validation_errors else ("empty" if not ranked else "ok")
    return {
        "status": status,
        "ranked_candidates": ranked,
        "filtered_candidates": filtered,
        "ranking_summary": {
            "input_candidate_count": len(raw_candidates),
            "eligible_candidate_count": len(accepted),
            "ranked_candidate_count": len(ranked),
            "filtered_candidate_count": len(filtered),
            "duplicate_candidate_id_count": len(duplicate_ids),
            "top_n": top_n,
            "ranking_policy": OPTIMIZER_RANKING_POLICY,
        },
        "warnings": warnings,
        "validation_errors": validation_errors,
    }


def build_ranked_portfolio_results(
    scanner_candidates: Sequence[Mapping[str, Any]],
    horizon: str,
    *,
    portfolio_size: int = MIN_PORTFOLIO_STOCKS,
    top_n: int = 20,
    min_pci: float | None = None,
    max_risk_score: float | None = None,
    min_expected_return: float | None = None,
    max_combinations: int | None = None,
    reference_universe: Sequence[Mapping[str, Any]] | None = None,
    sector_metrics: Mapping[str, SectorMetrics | Mapping[str, Any]] | None = None,
    stock_metrics_by_symbol: Mapping[str, Mapping[str, Any]] | None = None,
    price_data_by_symbol: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Run the Part 4 -> Part 5 chain without scanning, downloading, or mutation."""

    if not isinstance(scanner_candidates, Sequence) or isinstance(scanner_candidates, (str, bytes)):
        return {
            "status": "invalid", "ranked_candidates": [], "filtered_candidates": [],
            "rejected_candidates": [], "input_summary": {}, "generation_summary": {},
            "ranking_summary": {}, "warnings": [],
            "validation_errors": [_candidate_warning("INVALID_SCANNER_RESULTS", "Scanner results must be a sequence.", "service_input")],
            "rejection_summary": {"input_or_sector_rejections": 0, "optimizer_filtered_count": 0, "pci_rejected_count": 0},
            "service_facts": {"pipeline": "generate_portfolio_candidates -> optimize_portfolio_candidates", "market_rescan_performed": False, "price_download_performed": False, "top_n_cap": 20, "deterministic": True},
        }
    if isinstance(top_n, int) and not isinstance(top_n, bool) and top_n > 20:
        top_n = 20
    generation = generate_portfolio_candidates(
        scanner_candidates,
        horizon,
        min_assets=portfolio_size,
        max_assets=portfolio_size,
        max_combinations=max_combinations,
        reference_universe=reference_universe,
        sector_metrics=sector_metrics,
        stock_metrics_by_symbol=stock_metrics_by_symbol,
        price_data_by_symbol=price_data_by_symbol,
    )
    optimization = optimize_portfolio_candidates(
        generation,
        top_n=top_n,
        min_pci=min_pci,
        max_risk_score=max_risk_score,
        min_expected_return=min_expected_return,
    )
    generation_summary = dict(generation.get("generation_summary", {}))
    ranking_summary = dict(optimization.get("ranking_summary", {}))
    service_status = "invalid" if generation.get("validation_errors") else optimization["status"]
    return {
        "status": service_status,
        "ranked_candidates": list(optimization["ranked_candidates"]),
        "filtered_candidates": list(optimization["filtered_candidates"]),
        "rejected_candidates": list(generation.get("rejected_candidates", ())),
        "input_summary": dict(generation.get("input_summary", {})),
        "generation_summary": generation_summary,
        "ranking_summary": ranking_summary,
        "warnings": [
            *list(generation.get("warnings", ())),
            *list(optimization.get("warnings", ())),
        ],
        "validation_errors": [
            *list(generation.get("validation_errors", ())),
            *list(optimization.get("validation_errors", ())),
        ],
        "rejection_summary": {
            "input_or_sector_rejections": len(generation.get("rejected_candidates", ())),
            "optimizer_filtered_count": len(optimization.get("filtered_candidates", ())),
            "pci_rejected_count": generation_summary.get("pci_rejected_count", 0),
        },
        "service_facts": {
            "pipeline": "generate_portfolio_candidates -> optimize_portfolio_candidates",
            "market_rescan_performed": False,
            "price_download_performed": False,
            "top_n_cap": 20,
            "deterministic": True,
        },
    }


# Fail fast if the binding defaults are accidentally changed inconsistently.
validate_pci_weights()
validate_sector_score_weights()
