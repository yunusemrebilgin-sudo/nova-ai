from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

import critical_day_v2
import entry_timing
import expected_return_v2


SEVERITY_PENALTIES = {"KRİTİK": 25, "YÜKSEK": 15, "ORTA": 8}
CAUTIOUS_ENTRY_CLASSES = {
    "BEKLE / TEYİT GEREKİYOR",
    "GİRİŞ ZAYIF",
    "GEÇ GİRİŞ / RİSKLİ",
}
STRONG_BUY_SUITABILITY = 70.0
WEAK_BUY_SUITABILITY = 50.0


def _finite_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _first_float(row: Mapping[str, object], *keys: str) -> float | None:
    for key in keys:
        number = _finite_float(row.get(key))
        if number is not None:
            return number
    return None


def _unique_strings(*groups: object) -> list[str]:
    result: list[str] = []
    for group in groups:
        if not isinstance(group, Sequence) or isinstance(group, (str, bytes)):
            continue
        for value in group:
            text = str(value).strip()
            if text and text not in result:
                result.append(text)
    return result


def _normalized_signal(value: object) -> str:
    return str(value or "").upper().replace("İ", "I").replace("Ö", "O").replace("Ü", "U").replace("Ş", "S").replace("Ğ", "G").replace("Ç", "C")


def _current_system_positive(features: Mapping[str, Any]) -> bool:
    signal = _normalized_signal(features.get("current_signal"))
    suitability = _finite_float(features.get("current_buy_suitability"))
    return "GUCLU ALIM" in signal or signal == "AL" or suitability is not None and suitability >= STRONG_BUY_SUITABILITY


def _current_system_cautious(features: Mapping[str, Any]) -> bool:
    signal = _normalized_signal(features.get("current_signal"))
    suitability = _finite_float(features.get("current_buy_suitability"))
    cautious_signal = any(token in signal for token in ("BEKLE", "TAKIP", "NOTR", "UZAK", "SAT"))
    return cautious_signal or suitability is not None and suitability < WEAK_BUY_SUITABILITY


def parse_current_trading_window(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        start = _finite_float(value.get("start"))
        end = _finite_float(value.get("end"))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) == 2:
        start, end = _finite_float(value[0]), _finite_float(value[1])
    else:
        text = str(value or "").strip()
        if "işlem günü" not in text.lower():
            return {"raw": value, "start": None, "end": None, "parseable": False}
        range_match = re.search(r"(\d+)\s*[-–]\s*(\d+)", text)
        single_match = re.search(r"(\d+)", text)
        if range_match:
            start, end = float(range_match.group(1)), float(range_match.group(2))
        elif single_match:
            start = end = float(single_match.group(1))
        else:
            start = end = None
    if start is None or end is None or start < 1 or end < start or not start.is_integer() or not end.is_integer():
        return {"raw": value, "start": None, "end": None, "parseable": False}
    return {"raw": value, "start": int(start), "end": int(end), "parseable": True}


