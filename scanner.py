import pandas as pd
import streamlit as st
import yfinance as yf

import analytics


def _scan_row(symbol: str, name: str, raw_data: pd.DataFrame) -> dict[str, object] | None:
    required = {"Open", "High", "Low", "Close", "Volume"}
    if raw_data.empty or not required.issubset(raw_data.columns):
        return None
    data = analytics.calculate_indicators(raw_data).dropna()
    if data.empty:
        return None
    latest = data.iloc[-1]
    support, resistance = analytics.support_resistance(data)
    score = analytics.nova_score(latest)
    confidence = analytics.confidence_index(latest)
    buy = analytics.buy_suitability(score, latest)
    risk = analytics.sell_risk(score, latest)
    result = analytics.result_label(score, confidence, risk)
    return {
        "Hisse": symbol,
        "Şirket": name,
        "Nova Score": score,
        "AI Güven Endeksi": confidence,
        "Beklenen Getiri %": analytics.expected_return(latest, resistance),
        "Beklenen Taşıma Süresi": analytics.expected_holding_period(latest),
        "Alım Uygunluğu %": buy,
        "Sat Riski %": risk,
        "Trend": analytics.trend_text(latest),
        "Sonuç": result,
        "RSI": round(float(latest["RSI14"]), 2),
        "MACD": round(float(latest["MACD"]), 4),
        "EMA20 > EMA50": bool(latest["EMA20"] > latest["EMA50"]),
        "Hacim Oranı": round(float(latest.get("VOLUME_RATIO", 0)), 2),
        "Volatilite": round(float(latest.get("VOLATILITY20", 0)), 2),
        "Son Fiyat": round(float(latest["Close"]), 2),
        "Destek": round(support, 2),
        "Direnç": round(resistance, 2),
    }


@st.cache_data(ttl=900, show_spinner=False)
def scan_smart_market(symbol_rows: tuple[tuple[str, str], ...]) -> tuple[pd.DataFrame, list[str]]:
    rows = []
    failed = []
    for symbol, name in symbol_rows:
        try:
            raw_data = yf.download(
                symbol,
                period="6mo",
                interval="1d",
                progress=False,
                auto_adjust=True,
                multi_level_index=False,
                timeout=15,
            )
            row = _scan_row(symbol, name, raw_data)
        except Exception:
            row = None
        if row is None:
            failed.append(symbol)
        else:
            rows.append(row)
    table = pd.DataFrame(rows)
    if not table.empty:
        table = table.sort_values(["Nova Score", "AI Güven Endeksi"], ascending=False).reset_index(drop=True)
        table.insert(0, "Sıra", range(1, len(table) + 1))
    return table, failed


def apply_filters(
    table: pd.DataFrame,
    trend: str,
    momentum: str,
    min_score: int,
    min_confidence: int,
    ema_filter: bool,
    macd_filter: str,
    rsi_range: tuple[int, int],
    min_volume_ratio: float,
    max_volatility: float,
) -> pd.DataFrame:
    if table.empty:
        return table
    filtered = table.copy()
    if trend != "Tümü":
        filtered = filtered[filtered["Trend"] == trend]
    if momentum == "Pozitif":
        filtered = filtered[filtered["MACD"] > 0]
    elif momentum == "Negatif":
        filtered = filtered[filtered["MACD"] < 0]
    filtered = filtered[filtered["Nova Score"] >= min_score]
    filtered = filtered[filtered["AI Güven Endeksi"] >= min_confidence]
    if ema_filter:
        filtered = filtered[filtered["EMA20 > EMA50"]]
    if macd_filter == "Pozitif":
        filtered = filtered[filtered["MACD"] > 0]
    elif macd_filter == "Negatif":
        filtered = filtered[filtered["MACD"] < 0]
    filtered = filtered[(filtered["RSI"] >= rsi_range[0]) & (filtered["RSI"] <= rsi_range[1])]
    filtered = filtered[filtered["Hacim Oranı"] >= min_volume_ratio]
    filtered = filtered[filtered["Volatilite"] <= max_volatility]
    return filtered.reset_index(drop=True)
