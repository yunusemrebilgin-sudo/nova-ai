from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import entry_timing


HORIZON_MULTIPLIERS = {
    "1-5 gün": 0.90,
    "5-10 gün": 1.15,
    "10-30 gün": 1.45,
    "1-2 ay": 1.80,
    "2-4 ay": 2.20,
}
HORIZON_ALIASES = {
    "Günlük işlem": "1-5 gün",
    "Kısa vade": "10-30 gün",
    "Orta vade": "1-2 ay",
    "Uzun vade": "2-4 ay",
    "1–5 gün": "1-5 gün",
    "5–10 gün": "5-10 gün",
    "10–30 gün": "10-30 gün",
    "1–2 ay": "1-2 ay",
    "2–4 ay": "2-4 ay",
}
DEFAULT_HORIZON = "10-30 gün"
DIRECTIONAL_QUALITY_MULTIPLIERS = (
    (80, 1.20),
    (65, 1.08),
    (50, 1.00),
    (35, 0.82),
    (0, 0.60),
)
EXPECTED_RETURN_MIN = -10.0
EXPECTED_RETURN_MAX = 35.0
MAX_LATE_ENTRY_PENALTY = 5.0
MAX_RISK_PENALTY = 4.0
MIN_RESISTANCE_ADJUSTMENT = -1.5
MAX_RESISTANCE_ADJUSTMENT = 1.5
MIN_UNCERTAINTY = 1.0
MAX_UNCERTAINTY = 6.0


def _finite_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _first_float(row: Mapping[str, object], *keys: str) -> float | None:
    for key in keys:
        value = _finite_float(row.get(key))
        if value is not None:
            return value
    return None


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(upper, max(lower, value))


def _contribution(label: str, points: float, unit: str, category: str) -> dict[str, Any]:
    return {"label": label, "points": points, "unit": unit, "category": category}


def resolve_expected_return_horizon(selected_horizon: object) -> dict[str, Any]:
    requested = str(selected_horizon or "").strip()
    canonical = HORIZON_ALIASES.get(requested, requested)
    fallback_used = canonical not in HORIZON_MULTIPLIERS
    if fallback_used:
        canonical = DEFAULT_HORIZON
    return {
        "requested": requested or None,
        "canonical": canonical,
        "multiplier": HORIZON_MULTIPLIERS[canonical],
        "fallback_used": fallback_used,
        "fallback_message": (
            f"Tanımsız vade '{requested or 'boş'}' için {DEFAULT_HORIZON} eşlemesi kullanıldı."
            if fallback_used
            else None
        ),
    }