def build_validation_features(
    row: Mapping[str, object],
    selected_horizon: object,
    entry_timing_result: Mapping[str, Any],
    expected_return_result: Mapping[str, Any],
    critical_day_result: Mapping[str, Any],
) -> dict[str, Any]:
    entry_features = dict(entry_timing_result.get("features") or {})
    expected_features = dict(expected_return_result.get("features") or entry_features)
    critical_features = dict(critical_day_result.get("features") or expected_features)
    current_window_raw = row.get("Beklenen Taşıma Süresi")
    current_window = parse_current_trading_window(current_window_raw)

    features = {
        "symbol": row.get("Hisse"),
        "selected_horizon": selected_horizon,
        "current_close": _first_float(row, "_follow_close", "Son Fiyat"),
        "current_expected_return": _first_float(row, "Beklenen Getiri %"),
        "current_nova_score": _first_float(row, "Nova Score", "Nova Skoru"),
        "current_confidence": _first_float(row, "AI Güven Endeksi", "Güven Endeksi"),
        "current_buy_suitability": _first_float(row, "Alım Uygunluğu %"),
        "current_signal": row.get("Sonuç", row.get("Sinyal")),
        "current_risk": _first_float(row, "Sat Riski %", "Risk"),
        "current_holding_period": current_window_raw,
        "current_window": current_window,
        "trend": row.get("Trend"),
        "rsi": _first_float(row, "RSI", "RSI14"),
        "macd": _first_float(row, "MACD"),
        "volatility": _first_float(row, "Volatilite", "VOLATILITY20"),
        "volume_ratio": _first_float(row, "Hacim Oranı", "VOLUME_RATIO"),
        "support": _first_float(row, "Destek"),
        "resistance": _first_float(row, "Direnç", "Direnc"),
        "market_data_time": row.get("_market_data_time"),
        "atr_pct": _finite_float(expected_features.get("atr_pct")),
        "price_series_length": int(expected_features.get("price_series_length") or 0),
        "entry_timing_score": _finite_float(entry_timing_result.get("score")),
        "entry_timing_classification": entry_timing_result.get("classification"),
        "entry_positive_contributions": list(entry_timing_result.get("positive_contributions") or []),
        "entry_negative_contributions": list(entry_timing_result.get("negative_contributions") or []),
        "entry_warnings": list(entry_timing_result.get("warnings") or []),
        "entry_missing_data": list(entry_timing_result.get("missing_data") or []),
        "v2_conservative_expected_return": _finite_float(expected_return_result.get("conservative_expected_return")),
        "v2_main_expected_return": _finite_float(expected_return_result.get("main_expected_return")),
        "v2_optimistic_expected_return": _finite_float(expected_return_result.get("optimistic_expected_return")),
        "v2_model_confidence": _finite_float(expected_return_result.get("model_confidence")),
        "directional_quality_score": _finite_float(expected_return_result.get("directional_quality_score")),
        "movement_capacity": _finite_float(expected_return_result.get("movement_capacity")),
        "entry_timing_adjustment": _finite_float(expected_return_result.get("entry_timing_adjustment")),
        "resistance_adjustment": _finite_float(expected_return_result.get("resistance_adjustment")),
        "v2_risk_penalty": _finite_float(expected_return_result.get("risk_penalty")),
        "uncertainty": _finite_float(expected_return_result.get("uncertainty")),
        "expected_limiting_factors": list(expected_return_result.get("limiting_factors") or []),
        "expected_missing_data": list(expected_return_result.get("missing_data") or []),
        "critical_earliest_day": critical_day_result.get("earliest_reasonable_day"),
        "critical_main_day": critical_day_result.get("main_day"),
        "critical_window_start": critical_day_result.get("window_start"),
        "critical_window_end": critical_day_result.get("window_end"),
        "critical_late_day": critical_day_result.get("late_day"),
        "critical_reachability": critical_day_result.get("reachability"),
        "critical_model_confidence": _finite_float(critical_day_result.get("critical_day_model_confidence")),
        "critical_accelerators": list(critical_day_result.get("accelerators") or []),
        "critical_delays": list(critical_day_result.get("delays") or []),
        "critical_limiting_factors": list(critical_day_result.get("limiting_factors") or []),
        "critical_missing_data": list(critical_day_result.get("missing_data") or []),
        "critical_status": critical_day_result.get("status"),
    }

    missing_data = _unique_strings(
        features["entry_missing_data"],
        features["expected_missing_data"],
        features["critical_missing_data"],
    )
    if not current_window["parseable"]:
        missing_data.append("Mevcut kritik pencere sayısal işlem gününe çevrilemedi")
    features["missing_data"] = list(dict.fromkeys(missing_data))
    v2_main_expected = features["v2_main_expected_return"]
    features["critical_data_flags"] = {
        "atr_missing": features["atr_pct"] is None,
        "v2_main_missing": v2_main_expected is None,
        "entry_timing_missing": features["entry_timing_score"] is None,
        "critical_numeric_missing": (
            features["critical_reachability"] is None
            and (v2_main_expected is None or v2_main_expected > 0)
        ),
        "price_series_critically_short": features["price_series_length"] < 30,
    }
    return features


