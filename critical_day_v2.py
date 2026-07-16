from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import entry_timing
import expected_return_v2


HORIZON_TRADING_DAY_BOUNDS = {
    "1-5 gün": (1, 5),
    "5-10 gün": (5, 10),
    "10-30 gün": (10, 30),
    "1-2 ay": (20, 40),
    "2-4 ay": (40, 80),
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
BASE_DAILY_CAPACITY_FACTOR = 0.55
QUALITY_MULTIPLIERS = ((80, 1.15), (65, 1.05), (50, 0.95), (35, 0.80), (0, 0.65))
ENTRY_TIMING_MULTIPLIERS = ((80, 1.05), (65, 1.00), (50, 0.90), (35, 0.75), (0, 0.60))
MIN_DAILY_DIRECTIONAL_CAPACITY = 0.10
MAX_DAILY_DIRECTIONAL_CAPACITY = 8.0
MAX_ACCELERATION_DAYS = 3
MAX_DELAY_DAYS = 6
MIN_WINDOW_HALF_WIDTH = 1
MAX_WINDOW_HALF_WIDTH = 8


def _finite_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(upper, max(lower, value))


def _threshold_multiplier(value: float | None, table: tuple[tuple[int, float], ...], fallback: float) -> float:
    if value is None:
        return fallback
    for minimum, multiplier in table:
        if value >= minimum:
            return multiplier
    return table[-1][1]


def _day_adjustment(label: str, days: int, category: str) -> dict[str, Any]:
    return {"label": label, "days": days, "category": category}


def normalize_critical_day_horizon(selected_horizon: object) -> dict[str, Any]:
    requested = str(selected_horizon or "").strip()
    canonical = HORIZON_ALIASES.get(requested, requested)
    fallback_used = canonical not in HORIZON_TRADING_DAY_BOUNDS
    if fallback_used:
        canonical = DEFAULT_HORIZON
    minimum_day, maximum_day = HORIZON_TRADING_DAY_BOUNDS[canonical]
    return {
        "requested": requested or None,
        "canonical": canonical,
        "minimum_trading_day": minimum_day,
        "maximum_trading_day": maximum_day,
        "fallback_used": fallback_used,
        "fallback_message": (
            f"Tanımsız vade '{requested or 'boş'}' için {DEFAULT_HORIZON} işlem günü sınırları kullanıldı."
            if fallback_used
            else None
        ),
    }


def build_critical_day_v2_features(
    row: Mapping[str, object],
    selected_horizon: object,
    entry_timing_result: Mapping[str, Any] | None = None,
    expected_return_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    timing = dict(entry_timing_result) if entry_timing_result is not None else entry_timing.evaluate_entry_timing(row)
    expected = (
        dict(expected_return_result)
        if expected_return_result is not None
        else expected_return_v2.evaluate_expected_return_v2(row, selected_horizon, timing)
    )
    expected_features = dict(expected.get("features") or timing.get("features") or {})
    horizon = normalize_critical_day_horizon(selected_horizon)

    features = {
        **expected_features,
        "selected_horizon": selected_horizon,
        "critical_day_horizon": horizon,
        "entry_timing_score": _finite_float(timing.get("score")),
        "entry_timing_classification": timing.get("classification"),
        "conservative_expected_return": _finite_float(expected.get("conservative_expected_return")),
        "main_expected_return": _finite_float(expected.get("main_expected_return")),
        "optimistic_expected_return": _finite_float(expected.get("optimistic_expected_return")),
        "expected_return_model_confidence": _finite_float(expected.get("model_confidence")),
        "directional_quality_score": _finite_float(expected.get("directional_quality_score")),
        "movement_capacity": _finite_float(expected.get("movement_capacity")),
        "risk_penalty": _finite_float(expected.get("risk_penalty")),
        "uncertainty": _finite_float(expected.get("uncertainty")),
        "current_critical_window": row.get("Beklenen Taşıma Süresi"),
        "market_data_time": row.get("_market_data_time"),
    }

    required = {
        "ATR%": "atr_pct",
        "Volatility20": "volatility20",
        "ADX": "adx14",
        "EMA20": "ema20",
        "EMA50": "ema50",
        "Momentum10": "momentum10",
        "Momentum değişimi": "momentum_change",
        "RSI": "rsi14",
        "RSI yönü": "rsi_direction",
        "MACD Histogram": "macd_histogram",
        "MACD Histogram yönü": "macd_histogram_direction",
        "1 günlük getiri": "return_1d_pct",
        "3 günlük getiri": "return_3d_pct",
        "5 günlük getiri": "return_5d_pct",
        "Trend": "trend",
        "Entry Timing Score": "entry_timing_score",
        "Expected Return V2 muhafazakâr beklenti": "conservative_expected_return",
        "Expected Return V2 ana beklenti": "main_expected_return",
        "Expected Return V2 iyimser beklenti": "optimistic_expected_return",
        "Expected Return V2 Model Güveni": "expected_return_model_confidence",
        "Directional Quality Score": "directional_quality_score",
        "Hareket kapasitesi": "movement_capacity",
        "Expected Return V2 risk cezası": "risk_penalty",
        "Expected Return V2 belirsizlik payı": "uncertainty",
        "Güven Endeksi": "confidence",
        "Ana direnç": "resistance",
        "Ana dirence yüzde mesafe": "resistance_distance_pct",
    }
    missing_data = [label for label, key in required.items() if features.get(key) is None]
    if int(features.get("price_series_length") or 0) < 30:
        missing_data.append("En az 30 kapanışlık fiyat geçmişi")
    features["missing_data"] = missing_data
    return features


def estimate_daily_move_capacity(features: Mapping[str, Any]) -> dict[str, Any]:
    atr_pct = _finite_float(features.get("atr_pct"))
    quality_score = _finite_float(features.get("directional_quality_score"))
    entry_score = _finite_float(features.get("entry_timing_score"))
    volatility = _finite_float(features.get("volatility20"))

    quality_multiplier = _threshold_multiplier(quality_score, QUALITY_MULTIPLIERS, 0.95)
    entry_multiplier = _threshold_multiplier(entry_score, ENTRY_TIMING_MULTIPLIERS, 1.00)
    if volatility is None or volatility <= 3:
        volatility_multiplier = 1.00
    elif volatility <= 4:
        volatility_multiplier = 0.95
    elif volatility <= 6:
        volatility_multiplier = 0.85
    else:
        volatility_multiplier = 0.70

    if atr_pct is None:
        base_capacity = raw_capacity = capacity = None
        lower_clamp_hit = upper_clamp_hit = False
    else:
        base_capacity = atr_pct * BASE_DAILY_CAPACITY_FACTOR
        raw_capacity = base_capacity * quality_multiplier * entry_multiplier * volatility_multiplier
        capacity = _clamp(raw_capacity, MIN_DAILY_DIRECTIONAL_CAPACITY, MAX_DAILY_DIRECTIONAL_CAPACITY)
        lower_clamp_hit = raw_capacity <= MIN_DAILY_DIRECTIONAL_CAPACITY
        upper_clamp_hit = raw_capacity >= MAX_DAILY_DIRECTIONAL_CAPACITY

    return {
        "atr_pct": atr_pct,
        "base_daily_capacity": base_capacity,
        "quality_multiplier": quality_multiplier,
        "entry_timing_multiplier": entry_multiplier,
        "volatility_multiplier": volatility_multiplier,
        "raw_daily_directional_capacity": raw_capacity,
        "daily_directional_capacity": capacity,
        "lower_clamp_hit": lower_clamp_hit,
        "upper_clamp_hit": upper_clamp_hit,
    }


def calculate_target_reach_days(features: Mapping[str, Any], daily_capacity: float | None) -> dict[str, Any]:
    main_expected_return = _finite_float(features.get("main_expected_return"))
    if main_expected_return is None and daily_capacity is None:
        reason = "ATR% ve Expected Return V2 ana beklenti eksik olduğu için sayısal kritik gün üretilemedi"
    elif main_expected_return is None:
        reason = "Expected Return V2 ana beklenti eksik olduğu için sayısal kritik gün üretilemedi"
    elif daily_capacity is None:
        reason = "ATR% eksik olduğu için sayısal kritik gün üretilemedi"
    else:
        reason = None
    if reason is not None:
        return {"raw_reach_days": None, "base_reach_day": None, "reason": reason}
    if main_expected_return <= 0:
        return {
            "raw_reach_days": None,
            "base_reach_day": None,
            "reason": "Pozitif hedef için uygun teknik beklenti yok",
        }
    raw_reach_days = main_expected_return / daily_capacity
    return {
        "raw_reach_days": raw_reach_days,
        "base_reach_day": math.ceil(raw_reach_days),
        "reason": None,
    }


def calculate_window_adjustments(features: Mapping[str, Any]) -> dict[str, Any]:
    accelerators: list[dict[str, Any]] = []
    delays: list[dict[str, Any]] = []

    def accelerate(label: str) -> None:
        accelerators.append(_day_adjustment(label, -1, "acceleration"))

    def delay(label: str, days: int) -> None:
        delays.append(_day_adjustment(label, days, "delay"))

    adx = _finite_float(features.get("adx14"))
    ema20 = _finite_float(features.get("ema20"))
    ema50 = _finite_float(features.get("ema50"))
    if adx is not None and ema20 is not None and ema50 is not None and adx >= 25 and ema20 > ema50:
        accelerate("Güçlü trend ve ADX")
    momentum_change = _finite_float(features.get("momentum_change"))
    if momentum_change is not None and momentum_change > 0:
        accelerate("Momentum güçleniyor")
    histogram = _finite_float(features.get("macd_histogram"))
    histogram_direction = _finite_float(features.get("macd_histogram_direction"))
    if histogram is not None and histogram_direction is not None and histogram > 0 and histogram_direction > 0:
        accelerate("MACD Histogram pozitif ve güçleniyor")
    breakout = bool(features.get("breakout_confirmed", False))
    if breakout:
        accelerate("Kapanış kırılım teyidi")
    volume_ratio = _finite_float(features.get("volume_ratio"))
    if volume_ratio is not None and 1.20 <= volume_ratio <= 1.80:
        accelerate("Hacim teyidi")

    entry_score = _finite_float(features.get("entry_timing_score"))
    if entry_score is not None:
        if 50 <= entry_score < 65:
            delay("Entry Timing Score 50-64", 1)
        elif 35 <= entry_score < 50:
            delay("Entry Timing Score 35-49", 2)
        elif entry_score < 35:
            delay("Entry Timing Score 0-34", 3)
    if momentum_change is not None and momentum_change < 0:
        delay("Momentum zayıflıyor", 1)
    rsi = _finite_float(features.get("rsi14"))
    if rsi is not None and rsi >= 70:
        delay("RSI 70 ve üzerinde", 1)
    volatility = _finite_float(features.get("volatility20"))
    if volatility is not None:
        if volatility > 6:
            delay("Volatility20 6 üzerinde", 2)
        elif volatility >= 4:
            delay("Volatility20 4-6 aralığında", 1)
    resistance_distance = _finite_float(features.get("resistance_distance_pct"))
    if resistance_distance is not None and 0 <= resistance_distance <= 1.5 and not breakout:
        delay("Ana direnç altında ve breakout teyidi yok", 2)
    risk_penalty = _finite_float(features.get("risk_penalty"))
    if risk_penalty is not None and risk_penalty >= 2:
        delay("Expected Return V2 risk cezası 2 ve üzerinde", 1)
    if risk_penalty is not None and risk_penalty >= 3.5:
        delay("Expected Return V2 risk cezası 3.5 ve üzerinde ilave gecikme", 1)

    raw_acceleration = sum(item["days"] for item in accelerators)
    raw_delay = sum(item["days"] for item in delays)
    return {
        "accelerators": accelerators,
        "delays": delays,
        "raw_acceleration_days": raw_acceleration,
        "acceleration_days": max(-MAX_ACCELERATION_DAYS, raw_acceleration),
        "raw_delay_days": raw_delay,
        "delay_days": min(MAX_DELAY_DAYS, raw_delay),
    }


def _risk_extension_days(risk_penalty: float | None) -> int:
    if risk_penalty is None or risk_penalty < 1.5:
        return 0
    if risk_penalty < 2.5:
        return 1
    if risk_penalty < 3.5:
        return 2
    return 3


def classify_critical_day_confidence(confidence: float) -> str:
    if confidence >= 80:
        return "Yüksek Zamanlama Güveni"
    if confidence >= 65:
        return "İyi Zamanlama Güveni"
    if confidence >= 50:
        return "Orta Zamanlama Güveni"
    if confidence >= 35:
        return "Düşük Zamanlama Güveni"
    return "Yetersiz Zamanlama Güveni"


def _calculate_critical_day_confidence(
    features: Mapping[str, Any],
    capacity: Mapping[str, Any],
    reachability: bool | None,
) -> dict[str, Any]:
    base_confidence = _finite_float(features.get("expected_return_model_confidence"))
    raw_confidence = base_confidence if base_confidence is not None else 0.0
    penalties: list[dict[str, Any]] = []

    def penalize(condition: bool, label: str, points: int) -> None:
        nonlocal raw_confidence
        if condition:
            raw_confidence -= points
            penalties.append({"label": label, "points": -points})

    main_expected = _finite_float(features.get("main_expected_return"))
    penalize(features.get("atr_pct") is None, "ATR% eksik", 30)
    penalize(main_expected is None, "Ana beklenti eksik", 30)
    penalize(main_expected is not None and main_expected <= 0, "Ana beklenti pozitif değil", 20)
    penalize(bool(capacity.get("lower_clamp_hit")), "Daily Directional Capacity alt sınıra değdi", 8)
    penalize(bool(capacity.get("upper_clamp_hit")), "Daily Directional Capacity üst sınıra değdi", 8)
    penalize(int(features.get("price_series_length") or 0) < 30, "Fiyat serisi 30 kapanıştan kısa", 10)
    penalize(features.get("momentum_change") is None, "Momentum değişimi eksik", 5)
    penalize(features.get("macd_histogram_direction") is None, "MACD Histogram yönü eksik", 5)
    penalize(features.get("volatility20") is None, "Volatility20 eksik", 5)
    penalize(features.get("entry_timing_score") is None, "Entry Timing sonucu eksik", 10)
    penalize(features.get("resistance") is None, "Ana direnç bilgisi eksik", 5)
    penalize(reachability is False, "Seçilen vadede erişilebilir değil", 20)

    confidence = _clamp(raw_confidence, 0.0, 100.0)
    return {
        "base_confidence": base_confidence,
        "raw_confidence": raw_confidence,
        "confidence": confidence,
        "classification": classify_critical_day_confidence(confidence),
        "penalties": penalties,
    }


def calculate_critical_day_window_v2(features: Mapping[str, Any]) -> dict[str, Any]:
    horizon = features.get("critical_day_horizon") or normalize_critical_day_horizon(features.get("selected_horizon"))
    minimum_day = int(horizon["minimum_trading_day"])
    maximum_day = int(horizon["maximum_trading_day"])
    capacity = estimate_daily_move_capacity(features)
    reach = calculate_target_reach_days(features, capacity["daily_directional_capacity"])
    adjustments = calculate_window_adjustments(features)
    warnings: list[str] = []
    limiting_factors: list[str] = []

    if horizon.get("fallback_message"):
        warnings.append(str(horizon["fallback_message"]))

    base_reach_day = reach["base_reach_day"]
    raw_adjusted_reach_day = (
        None
        if base_reach_day is None
        else base_reach_day + adjustments["acceleration_days"] + adjustments["delay_days"]
    )
    adjusted_reach_day = raw_adjusted_reach_day
    reachability: bool | None
    if raw_adjusted_reach_day is None:
        reachability = None
        main_day = None
        if reach["reason"]:
            warnings.append(str(reach["reason"]))
    elif raw_adjusted_reach_day > maximum_day:
        reachability = False
        main_day = None
        limiting_factors.append("Beklenen getiri seçilen vadede teknik olarak erişilebilir görünmüyor")
    else:
        reachability = True
        if raw_adjusted_reach_day < minimum_day:
            adjusted_reach_day = minimum_day
            warnings.append("Model hedefi seçilen vadenin alt sınırından daha erken hesapladı")
        main_day = int(adjusted_reach_day)

    critical_confidence = _calculate_critical_day_confidence(features, capacity, reachability)
    uncertainty = _finite_float(features.get("uncertainty"))
    volatility = _finite_float(features.get("volatility20"))
    expected_confidence = _finite_float(features.get("expected_return_model_confidence"))
    uncertainty_for_window = uncertainty if uncertainty is not None else 1.0
    volatility_component = max(0.0, volatility - 3.0) * 0.35 if volatility is not None else 0.0
    confidence_component = (100.0 - expected_confidence) * 0.015 if expected_confidence is not None else 1.5
    raw_window_half_width = (
        1.0
        + max(0.0, uncertainty_for_window - 1.0) * 0.45
        + volatility_component
        + confidence_component
    )
    base_window_half_width = int(_clamp(math.ceil(raw_window_half_width), MIN_WINDOW_HALF_WIDTH, MAX_WINDOW_HALF_WIDTH))
    extra_window_days = 0
    entry_score = _finite_float(features.get("entry_timing_score"))
    if entry_score is not None and entry_score < 50:
        extra_window_days += 1
    if expected_confidence is not None and expected_confidence < 50:
        extra_window_days += 1
    window_half_width = int(
        _clamp(base_window_half_width + extra_window_days, MIN_WINDOW_HALF_WIDTH, MAX_WINDOW_HALF_WIDTH)
    )

    window_start = window_end = earliest_day = late_day = None
    risk_extension = _risk_extension_days(_finite_float(features.get("risk_penalty")))
    if reachability is True and main_day is not None:
        window_start = max(minimum_day, main_day - window_half_width)
        window_end = min(maximum_day, main_day + window_half_width)
        window_start = min(window_start, main_day)
        window_end = max(window_end, main_day)

        conservative = _finite_float(features.get("conservative_expected_return"))
        if conservative is None or conservative <= 0:
            earliest_base_day = minimum_day
        else:
            earliest_base_day = math.ceil(conservative / capacity["daily_directional_capacity"])
        half_acceleration = math.ceil(abs(adjustments["acceleration_days"]) / 2)
        earliest_day = max(minimum_day, earliest_base_day - half_acceleration)
        earliest_day = min(earliest_day, window_start, main_day, window_end)

        late_day = window_end + math.ceil(uncertainty_for_window) + risk_extension
        late_day = min(maximum_day, late_day)

    if reachability is True:
        status = "ANA PENCERE"
    elif reachability is False:
        status = "VADE İÇİNDE ERİŞİLEMEZ"
    else:
        status = "SAYISAL SONUÇ ÜRETİLEMEDİ"

    return {
        "status": status,
        "reachability": reachability,
        "earliest_reasonable_day": earliest_day,
        "main_day": main_day,
        "window_start": window_start,
        "window_end": window_end,
        "late_day": late_day,
        "critical_day_model_confidence": critical_confidence["confidence"],
        "critical_day_confidence_classification": critical_confidence["classification"],
        "daily_directional_capacity": capacity["daily_directional_capacity"],
        "base_reach_day": base_reach_day,
        "adjusted_reach_day": adjusted_reach_day,
        "window_half_width": window_half_width if reachability is True else None,
        "risk_extension_days": risk_extension if reachability is True else None,
        "accelerators": adjustments["accelerators"],
        "delays": adjustments["delays"],
        "limiting_factors": limiting_factors,
        "missing_data": list(features.get("missing_data") or []),
        "warnings": list(dict.fromkeys(warnings)),
        "debug": {
            "normalized_horizon": horizon,
            "inputs": dict(features),
            "daily_capacity": capacity,
            "target_reach": reach,
            "adjustments": adjustments,
            "raw_adjusted_reach_day": raw_adjusted_reach_day,
            "adjusted_reach_day": adjusted_reach_day,
            "window": {
                "raw_window_half_width": raw_window_half_width,
                "base_window_half_width": base_window_half_width,
                "extra_window_days": extra_window_days,
                "window_half_width": window_half_width if reachability is True else None,
                "window_start": window_start,
                "window_end": window_end,
            },
            "earliest_reasonable_day": earliest_day,
            "late_day": late_day,
            "risk_extension_days": risk_extension if reachability is True else None,
            "reachability": reachability,
            "critical_day_confidence": critical_confidence,
            "missing_data": list(features.get("missing_data") or []),
        },
    }


def evaluate_critical_day_v2(
    row: Mapping[str, object],
    selected_horizon: object,
    entry_timing_result: Mapping[str, Any] | None = None,
    expected_return_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    features = build_critical_day_v2_features(
        row,
        selected_horizon,
        entry_timing_result=entry_timing_result,
        expected_return_result=expected_return_result,
    )
    result = calculate_critical_day_window_v2(features)
    return {**result, "features": features}
