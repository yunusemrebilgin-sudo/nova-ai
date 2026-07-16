from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd


ATR_HIGH_THRESHOLD = 4.0
BOLLINGER_SAFE_DISTANCE_PCT = 1.5


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


def _price_series(row: Mapping[str, object]) -> pd.Series:
    values = row.get("_portfolio_price_series", [])
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return pd.Series(dtype="float64")
    parsed = [_finite_float(value) for value in values]
    return pd.Series([value for value in parsed if value is not None], dtype="float64")


def _last_finite(series: pd.Series, offset: int = 0) -> float | None:
    values = series.dropna()
    if len(values) <= offset:
        return None
    return _finite_float(values.iloc[-1 - offset])


def _return_for_days(prices: pd.Series, days: int) -> float | None:
    if len(prices) <= days:
        return None
    start = _finite_float(prices.iloc[-1 - days])
    end = _finite_float(prices.iloc[-1])
    if start in (None, 0.0) or end is None:
        return None
    return (end / start - 1.0) * 100.0


def _rsi_series(prices: pd.Series) -> pd.Series:
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    average_gain = gain.rolling(14).mean()
    average_loss = loss.rolling(14).mean()
    zero_loss = average_loss.eq(0)
    relative_strength = average_gain / average_loss.mask(zero_loss)
    rsi = 100 - (100 / (1 + relative_strength))
    rsi = rsi.mask(zero_loss & average_gain.gt(0), 100.0)
    return rsi.mask(zero_loss & average_gain.eq(0), 50.0)


def _previous_20_close_resistance(prices: pd.Series) -> float | None:
    if len(prices) < 2:
        return None
    return _last_finite(pd.Series([prices.iloc[:-1].tail(20).max()]))


def build_entry_timing_features(row: Mapping[str, object]) -> dict[str, Any]:
    """Build LAB-only timing features from one existing Smart Scanner row."""
    prices = _price_series(row)
    close = _first_float(row, "_follow_close", "Son Fiyat")
    if close is None and not prices.empty:
        close = _finite_float(prices.iloc[-1])

    ema20_series = prices.ewm(span=20, adjust=False).mean() if not prices.empty else pd.Series(dtype="float64")
    ema50_series = prices.ewm(span=50, adjust=False).mean() if not prices.empty else pd.Series(dtype="float64")
    direct_ema20 = _first_float(row, "_follow_ema20")
    direct_ema50 = _first_float(row, "_follow_ema50")
    ema20 = direct_ema20 if direct_ema20 is not None else _last_finite(ema20_series)
    ema50 = direct_ema50 if direct_ema50 is not None else _last_finite(ema50_series)

    if not prices.empty:
        macd_series = prices.ewm(span=12, adjust=False).mean() - prices.ewm(span=26, adjust=False).mean()
        macd_signal_series = macd_series.ewm(span=9, adjust=False).mean()
        histogram_series = macd_series - macd_signal_series
        momentum_series = prices.pct_change(10) * 100.0
        rsi_series = _rsi_series(prices)
        rolling_mean = prices.rolling(20).mean()
        rolling_std = prices.rolling(20).std()
        bollinger_upper = _last_finite(rolling_mean + rolling_std * 2.0)
    else:
        macd_series = macd_signal_series = histogram_series = pd.Series(dtype="float64")
        momentum_series = rsi_series = pd.Series(dtype="float64")
        bollinger_upper = None

    macd = _last_finite(macd_series)
    macd_signal = _last_finite(macd_signal_series)
    macd_histogram = _last_finite(histogram_series)
    previous_histogram = _last_finite(histogram_series, 1)

    momentum10 = _first_float(row, "_follow_momentum10", "Momentum10", "MOMENTUM10")
    if momentum10 is None:
        momentum10 = _last_finite(momentum_series)
    previous_momentum10 = _last_finite(momentum_series, 1)

    derived_rsi14 = _last_finite(rsi_series)
    rsi14 = derived_rsi14 if derived_rsi14 is not None else _first_float(row, "RSI", "RSI14")
    previous_rsi14 = _last_finite(rsi_series, 1)

    resistance = _first_float(row, "Direnç", "Direnc")
    support = _first_float(row, "Destek")
    volume_ratio = _first_float(row, "Hacim Oranı", "Hacim Orani", "VOLUME_RATIO")
    resistance_distance = None
    if close not in (None, 0.0) and resistance is not None:
        resistance_distance = ((resistance - close) / close) * 100.0

    ema20_distance = None
    if close not in (None, 0.0) and ema20 not in (None, 0.0):
        ema20_distance = ((close - ema20) / ema20) * 100.0
    ema50_distance = None
    if close not in (None, 0.0) and ema50 not in (None, 0.0):
        ema50_distance = ((close - ema50) / ema50) * 100.0
    bollinger_upper_distance = None
    if close not in (None, 0.0) and bollinger_upper is not None:
        bollinger_upper_distance = ((bollinger_upper - close) / close) * 100.0

    previous_20_close_resistance = _previous_20_close_resistance(prices)
    breakout_close = _last_finite(prices)
    breakout_confirmed = bool(
        breakout_close is not None
        and previous_20_close_resistance is not None
        and breakout_close > previous_20_close_resistance
        and volume_ratio is not None
        and volume_ratio >= 1.10
    )

    features = {
        "close": close,
        "rsi14": rsi14,
        "previous_rsi14": previous_rsi14,
        "rsi_direction": None if rsi14 is None or previous_rsi14 is None else rsi14 - previous_rsi14,
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_histogram": macd_histogram,
        "previous_macd_histogram": previous_histogram,
        "momentum10": momentum10,
        "previous_momentum10": previous_momentum10,
        "momentum_change": None if momentum10 is None or previous_momentum10 is None else momentum10 - previous_momentum10,
        "ema20": ema20,
        "ema50": ema50,
        "ema20_distance_pct": ema20_distance,
        "ema50_distance_pct": ema50_distance,
        "adx14": _first_float(row, "_follow_adx14", "ADX", "ADX14"),
        "atr_pct": _first_float(row, "ATR%", "ATR_PCT", "ATR %"),
        "volatility20": _first_float(row, "Volatilite", "VOLATILITY20"),
        "volume_ratio": volume_ratio,
        "support": support,
        "resistance": resistance,
        "resistance_distance_pct": resistance_distance,
        "previous_20_close_resistance": previous_20_close_resistance,
        "bollinger_upper": bollinger_upper,
        "bollinger_upper_distance_pct": bollinger_upper_distance,
        "return_1d_pct": _return_for_days(prices, 1),
        "return_2d_pct": _return_for_days(prices, 2),
        "return_3d_pct": _return_for_days(prices, 3),
        "return_5d_pct": _return_for_days(prices, 5),
        "nova_score": _first_float(row, "Nova Score", "Nova Skoru"),
        "confidence": _first_float(row, "AI Güven Endeksi", "Güven Endeksi"),
        "trend": row.get("Trend"),
        "breakout_confirmed": breakout_confirmed,
        "market_data_time": row.get("_market_data_time"),
    }
    required = {
        "Son kapanış": "close",
        "RSI14": "rsi14",
        "MACD": "macd",
        "MACD Signal": "macd_signal",
        "Momentum10": "momentum10",
        "EMA20": "ema20",
        "EMA50": "ema50",
        "ADX": "adx14",
        "ATR%": "atr_pct",
        "Volatility20": "volatility20",
        "Volume Ratio": "volume_ratio",
        "Direnç": "resistance",
        "1 günlük getiri": "return_1d_pct",
        "2 günlük getiri": "return_2d_pct",
        "3 günlük getiri": "return_3d_pct",
        "5 günlük getiri": "return_5d_pct",
        "RSI geçmişi": "previous_rsi14",
        "Bollinger üst bant": "bollinger_upper",
    }
    features["missing_data"] = [label for label, key in required.items() if features.get(key) is None]
    return features