def compare_current_and_lab_models(features: Mapping[str, Any]) -> dict[str, Any]:
    current_expected = _finite_float(features.get("current_expected_return"))
    v2_expected = _finite_float(features.get("v2_main_expected_return"))
    if current_expected is None or v2_expected is None:
        difference = absolute_difference = None
        difference_class = None
    else:
        difference = v2_expected - current_expected
        absolute_difference = abs(difference)
        if absolute_difference <= 1.5:
            difference_class = "Yakın"
        elif absolute_difference <= 3.0:
            difference_class = "Orta Fark"
        elif absolute_difference <= 5.0:
            difference_class = "Yüksek Fark"
        else:
            difference_class = "Kritik Fark"

    current_window = features.get("current_window") or {}
    v2_start = features.get("critical_window_start")
    v2_end = features.get("critical_window_end")
    if current_window.get("parseable") and v2_start is not None and v2_end is not None:
        overlap = max(current_window["start"], int(v2_start)) <= min(current_window["end"], int(v2_end))
    else:
        overlap = None
    return {
        "expected_return_difference": difference,
        "absolute_expected_return_difference": absolute_difference,
        "expected_return_difference_class": difference_class,
        "current_window": current_window,
        "v2_window": {"start": v2_start, "end": v2_end},
        "window_overlap": overlap,
    }


def _conflict(
    conflict_id: str,
    severity: str,
    title: str,
    description: str,
    current_value: object,
    lab_value: object,
) -> dict[str, Any]:
    return {
        "id": conflict_id,
        "severity": severity,
        "title": title,
        "description": description,
        "current_value": current_value,
        "lab_value": lab_value,
    }


