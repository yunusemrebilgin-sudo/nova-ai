import pandas as pd

from utils import clamp_percent, safe_float


def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    df = data.copy()
    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()

    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    df["RSI14"] = 100 - (100 / (1 + rs))

    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["DAILY_CHANGE_PCT"] = df["Close"].pct_change() * 100
    df["VOLUME_AVG20"] = df["Volume"].rolling(window=20).mean()
    df["VOLUME_RATIO"] = df["Volume"] / df["VOLUME_AVG20"]

    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["ATR14"] = true_range.rolling(window=14).mean()
    df["ATR_PCT"] = (df["ATR14"] / df["Close"]) * 100

    up_move = df["High"].diff()
    down_move = -df["Low"].diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0)
    tr_sum = true_range.rolling(window=14).sum()
    plus_di = 100 * plus_dm.rolling(window=14).sum() / tr_sum
    minus_di = 100 * minus_dm.rolling(window=14).sum() / tr_sum
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, pd.NA)) * 100
    df["ADX14"] = dx.rolling(window=14).mean()

    df["MOMENTUM10"] = df["Close"].pct_change(periods=10) * 100
    df["VOLATILITY20"] = df["Close"].pct_change().rolling(window=20).std() * 100
    df["CHANGE20"] = df["Close"].pct_change(periods=20) * 100
    return df


def support_resistance(data: pd.DataFrame) -> tuple[float, float]:
    recent_data = data.tail(20)
    return float(recent_data["Low"].min()), float(recent_data["High"].max())


def trend_text(latest: pd.Series) -> str:
    if latest["Close"] > latest["EMA20"] and latest["EMA20"] > latest["EMA50"]:
        return "Pozitif"
    if latest["Close"] < latest["EMA50"] or latest["EMA20"] < latest["EMA50"]:
        return "Negatif"
    return "Nötr"


def risk_text(latest: pd.Series) -> str:
    if latest["Close"] < latest["EMA50"] or latest["MACD"] < 0:
        return "Yüksek"
    if latest["RSI14"] > 70 or latest["EMA20"] < latest["EMA50"]:
        return "Orta"
    return "Düşük"


def nova_score(latest: pd.Series) -> int:
    score = 0
    if latest["EMA20"] > latest["EMA50"]:
        score += 30
    if latest["MACD"] > 0:
        score += 25
    if 40 <= latest["RSI14"] <= 65:
        score += 20
    if latest["Close"] > latest["EMA20"]:
        score += 15
    if latest["DAILY_CHANGE_PCT"] > 0:
        score += 10
    return clamp_percent(score)


def confidence_index(latest: pd.Series) -> int:
    score = 0
    adx = safe_float(latest.get("ADX14"))
    trend_positive = latest["EMA20"] > latest["EMA50"] and latest["Close"] > latest["EMA20"]
    if trend_positive and adx >= 25:
        score += 25
    elif trend_positive:
        score += 18
    elif adx >= 25:
        score += 10
    momentum = safe_float(latest.get("MOMENTUM10"))
    if momentum > 3:
        score += 20
    elif momentum > 0:
        score += 14
    elif momentum > -2:
        score += 6
    if latest["EMA20"] > latest["EMA50"]:
        score += 15
    elif latest["Close"] > latest["EMA20"]:
        score += 7
    if latest["MACD"] > 0:
        score += 15
    if 40 <= latest["RSI14"] <= 65:
        score += 10
    elif 30 <= latest["RSI14"] < 40 or 65 < latest["RSI14"] <= 70:
        score += 5
    volume_ratio = safe_float(latest.get("VOLUME_RATIO"), 1.0)
    if volume_ratio >= 1.2 and latest["DAILY_CHANGE_PCT"] >= 0:
        score += 10
    elif volume_ratio >= 0.8:
        score += 5
    volatility = safe_float(latest.get("VOLATILITY20"))
    if 0 < volatility <= 2.5:
        score += 5
    elif volatility <= 4:
        score += 3
    return clamp_percent(score)


def buy_suitability(score: int, latest: pd.Series) -> int:
    value = float(score)
    if 40 <= latest["RSI14"] <= 65:
        value += 8
    elif latest["RSI14"] > 70:
        value -= 22
    if latest["MACD"] > 0:
        value += 8
    else:
        value -= 14
    if latest["EMA20"] > latest["EMA50"]:
        value += 6
    else:
        value -= 12
    if latest["Close"] < latest["EMA50"]:
        value -= 24
    return clamp_percent(value)