def calculate_entry_timing_score(features: Mapping[str, Any]) -> dict[str, Any]:
    score = 50
    positive: list[dict[str, Any]] = []
    negative: list[dict[str, Any]] = []
    warnings: list[str] = []

    def add(label: str, points: int) -> None:
        nonlocal score
        score += points
        (positive if points > 0 else negative).append({"label": label, "points": points})

    ema20, ema50, close = features.get("ema20"), features.get("ema50"), features.get("close")
    if ema20 is not None and ema50 is not None and ema20 > ema50:
        add("EMA20 > EMA50", 8)
    if close is not None and ema20 is not None and close > ema20:
        add("Son kapanış EMA20 üzerinde", 6)
    if features.get("adx14") is not None and features["adx14"] >= 25:
        add("ADX trend teyidi", 5)

    momentum = features.get("momentum10")
    previous_momentum = features.get("previous_momentum10")
    if momentum is not None and momentum > 0:
        add("Momentum10 pozitif", 5)
    if momentum is not None and previous_momentum is not None and momentum > previous_momentum:
        add("Momentum güçleniyor", 5)
    macd, signal = features.get("macd"), features.get("macd_signal")
    if macd is not None and signal is not None and macd > signal:
        add("MACD signal üzerinde", 6)
    histogram, previous_histogram = features.get("macd_histogram"), features.get("previous_macd_histogram")
    if histogram is not None and previous_histogram is not None and histogram > 0 and histogram > previous_histogram:
        add("MACD Histogram pozitif ve güçleniyor", 4)

    rsi = features.get("rsi14")
    if rsi is not None:
        if 45 <= rsi <= 60:
            add("RSI 45-60 sağlıklı bölge", 7)
        elif 60 < rsi <= 68:
            add("RSI 60-68 destekleyici bölge", 3)
        elif 35 <= rsi < 45:
            add("RSI 35-45 toparlanma bölgesi", 2)

    volume_ratio = features.get("volume_ratio")
    if volume_ratio is not None:
        if 1.10 <= volume_ratio <= 1.50:
            add("Hacim oranı 1.10-1.50", 5)
        elif volume_ratio > 1.50:
            add("Hacim oranı 1.50 üzerinde", 3)

    ema20_distance = features.get("ema20_distance_pct")
    if ema20_distance is not None and 0 <= ema20_distance <= 2.5:
        add("Fiyat EMA20 üzerinde dengeli konumda", 5)
    resistance_distance = features.get("resistance_distance_pct")
    if resistance_distance is not None and 3 <= resistance_distance <= 8:
        add("Dirence sağlıklı mesafe", 4)
    bollinger_distance = features.get("bollinger_upper_distance_pct")
    if bollinger_distance is not None and bollinger_distance > BOLLINGER_SAFE_DISTANCE_PCT:
        add("Bollinger üst banda aşırı yakın değil", 3)

    return_1d = features.get("return_1d_pct")
    return_3d = features.get("return_3d_pct")
    return_5d = features.get("return_5d_pct")
    if return_3d is not None and return_3d >= 8:
        add("Son 3 günlük yükseliş aşırı", -12)
        warnings.append("Sert yükseliş sonrası geç giriş riski")
    if return_5d is not None and return_5d >= 12:
        add("Son 5 günlük yükseliş aşırı", -14)
    if return_1d is not None and return_1d >= 6:
        add("Son 1 günlük yükseliş aşırı", -8)
    if ema20_distance is not None and ema20_distance > 5:
        add("Fiyat EMA20'nin %5'ten fazla üzerinde", -10)
    if ema20_distance is not None and ema20_distance > 8:
        add("Fiyat EMA20'nin %8'den fazla üzerinde", -8)

    if rsi is not None and rsi >= 70:
        add("RSI 70 ve üzerinde", -12)
        warnings.append("Aşırı alım riski")
    if rsi is not None and rsi >= 75:
        add("RSI 75 ve üzerinde ilave ceza", -8)
    if rsi is not None and rsi <= 30:
        add("RSI 30 ve altında", -5)

    near_resistance = resistance_distance is not None and 0 <= resistance_distance <= 1.5
    if near_resistance and not features.get("breakout_confirmed", False):
        add("Dirence çok yakın ve kırılım teyidi yok", -12)
        warnings.append("Direnç altında giriş riski")
        if volume_ratio is not None and volume_ratio < 1.0:
            add("Direnç altında hacim zayıf", -5)

    momentum_weakening = momentum is not None and previous_momentum is not None and momentum > 0 and momentum < previous_momentum
    histogram_weakening = macd is not None and histogram is not None and previous_histogram is not None and macd > 0 and histogram < previous_histogram
    if momentum_weakening:
        add("Momentum10 zayıflıyor", -7)
    if histogram_weakening:
        add("MACD Histogram küçülüyor", -6)
    if features.get("rsi_direction") is not None and features["rsi_direction"] < 0:
        add("RSI düşüş yönünde", -4)
    if momentum_weakening or histogram_weakening:
        warnings.append("Momentum yoruluyor")

    volatility = features.get("volatility20")
    if volatility is not None and volatility > 4:
        add("Volatilite20 4 üzerinde", -5)
    if volatility is not None and volatility > 6:
        add("Volatilite20 6 üzerinde ilave ceza", -5)
    atr_pct = features.get("atr_pct")
    if atr_pct is not None and atr_pct > ATR_HIGH_THRESHOLD:
        add(f"ATR% {ATR_HIGH_THRESHOLD:.1f} üzerinde", -5)

    return {
        "score": min(100, max(0, int(round(score)))),
        "positive_contributions": positive,
        "negative_contributions": negative,
        "warnings": list(dict.fromkeys(warnings)),
    }


def classify_entry_timing(score: int) -> str:
    if score >= 80:
        return "GİRİŞ UYGUN"
    if score >= 65:
        return "KADEMELİ GİRİŞ"
    if score >= 50:
        return "BEKLE / TEYİT GEREKİYOR"
    if score >= 35:
        return "GİRİŞ ZAYIF"
    return "GEÇ GİRİŞ / RİSKLİ"


def evaluate_entry_timing(row: Mapping[str, object]) -> dict[str, Any]:
    features = build_entry_timing_features(row)
    evaluation = calculate_entry_timing_score(features)
    missing = list(features["missing_data"])
    warnings = list(evaluation["warnings"])
    if missing:
        warnings.append("Eksik veri nedeniyle sınırlı değerlendirme")
    return {
        **evaluation,
        "classification": classify_entry_timing(evaluation["score"]),
        "features": features,
        "missing_data": missing,
        "warnings": list(dict.fromkeys(warnings)),
    }