def detect_model_conflicts(features: Mapping[str, Any], comparison: Mapping[str, Any]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(item: dict[str, Any]) -> None:
        if item["id"] not in seen:
            seen.add(item["id"])
            conflicts.append(item)

    nova = _finite_float(features.get("current_nova_score"))
    confidence = _finite_float(features.get("current_confidence"))
    entry_score = _finite_float(features.get("entry_timing_score"))
    current_expected = _finite_float(features.get("current_expected_return"))
    v2_expected = _finite_float(features.get("v2_main_expected_return"))
    v2_confidence = _finite_float(features.get("v2_model_confidence"))
    reachability = features.get("critical_reachability")
    entry_class = str(features.get("entry_timing_classification") or "")

    if entry_score is not None and entry_score < 50 and ((nova is not None and nova >= 70) or (confidence is not None and confidence >= 70)):
        add(_conflict("strong_stock_bad_entry", "YÜKSEK", "Güçlü hisse, ancak mevcut giriş zamanı zayıf", "Ana kalite göstergeleri güçlü olsa da Entry Timing skoru 50 altında.", {"Nova Score": nova, "Güven Endeksi": confidence}, {"Entry Timing Score": entry_score}))
    if current_expected is not None and v2_expected is not None and current_expected >= 7 and current_expected - v2_expected >= 3:
        add(_conflict("current_return_above_v2", "YÜKSEK", "Mevcut motor getiri potansiyelini LAB modelinden belirgin yüksek gösteriyor", "Mevcut beklenti, V2 ana beklentiden en az 3 puan yüksek.", current_expected, v2_expected))
    if v2_expected is not None and v2_expected > 0 and reachability is False:
        add(_conflict("positive_return_unreachable", "KRİTİK", "Pozitif getiri beklentisi var, ancak seçilen vadede teknik olarak erişilebilir görünmüyor", "Expected Return V2 pozitif; Critical Day V2 seçilen vadede erişilebilirlik üretmiyor.", v2_expected, reachability))
    if v2_expected is not None and v2_expected >= 7 and v2_confidence is not None and v2_confidence < 50:
        add(_conflict("high_return_low_confidence", "YÜKSEK", "Yüksek beklenti, düşük model güveniyle üretilmiş", "V2 beklentisi yüksek olmasına rağmen model güveni 50 altında.", None, {"V2 beklenti": v2_expected, "Model güveni": v2_confidence}))
    if entry_score is not None and entry_score >= 65 and v2_expected is not None and v2_expected <= 0:
        add(_conflict("good_entry_nonpositive_return", "ORTA", "Giriş yapısı olumlu, ancak teknik getiri beklentisi pozitif değil", "Entry Timing olumlu ancak V2 ana beklenti sıfır veya negatif.", None, {"Entry Timing Score": entry_score, "V2 beklenti": v2_expected}))
    window_start = features.get("critical_window_start")
    window_end = features.get("critical_window_end")
    uncertainty = _finite_float(features.get("uncertainty"))
    if window_start is not None and window_end is not None and int(window_end) - int(window_start) <= 2 and uncertainty is not None and uncertainty >= 4:
        add(_conflict("narrow_window_high_uncertainty", "ORTA", "Kritik pencere dar, fakat getiri belirsizliği yüksek", "V2 kritik pencere genişliği 2 gün veya daha az; belirsizlik en az 4.", None, {"Pencere": [window_start, window_end], "Belirsizlik": uncertainty}))
    if _current_system_positive(features) and entry_class in CAUTIOUS_ENTRY_CLASSES:
        add(_conflict("current_buy_lab_wait", "YÜKSEK", "Mevcut sistem girişe olumlu, LAB zamanlama modeli temkinli", "Mevcut sinyal veya alım uygunluğu olumlu; Entry Timing sınıfı temkinli.", {"Sinyal": features.get("current_signal"), "Alım uygunluğu": features.get("current_buy_suitability")}, entry_class))
    if entry_score is not None and entry_score >= 80 and v2_expected is not None and v2_expected > 0 and reachability is True and _current_system_cautious(features):
        add(_conflict("lab_positive_current_cautious", "ORTA", "LAB modelleri olumlu, mevcut sistem daha temkinli", "Üç LAB motoru olumlu koşulları sağlarken mevcut sistem temkinli.", {"Sinyal": features.get("current_signal"), "Alım uygunluğu": features.get("current_buy_suitability")}, {"Entry Timing": entry_score, "V2 beklenti": v2_expected, "Reachability": reachability}))
    critical_flags = features.get("critical_data_flags") or {}
    if any(bool(value) for value in critical_flags.values()):
        add(_conflict("critical_data_missing", "KRİTİK", "Karşılaştırma kritik veri eksikliği nedeniyle sınırlı", "En az bir LAB motorunun sayısal karşılaştırma için zorunlu girdisi eksik.", None, [key for key, value in critical_flags.items() if value]))
    if comparison.get("window_overlap") is False:
        add(_conflict("window_no_overlap", "YÜKSEK", "Mevcut ve V2 kritik pencereleri çakışmıyor", "Sayısal mevcut pencere ile V2 penceresinin ortak işlem günü bulunmuyor.", comparison.get("current_window"), comparison.get("v2_window")))
    return conflicts


def calculate_validation_score(
    features: Mapping[str, Any],
    comparison: Mapping[str, Any],
    conflicts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    raw_score = 100
    penalties: list[dict[str, Any]] = []
    applied_keys: set[str] = set()
    conflict_ids = {str(item.get("id")) for item in conflicts}

    def penalize(key: str, label: str, points: int) -> None:
        nonlocal raw_score
        if key in applied_keys:
            return
        applied_keys.add(key)
        raw_score -= points
        penalties.append({"key": key, "label": label, "points": -points})

    for item in conflicts:
        severity = str(item.get("severity"))
        penalize(f"conflict:{item.get('id')}", str(item.get("title")), SEVERITY_PENALTIES[severity])

    absolute_difference = _finite_float(comparison.get("absolute_expected_return_difference"))
    if "current_return_above_v2" not in conflict_ids and absolute_difference is not None:
        if absolute_difference > 5:
            penalize("expected_return_gap", "Expected Return farkı 5 puan üzerinde", 15)
        elif absolute_difference >= 3:
            penalize("expected_return_gap", "Expected Return farkı 3-5 puan", 8)

    if comparison.get("window_overlap") is False and "window_no_overlap" not in conflict_ids:
        penalize("window_no_overlap", "Mevcut ve V2 kritik pencereleri çakışmıyor", 15)

    v2_confidence = _finite_float(features.get("v2_model_confidence"))
    critical_confidence = _finite_float(features.get("critical_model_confidence"))
    if (v2_confidence is not None and v2_confidence < 35) or (critical_confidence is not None and critical_confidence < 35):
        penalize("low_lab_confidence", "LAB motor güvenlerinden en az biri 35 altında", 10)

    critical_missing_absorbed = "critical_data_missing" in conflict_ids
    if any(bool(value) for value in (features.get("critical_data_flags") or {}).values()) and not critical_missing_absorbed:
        penalize("critical_missing_data", "Kritik veri eksikliği", 20)

    score = min(100, max(0, raw_score))
    return {
        "raw_score": raw_score,
        "score": score,
        "classification": classify_validation_result(score),
        "penalties": penalties,
        "critical_missing_absorbed_by_conflict": critical_missing_absorbed,
    }


def classify_validation_result(score: int) -> str:
    if score >= 85:
        return "YÜKSEK TUTARLILIK"
    if score >= 70:
        return "İYİ TUTARLILIK"
    if score >= 50:
        return "ORTA TUTARLILIK"
    if score >= 30:
        return "DÜŞÜK TUTARLILIK"
    return "KRİTİK UYUMSUZLUK"


def build_validation_summary(
    features: Mapping[str, Any],
    conflicts: Sequence[Mapping[str, Any]],
    validation_score: int,
) -> dict[str, str]:
    entry_score = _finite_float(features.get("entry_timing_score"))
    v2_expected = _finite_float(features.get("v2_main_expected_return"))
    reachability = features.get("critical_reachability")
    nova = _finite_float(features.get("current_nova_score"))
    confidence = _finite_float(features.get("current_confidence"))
    critical_missing = any(item.get("id") == "critical_data_missing" for item in conflicts)
    has_critical_conflict = any(item.get("severity") == "KRİTİK" for item in conflicts)

    if critical_missing or v2_expected is None or entry_score is None or validation_score < 50:
        decision = "MODEL BELİRSİZ"
        reason = "Kritik girdiler eksik veya model tutarlılığı güvenilir ortak sonuç üretmek için yetersiz."
    elif reachability is False:
        decision = "VADEYLE UYUMSUZ"
        reason = "V2 getiri beklentisi seçilen işlem günü vadesinde erişilebilir görünmüyor."
    elif v2_expected <= 0:
        decision = "TEKNİK BEKLENTİ ZAYIF"
        reason = f"Expected Return V2 ana beklentisi %{v2_expected:.2f}; pozitif teknik hedef oluşmadı."
    elif entry_score < 50 and ((nova is not None and nova >= 70) or (confidence is not None and confidence >= 70)):
        decision = "GÜÇLÜ ADAY — GİRİŞ KAÇMIŞ OLABİLİR"
        reason = f"Nova Score/Güven yapısı güçlü, ancak Entry Timing Score {entry_score:.0f}; mevcut giriş zamanı zayıf."
    elif entry_score >= 65 and v2_expected > 0 and reachability is True and validation_score >= 70 and not has_critical_conflict:
        decision = "UYGUN ADAY — GİRİŞ UYGUN"
        reason = f"Entry Timing Score {entry_score:.0f}, V2 ana beklenti %{v2_expected:.2f} ve kritik pencere erişilebilir."
    elif 50 <= entry_score < 65 and v2_expected > 0 and reachability is True and not critical_missing:
        decision = "UYGUN ADAY — TEYİT BEKLE"
        reason = f"V2 beklenti pozitif, ancak Entry Timing Score {entry_score:.0f}; ek teknik teyit gerekiyor."
    else:
        decision = "MODEL BELİRSİZ"
        reason = "Mevcut sistem ve LAB motorları ortak bir doğrulama sınıfında birleşmedi."
    return {"decision": decision, "reason": reason}


def _build_agreements_and_divergences(
    features: Mapping[str, Any],
    comparison: Mapping[str, Any],
    conflicts: Sequence[Mapping[str, Any]],
) -> tuple[list[str], list[str]]:
    agreements: list[str] = []
    if comparison.get("expected_return_difference_class") == "Yakın":
        agreements.append("Mevcut ve V2 beklenen getiri sonuçları yakın")
    if comparison.get("window_overlap") is True:
        agreements.append("Mevcut ve V2 kritik pencereleri çakışıyor")
    if _current_system_positive(features) and (_finite_float(features.get("entry_timing_score")) or 0) >= 65:
        agreements.append("Mevcut giriş görünümü ile Entry Timing sonucu olumlu yönde ortaklaşıyor")
    if features.get("critical_reachability") is True and (_finite_float(features.get("v2_main_expected_return")) or 0) > 0:
        agreements.append("Pozitif V2 beklentisi seçilen vadede erişilebilir")
    divergences = [str(item.get("title")) for item in conflicts]
    return agreements, list(dict.fromkeys(divergences))


def evaluate_validation_engine(
    row: Mapping[str, object],
    selected_horizon: object,
    entry_timing_result: Mapping[str, Any] | None = None,
    expected_return_result: Mapping[str, Any] | None = None,
    critical_day_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    entry_result = dict(entry_timing_result) if entry_timing_result is not None else entry_timing.evaluate_entry_timing(row)
    expected_result = (
        dict(expected_return_result)
        if expected_return_result is not None
        else expected_return_v2.evaluate_expected_return_v2(row, selected_horizon, entry_result)
    )
    critical_result = (
        dict(critical_day_result)
        if critical_day_result is not None
        else critical_day_v2.evaluate_critical_day_v2(row, selected_horizon, entry_result, expected_result)
    )
    features = build_validation_features(row, selected_horizon, entry_result, expected_result, critical_result)
    comparison = compare_current_and_lab_models(features)
    conflicts = detect_model_conflicts(features, comparison)
    score = calculate_validation_score(features, comparison, conflicts)
    summary = build_validation_summary(features, conflicts, score["score"])
    agreements, divergences = _build_agreements_and_divergences(features, comparison, conflicts)
    limiting_factors = _unique_strings(features["expected_limiting_factors"], features["critical_limiting_factors"])
    return {
        "symbol": features.get("symbol"),
        "model_consistency_score": score["score"],
        "model_consistency_classification": score["classification"],
        "summary": summary,
        "comparison": comparison,
        "conflicts": conflicts,
        "agreements": agreements,
        "divergences": divergences,
        "missing_data": list(features["missing_data"]),
        "limiting_factors": limiting_factors,
        "features": features,
        "debug": {
            "current_system_inputs": {key: value for key, value in features.items() if key.startswith("current_") or key in {"symbol", "selected_horizon", "trend", "rsi", "macd", "volatility", "volume_ratio", "support", "resistance", "market_data_time"}},
            "entry_timing_result": entry_result,
            "expected_return_v2_result": expected_result,
            "critical_day_v2_result": critical_result,
            "comparison": comparison,
            "conflicts": conflicts,
            "score_penalties": score["penalties"],
            "raw_model_consistency_score": score["raw_score"],
            "clamped_model_consistency_score": score["score"],
            "decision_priority": ["MODEL BELİRSİZ", "VADEYLE UYUMSUZ", "TEKNİK BEKLENTİ ZAYIF", "GÜÇLÜ ADAY — GİRİŞ KAÇMIŞ OLABİLİR", "UYGUN ADAY — GİRİŞ UYGUN", "UYGUN ADAY — TEYİT BEKLE", "MODEL BELİRSİZ fallback"],
            "missing_data": list(features["missing_data"]),
            "critical_missing_absorbed_by_conflict": score["critical_missing_absorbed_by_conflict"],
        },
    }