def build_expected_return_v2_features(
    row: Mapping[str, object],
    selected_horizon: object,
    entry_timing_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    timing = dict(entry_timing_result) if entry_timing_result is not None else entry_timing.evaluate_entry_timing(row)
    timing_features = dict(timing.get("features") or {})
    horizon = resolve_expected_return_horizon(selected_horizon)

    raw_prices = row.get("_portfolio_price_series", [])
    if isinstance(raw_prices, Sequence) and not isinstance(raw_prices, (str, bytes)):
        price_count = sum(_finite_float(value) is not None for value in raw_prices)
    else:
        price_count = 0

    histogram = _finite_float(timing_features.get("macd_histogram"))
    previous_histogram = _finite_float(timing_features.get("previous_macd_histogram"))
    histogram_direction = (
        None if histogram is None or previous_histogram is None else histogram - previous_histogram
    )

    features = {
        **timing_features,
        "macd_histogram_direction": histogram_direction,
        "entry_timing_score": _finite_float(timing.get("score")),
        "entry_timing_classification": timing.get("classification"),
        "selected_horizon": selected_horizon,
        "horizon_mapping": horizon,
        "price_series_length": price_count,
        "current_expected_return": _first_float(row, "Beklenen Getiri %"),
        "market_data_time": row.get("_market_data_time"),
    }

    required = {
        "Son kapanış": "close",
        "ATR%": "atr_pct",
        "Volatility20": "volatility20",
        "EMA20": "ema20",
        "EMA50": "ema50",
        "ADX": "adx14",
        "RSI": "rsi14",
        "RSI yönü": "rsi_direction",
        "MACD": "macd",
        "MACD Signal": "macd_signal",
        "MACD Histogram": "macd_histogram",
        "MACD Histogram yönü": "macd_histogram_direction",
        "Momentum10": "momentum10",
        "Momentum değişimi": "momentum_change",
        "1 günlük getiri": "return_1d_pct",
        "3 günlük getiri": "return_3d_pct",
        "5 günlük getiri": "return_5d_pct",
        "Volume Ratio": "volume_ratio",
        "Destek": "support",
        "Ana direnç": "resistance",
        "Önceki 20 Kapanış Direnci": "previous_20_close_resistance",
        "Nova Score": "nova_score",
        "Güven Endeksi": "confidence",
        "Entry Timing Score": "entry_timing_score",
    }
    missing_data = [label for label, key in required.items() if features.get(key) is None]
    if price_count < 30:
        missing_data.append("En az 30 kapanışlık fiyat geçmişi")

    critical_labels = {
        "ATR%",
        "Volatility20",
        "RSI yönü",
        "MACD Histogram yönü",
        "Momentum değişimi",
        "Ana direnç",
        "Volume Ratio",
        "Güven Endeksi",
        "Entry Timing Score",
        "En az 30 kapanışlık fiyat geçmişi",
    }
    features["missing_data"] = missing_data
    features["critical_missing_data"] = [label for label in missing_data if label in critical_labels]
    return features


def calculate_movement_capacity(features: Mapping[str, Any]) -> dict[str, Any]:
    atr_pct = _finite_float(features.get("atr_pct"))
    mapping = features.get("horizon_mapping") or resolve_expected_return_horizon(features.get("selected_horizon"))
    multiplier = _finite_float(mapping.get("multiplier")) or HORIZON_MULTIPLIERS[DEFAULT_HORIZON]
    capacity = None if atr_pct is None else atr_pct * multiplier
    return {"atr_pct": atr_pct, "horizon_multiplier": multiplier, "movement_capacity": capacity}


def calculate_directional_quality(features: Mapping[str, Any]) -> dict[str, Any]:
    score = 50.0
    positive: list[dict[str, Any]] = []
    negative: list[dict[str, Any]] = []

    def add(label: str, points: float) -> None:
        nonlocal score
        score += points
        item = _contribution(label, points, "kalite puanı", "directional_quality")
        (positive if points > 0 else negative).append(item)

    close = _finite_float(features.get("close"))
    ema20 = _finite_float(features.get("ema20"))
    ema50 = _finite_float(features.get("ema50"))
    if ema20 is not None and ema50 is not None:
        add("Güçlü EMA yapısı (EMA20 > EMA50)", 10 if ema20 > ema50 else -8)
    if close is not None and ema20 is not None:
        if close > ema20:
            add("Kapanış EMA20 üzerinde", 7)
        elif close < ema20:
            add("Kapanış EMA20 altında", -7)

    adx = _finite_float(features.get("adx14"))
    if adx is not None and adx >= 25:
        add("ADX trend teyidi", 7)

    momentum = _finite_float(features.get("momentum10"))
    momentum_change = _finite_float(features.get("momentum_change"))
    if momentum is not None:
        if momentum > 0:
            add("Momentum10 pozitif", 6)
        elif momentum < 0:
            add("Momentum10 negatif", -7)
    if momentum_change is not None:
        if momentum_change > 0:
            add("Momentum güçleniyor", 5)
        elif momentum_change < 0:
            add("Momentum zayıflıyor", -5)

    macd = _finite_float(features.get("macd"))
    signal = _finite_float(features.get("macd_signal"))
    if macd is not None and signal is not None:
        if macd > signal:
            add("MACD teyidi", 6)
        elif macd < signal:
            add("MACD Signal altında", -6)

    histogram = _finite_float(features.get("macd_histogram"))
    histogram_direction = _finite_float(features.get("macd_histogram_direction"))
    if histogram is not None:
        if histogram > 0:
            add("MACD Histogram pozitif", 4)
        elif histogram < 0:
            add("MACD Histogram negatif", -4)
    if histogram_direction is not None and histogram_direction > 0:
        add("MACD Histogram güçleniyor", 4)

    rsi = _finite_float(features.get("rsi14"))
    if rsi is not None:
        if 45 <= rsi <= 65:
            add("RSI 45-65 dengeli bölge", 5)
        if rsi >= 70:
            add("RSI 70 ve üzerinde", -6)
        if rsi >= 75:
            add("RSI 75 ve üzerinde ilave ceza", -5)
        if rsi <= 30:
            add("RSI 30 ve altında", -5)

    volume_ratio = _finite_float(features.get("volume_ratio"))
    if volume_ratio is not None:
        if 1.10 <= volume_ratio <= 1.80:
            add("Hacim teyidi", 5)
        elif volume_ratio < 0.80:
            add("Hacim oranı 0.80 altında", -4)

    nova_score = _finite_float(features.get("nova_score"))
    if nova_score is not None and nova_score >= 70:
        add("Nova Score 70 ve üzerinde", 4)
    confidence = _finite_float(features.get("confidence"))
    if confidence is not None and confidence >= 70:
        add("Güven Endeksi 70 ve üzerinde", 4)

    volatility = _finite_float(features.get("volatility20"))
    if volatility is not None and volatility > 4:
        add("Volatility20 4 üzerinde", -4)
    if volatility is not None and volatility > 6:
        add("Volatility20 6 üzerinde ilave ceza", -4)

    clamped_score = _clamp(score, 0.0, 100.0)
    return {
        "raw_score": score,
        "score": clamped_score,
        "positive_contributions": positive,
        "negative_contributions": negative,
    }


def _directional_quality_multiplier(score: float) -> float:
    for minimum_score, multiplier in DIRECTIONAL_QUALITY_MULTIPLIERS:
        if score >= minimum_score:
            return multiplier
    return DIRECTIONAL_QUALITY_MULTIPLIERS[-1][1]


def calculate_entry_timing_adjustment(features: Mapping[str, Any]) -> dict[str, Any]:
    score = _finite_float(features.get("entry_timing_score"))
    if score is None:
        base_adjustment = 0.0
    elif score >= 80:
        base_adjustment = 1.5
    elif score >= 65:
        base_adjustment = 0.5
    elif score >= 50:
        base_adjustment = 0.0
    elif score >= 35:
        base_adjustment = -1.5
    else:
        base_adjustment = -3.0

    positive: list[dict[str, Any]] = []
    negative: list[dict[str, Any]] = []
    if base_adjustment:
        item = _contribution(
            "Uygun giriş zamanlaması" if base_adjustment > 0 else "Zayıf giriş zamanlaması",
            base_adjustment,
            "getiri puanı",
            "entry_timing",
        )
        (positive if base_adjustment > 0 else negative).append(item)

    late_penalties: list[dict[str, Any]] = []

    def late(label: str, points: float) -> None:
        item = _contribution(label, points, "getiri puanı", "late_entry")
        late_penalties.append(item)
        negative.append(item)

    return_1d = _finite_float(features.get("return_1d_pct"))
    return_3d = _finite_float(features.get("return_3d_pct"))
    return_5d = _finite_float(features.get("return_5d_pct"))
    ema20_distance = _finite_float(features.get("ema20_distance_pct"))
    if return_1d is not None and return_1d >= 6:
        late("Son 1 günde aşırı yükseliş", -1.0)
    if return_3d is not None and return_3d >= 8:
        late("Son 3 günde aşırı yükseliş", -2.0)
    if return_5d is not None and return_5d >= 12:
        late("Son 5 günde aşırı yükseliş", -2.5)
    if ema20_distance is not None and ema20_distance > 5:
        late("EMA20'den %5'in üzerinde uzaklaşma", -1.5)
    if ema20_distance is not None and ema20_distance > 8:
        late("EMA20'den %8'in üzerinde ilave uzaklaşma", -1.5)

    raw_late_penalty = sum(item["points"] for item in late_penalties)
    late_entry_penalty = max(-MAX_LATE_ENTRY_PENALTY, raw_late_penalty)
    limiting_factors = []
    if raw_late_penalty < late_entry_penalty:
        limiting_factors.append("Geç giriş cezası -5.0 getiri puanıyla sınırlandı")
    return {
        "entry_timing_score": score,
        "base_adjustment": base_adjustment,
        "raw_late_entry_penalty": raw_late_penalty,
        "late_entry_penalty": late_entry_penalty,
        "total_adjustment": base_adjustment + late_entry_penalty,
        "positive_contributions": positive,
        "negative_contributions": negative,
        "limiting_factors": limiting_factors,
    }


def calculate_resistance_adjustment(features: Mapping[str, Any]) -> dict[str, Any]:
    resistance = _finite_float(features.get("resistance"))
    distance = _finite_float(features.get("resistance_distance_pct"))
    breakout = bool(features.get("breakout_confirmed", False))
    raw_adjustment = 0.0
    positive: list[dict[str, Any]] = []
    negative: list[dict[str, Any]] = []
    limiting_factors: list[str] = []

    if breakout:
        raw_adjustment += 1.5
        positive.append(_contribution("Önceki 20 Kapanış Direnci hacimle kırıldı", 1.5, "getiri puanı", "resistance"))
    elif resistance is not None and distance is not None:
        if 0 <= distance < 1.5:
            raw_adjustment -= 1.0
            negative.append(_contribution("Direnç alanı potansiyeli sınırlıyor", -1.0, "getiri puanı", "resistance"))
            limiting_factors.append("Ana dirence %1.5'ten az mesafe var ve breakout teyidi yok")
        elif 1.5 <= distance <= 4:
            limiting_factors.append("Ana dirence %1.5-%4 mesafe doğrudan getiri katkısı olarak kullanılmadı")
        elif distance > 4:
            raw_adjustment += 1.0
            positive.append(_contribution("Ana dirence kadar hareket alanı", 1.0, "getiri puanı", "resistance"))
        else:
            limiting_factors.append("Ana direnç fiyatın altında; hacimli kapanış kırılımı teyit edilmedi")
    elif resistance is None:
        limiting_factors.append("Ana direnç verisi eksik")

    adjustment = _clamp(raw_adjustment, MIN_RESISTANCE_ADJUSTMENT, MAX_RESISTANCE_ADJUSTMENT)
    return {
        "raw_adjustment": raw_adjustment,
        "adjustment": adjustment,
        "positive_contributions": positive,
        "negative_contributions": negative,
        "limiting_factors": limiting_factors,
    }


def calculate_risk_penalty(features: Mapping[str, Any]) -> dict[str, Any]:
    raw_penalty = 0.0
    negative: list[dict[str, Any]] = []

    def add(label: str, penalty: float) -> None:
        nonlocal raw_penalty
        raw_penalty += penalty
        negative.append(_contribution(label, -penalty, "risk cezası", "risk"))

    volatility = _finite_float(features.get("volatility20"))
    if volatility is not None:
        if volatility > 6:
            add("Volatility20 6 üzerinde", 2.0)
        elif volatility > 4:
            add("Volatility20 4-6 aralığında", 1.0)
        elif volatility >= 3:
            add("Volatility20 3-4 aralığında", 0.5)
    rsi = _finite_float(features.get("rsi14"))
    if rsi is not None and rsi >= 75:
        add("RSI 75 ve üzerinde", 1.0)
    volume = _finite_float(features.get("volume_ratio"))
    if volume is not None and volume < 0.70:
        add("Volume Ratio 0.70 altında", 0.75)
    adx = _finite_float(features.get("adx14"))
    if adx is not None and adx < 15:
        add("ADX 15 altında", 0.75)
    confidence = _finite_float(features.get("confidence"))
    if confidence is not None and confidence < 50:
        add("Güven Endeksi 50 altında", 1.0)

    return {
        "raw_penalty": raw_penalty,
        "penalty": min(MAX_RISK_PENALTY, raw_penalty),
        "negative_contributions": negative,
    }


def calculate_return_adjustments(features: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "entry_timing": calculate_entry_timing_adjustment(features),
        "resistance": calculate_resistance_adjustment(features),
        "risk": calculate_risk_penalty(features),
    }


def calculate_uncertainty(features: Mapping[str, Any]) -> dict[str, Any]:
    volatility = _finite_float(features.get("volatility20"))
    confidence = _finite_float(features.get("confidence"))
    missing_count = len(features.get("critical_missing_data") or [])
    volatility_component = max(0.0, volatility - 2.5) * 0.45 if volatility is not None else 0.0
    confidence_component = (100.0 - confidence) * 0.025 if confidence is not None else 2.5
    missing_component = missing_count * 0.40
    raw_uncertainty = 1.0 + volatility_component + confidence_component + missing_component
    return {
        "raw_uncertainty": raw_uncertainty,
        "uncertainty": _clamp(raw_uncertainty, MIN_UNCERTAINTY, MAX_UNCERTAINTY),
        "volatility_component": volatility_component,
        "confidence_component": confidence_component,
        "missing_data_component": missing_component,
        "critical_missing_data_count": missing_count,
    }


def calculate_model_confidence(features: Mapping[str, Any]) -> dict[str, Any]:
    base_confidence = _finite_float(features.get("confidence"))
    raw_confidence = base_confidence if base_confidence is not None else 0.0
    penalties: list[dict[str, Any]] = []

    def penalize(condition: bool, label: str, points: float) -> None:
        nonlocal raw_confidence
        if condition:
            raw_confidence -= points
            penalties.append(_contribution(label, -points, "model güven puanı", "model_confidence"))

    penalize(features.get("atr_pct") is None, "ATR% eksik", 25)
    penalize(int(features.get("price_series_length") or 0) < 30, "Fiyat serisi 30 kapanıştan kısa", 15)
    penalize(features.get("rsi_direction") is None, "RSI yönü eksik", 5)
    penalize(features.get("momentum_change") is None, "Momentum değişimi eksik", 5)
    penalize(features.get("macd_histogram_direction") is None, "MACD Histogram yönü eksik", 5)
    penalize(features.get("resistance") is None, "Ana direnç eksik", 5)
    penalize(features.get("volume_ratio") is None, "Volume Ratio eksik", 5)
    penalize(features.get("volatility20") is None, "Volatility20 eksik", 5)
    penalize(features.get("entry_timing_score") is None, "Entry Timing sonucu eksik", 10)

    confidence = _clamp(raw_confidence, 0.0, 100.0)
    return {
        "base_confidence": base_confidence,
        "raw_confidence": raw_confidence,
        "confidence": confidence,
        "classification": classify_expected_return_confidence(confidence),
        "penalties": penalties,
    }


def classify_expected_return_confidence(confidence: float) -> str:
    if confidence >= 80:
        return "Yüksek Model Güveni"
    if confidence >= 65:
        return "İyi Model Güveni"
    if confidence >= 50:
        return "Orta Model Güveni"
    if confidence >= 35:
        return "Düşük Model Güveni"
    return "Yetersiz Model Güveni"


def calculate_expected_return_v2(features: Mapping[str, Any]) -> dict[str, Any]:
    movement = calculate_movement_capacity(features)
    quality = calculate_directional_quality(features)
    adjustments = calculate_return_adjustments(features)
    uncertainty = calculate_uncertainty(features)
    model_confidence = calculate_model_confidence(features)

    quality_multiplier = _directional_quality_multiplier(quality["score"])
    capacity = movement["movement_capacity"]
    adjusted_capacity = None if capacity is None else capacity * quality_multiplier
    entry_adjustment = adjustments["entry_timing"]["total_adjustment"]
    resistance_adjustment = adjustments["resistance"]["adjustment"]
    risk_penalty = adjustments["risk"]["penalty"]

    warnings: list[str] = []
    if capacity is None:
        raw_main = main = conservative = optimistic = None
        raw_conservative = raw_optimistic = None
        warnings.append("ATR% eksik olduğu için sayısal beklenen getiri üretilemedi")
    else:
        raw_main = adjusted_capacity + entry_adjustment + resistance_adjustment - risk_penalty
        main = _clamp(raw_main, EXPECTED_RETURN_MIN, EXPECTED_RETURN_MAX)
        raw_conservative = main - uncertainty["uncertainty"]
        raw_optimistic = main + uncertainty["uncertainty"]
        conservative = _clamp(raw_conservative, EXPECTED_RETURN_MIN, EXPECTED_RETURN_MAX)
        optimistic = _clamp(raw_optimistic, EXPECTED_RETURN_MIN, EXPECTED_RETURN_MAX)

    horizon_mapping = features.get("horizon_mapping") or {}
    if horizon_mapping.get("fallback_message"):
        warnings.append(str(horizon_mapping["fallback_message"]))

    positive = [
        *quality["positive_contributions"],
        *adjustments["entry_timing"]["positive_contributions"],
        *adjustments["resistance"]["positive_contributions"],
    ]
    negative = [
        *quality["negative_contributions"],
        *adjustments["entry_timing"]["negative_contributions"],
        *adjustments["resistance"]["negative_contributions"],
        *adjustments["risk"]["negative_contributions"],
    ]
    limiting_factors = [
        *adjustments["entry_timing"]["limiting_factors"],
        *adjustments["resistance"]["limiting_factors"],
    ]

    return {
        "conservative_expected_return": conservative,
        "main_expected_return": main,
        "optimistic_expected_return": optimistic,
        "expected_return_range": None if main is None else [conservative, optimistic],
        "model_confidence": model_confidence["confidence"],
        "model_confidence_classification": model_confidence["classification"],
        "movement_capacity": capacity,
        "directional_quality_score": quality["score"],
        "directional_quality_multiplier": quality_multiplier,
        "adjusted_capacity": adjusted_capacity,
        "entry_timing_adjustment": entry_adjustment,
        "resistance_adjustment": resistance_adjustment,
        "risk_penalty": risk_penalty,
        "uncertainty": uncertainty["uncertainty"],
        "positive_contributions": positive,
        "negative_contributions": negative,
        "limiting_factors": limiting_factors,
        "missing_data": list(features.get("missing_data") or []),
        "warnings": warnings,
        "debug": {
            "horizon_mapping": horizon_mapping,
            "movement_capacity": movement,
            "directional_quality": quality,
            "entry_timing": adjustments["entry_timing"],
            "resistance": adjustments["resistance"],
            "risk": adjustments["risk"],
            "uncertainty": uncertainty,
            "model_confidence": model_confidence,
            "clamps": {
                "directional_quality": {"raw": quality["raw_score"], "clamped": quality["score"]},
                "late_entry_penalty": {
                    "raw": adjustments["entry_timing"]["raw_late_entry_penalty"],
                    "clamped": adjustments["entry_timing"]["late_entry_penalty"],
                },
                "resistance_adjustment": {
                    "raw": adjustments["resistance"]["raw_adjustment"],
                    "clamped": resistance_adjustment,
                },
                "risk_penalty": {"raw": adjustments["risk"]["raw_penalty"], "clamped": risk_penalty},
                "uncertainty": {"raw": uncertainty["raw_uncertainty"], "clamped": uncertainty["uncertainty"]},
                "main_expected_return": {"raw": raw_main, "clamped": main},
                "conservative_expected_return": {"raw": raw_conservative, "clamped": conservative},
                "optimistic_expected_return": {"raw": raw_optimistic, "clamped": optimistic},
            },
            "formula_components": {
                "adjusted_capacity": adjusted_capacity,
                "entry_timing_adjustment": entry_adjustment,
                "resistance_adjustment": resistance_adjustment,
                "risk_penalty_subtracted": risk_penalty,
                "formula": "Adjusted Capacity + Entry Timing Adjustment + Resistance Adjustment - Risk Penalty",
            },
            "missing_data": list(features.get("missing_data") or []),
        },
    }


def evaluate_expected_return_v2(
    row: Mapping[str, object],
    selected_horizon: object,
    entry_timing_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    features = build_expected_return_v2_features(row, selected_horizon, entry_timing_result)
    result = calculate_expected_return_v2(features)
    return {**result, "features": features}