def sell_risk(score: int, latest: pd.Series) -> int:
    value = 100 - buy_suitability(score, latest)
    if latest["RSI14"] > 70:
        value += 18
    if latest["Close"] < latest["EMA50"]:
        value += 28
    if latest["MACD"] < 0:
        value += 18
    if latest["EMA20"] < latest["EMA50"]:
        value += 12
    if safe_float(latest.get("VOLATILITY20")) > 4:
        value += 8
    return clamp_percent(value)


def result_label(score: int, confidence: int, risk: int) -> str:
    if score >= 75 and confidence >= 70 and risk < 45:
        return "🟢 Güçlü Alım"
    if score >= 50 and risk < 70:
        return "🟡 Takip Et"
    return "🔴 Uzak Dur"


def normalize_horizon(selected_horizon: str) -> str:
    return "Günlük işlem" if str(selected_horizon) == "1-5 gün" else str(selected_horizon)


def expected_holding_period(latest: pd.Series, selected_horizon: str = "Günlük işlem") -> str:
    selected_horizon = normalize_horizon(selected_horizon)
    scanner_horizon_periods = {
        "5-10 gün": "5-10 işlem günü",
        "10-30 gün": "10-30 işlem günü",
        "1-2 ay": "1-2 ay",
        "2-4 ay": "2-4 ay",
    }
    if selected_horizon in scanner_horizon_periods:
        return scanner_horizon_periods[selected_horizon]

    adx = safe_float(latest.get("ADX14"))
    volatility = safe_float(latest.get("VOLATILITY20"))

    if selected_horizon == "Günlük işlem":
        return "1-5 işlem günü" if volatility <= 4 else "1-3 işlem günü"
    if selected_horizon == "Kısa vade":
        if adx >= 25 and volatility <= 3:
            return "12-18 işlem günü"
        return "8-12 işlem günü"
    if selected_horizon == "Orta vade":
        if adx >= 25 and latest["EMA20"] > latest["EMA50"]:
            return "2-4 ay"
        return "20-35 işlem günü"
    if adx >= 25 and latest["Close"] > latest["EMA50"]:
        return "6-12 ay"
    return "2-4 ay"


def expected_return(latest: pd.Series, resistance: float, selected_horizon: str | None = None) -> float:
    close = safe_float(latest["Close"])
    atr_pct = safe_float(latest.get("ATR_PCT"))
    volatility = safe_float(latest.get("VOLATILITY20"))
    resistance_gap = max(0.0, ((resistance - close) / close) * 100) if close else 0.0
    trend_bonus = 2.0 if latest["EMA20"] > latest["EMA50"] else 0.5
    horizon_multiplier = {
        "1-5 gün": 0.85,
        "5-10 gün": 1.05,
        "10-30 gün": 1.30,
        "1-2 ay": 1.65,
        "2-4 ay": 2.05,
    }.get(selected_horizon, 1.3)
    potential = atr_pct * horizon_multiplier + resistance_gap * 0.55 + trend_bonus - volatility * 0.25
    return round(max(1.0, min(35.0, potential)), 1)


def score_breakdown(latest: pd.Series, score: int, confidence: int) -> dict[str, int]:
    adx = safe_float(latest.get("ADX14"))
    volatility = safe_float(latest.get("VOLATILITY20"))
    volume_ratio = safe_float(latest.get("VOLUME_RATIO"), 1.0)
    technical = 0
    if latest["EMA20"] > latest["EMA50"]:
        technical += 45
    if latest["Close"] > latest["EMA20"]:
        technical += 35
    if latest["Close"] > latest["EMA50"]:
        technical += 20
    momentum = 45 if latest["MACD"] > 0 else 15
    if safe_float(latest.get("MOMENTUM10")) > 0:
        momentum += 25
    trend = 30 + (30 if latest["EMA20"] > latest["EMA50"] else 0) + (20 if adx >= 25 else 0)
    volume = 45 + (30 if volume_ratio >= 1.2 else 10 if volume_ratio >= 0.8 else 0)
    risk = 100 - sell_risk(score, latest)
    vol_score = 85 if 0 < volatility <= 2 else 55 if volatility <= 4 else 35
    fundamental = 50 + (12 if volume_ratio >= 1 else 0) + (10 if latest["Close"] > latest["EMA50"] else 0)
    return {
        "Teknik": clamp_percent(technical),
        "Temel": clamp_percent(fundamental),
        "Momentum": clamp_percent(momentum),
        "Hacim": clamp_percent(volume),
        "Risk": clamp_percent(risk),
        "Trend": clamp_percent(trend),
        "Volatilite": clamp_percent(vol_score),
        "Genel": clamp_percent((score + confidence) / 2),
        "ADX": clamp_percent(adx * 3),
    }
