import pandas as pd
import plotly.graph_objects as go
import re
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from plotly.subplots import make_subplots
from zoneinfo import ZoneInfo

import analytics as nova_analytics
import decision_center as nova_decision
import scanner as nova_scanner
import user_store
from theme import apply_terminal_theme, init_theme_state, set_theme_from_toggle, theme_tokens

DECISION_SUPPORT_DISCLAIMER = "Bu platform yalnızca karar destek amaçlıdır. Kesin yatırım tavsiyesi vermez."
DISCLAIMER = DECISION_SUPPORT_DISCLAIMER
SIGNAL_DISCLAIMER = DECISION_SUPPORT_DISCLAIMER
BIST_SYMBOLS_PATH = Path("data/bist_symbols.csv")
SMART_SCAN_MODES = {
    "Hızlı Tarama: İlk 50 hisse": 50,
    "Geniş Tarama: İlk 150 hisse": 150,
    "Tam Tarama: Tüm BIST": None,
}
SMART_SCANNER_HORIZONS = [
    "1-5 gün",
    "5-10 gün",
    "10-30 gün",
    "1-2 ay",
    "2-4 ay",
]
SMART_SCANNER_CALC_VERSION = "smart-scanner-news-impact-v1"

GLOBAL_TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "TSLA",
    "BTC-USD",
    "GC=F",
    "USDTRY=X",
]

PERIOD_OPTIONS = {
    "1 Ay": "1mo",
    "3 Ay": "3mo",
    "6 Ay": "6mo",
    "1 Yıl": "1y",
    "2 Yıl": "2y",
}
DEFAULT_PERIOD_LABEL = "6 Ay"

TRADE_HORIZONS = [
    "Günlük işlem",
    "Kısa vade",
    "Orta vade",
    "Uzun vade",
]

TIMEFRAME_WINDOWS = {
    "Günlük": 2,
    "Haftalık": 5,
    "Aylık": 21,
    "3 Aylık": 63,
    "6 Aylık": 126,
    "1 Yıllık": 252,
}

PUBLIC_DASHBOARD_PAGE = "Dashboard"
SMART_SCANNER_PAGE = "🔐 Smart Scanner"
YEB_PRO_PAGE = "⭐ YEB PRO"
PAGES = [
    PUBLIC_DASHBOARD_PAGE,
    SMART_SCANNER_PAGE,
    YEB_PRO_PAGE,
]
PRO_MODULES = [
    "Aldım",
    "Sattım",
    "Pozisyon Takibi",
    "Simülasyon",
    "Trade Journal",
    "Bildirimler",
]
DEFAULT_PRO_MODULE = "Pozisyon Takibi"
APP_TIMEZONE_NAME = "Europe/Istanbul"


def app_timezone() -> timezone:
    try:
        return ZoneInfo(APP_TIMEZONE_NAME)
    except Exception:
        return timezone(timedelta(hours=3))


def stop_app() -> None:
    st.stop()
    raise SystemExit


def sync_manual_ticker() -> None:
    st.session_state.manual_ticker = st.session_state.quick_ticker


def now_istanbul() -> datetime:
    return datetime.now(app_timezone())


def current_timestamp_label() -> str:
    return now_istanbul().strftime("%d.%m.%Y %H:%M:%S")


def init_access_state() -> None:
    if "is_authenticated" not in st.session_state:
        st.session_state.is_authenticated = False
    if "auth_user" not in st.session_state:
        st.session_state.auth_user = ""
    if "yeb_pro_active" not in st.session_state:
        st.session_state.yeb_pro_active = False
    if "yeb_data_user" not in st.session_state:
        st.session_state.yeb_data_user = ""
    if "yeb_open_positions" not in st.session_state:
        st.session_state.yeb_open_positions = []
    if "yeb_closed_trades" not in st.session_state:
        st.session_state.yeb_closed_trades = []
    if "yeb_pro_module" not in st.session_state:
        st.session_state.yeb_pro_module = DEFAULT_PRO_MODULE


def is_authenticated() -> bool:
    return bool(st.session_state.get("is_authenticated", False))


def has_pro_access() -> bool:
    return bool(st.session_state.get("yeb_pro_active", False))


def current_auth_user() -> str:
    return str(st.session_state.get("auth_user", "")).strip().lower()


def load_current_user_pro_data() -> None:
    username = current_auth_user()
    if not username or st.session_state.get("yeb_data_user") == username:
        return
    st.session_state.yeb_open_positions = user_store.load_open_positions(username)
    st.session_state.yeb_closed_trades = user_store.load_closed_trades(username)
    st.session_state.yeb_data_user = username


def save_current_user_pro_data() -> None:
    username = current_auth_user()
    if not username:
        return
    user_store.save_open_positions(username, st.session_state.get("yeb_open_positions", []))
    user_store.save_closed_trades(username, st.session_state.get("yeb_closed_trades", []))
    st.session_state.yeb_data_user = username


def logout_current_user() -> None:
    st.session_state.is_authenticated = False
    st.session_state.auth_user = ""
    st.session_state.yeb_pro_active = False
    st.session_state.yeb_data_user = ""
    st.session_state.yeb_open_positions = []
    st.session_state.yeb_closed_trades = []


@st.cache_data(show_spinner=False)
def load_bist_symbols() -> pd.DataFrame:
    if not BIST_SYMBOLS_PATH.exists():
        raise FileNotFoundError("data/bist_symbols.csv bulunamadı.")

    symbols = pd.read_csv(BIST_SYMBOLS_PATH)
    required_columns = {"symbol", "name", "sector"}
    if not required_columns.issubset(symbols.columns):
        raise ValueError("data/bist_symbols.csv kolonları symbol,name,sector olmalıdır.")

    symbols = symbols.dropna(subset=["symbol", "name", "sector"]).copy()
    symbols["symbol"] = symbols["symbol"].astype(str).str.strip().str.upper()
    symbols["name"] = symbols["name"].astype(str).str.strip()
    symbols["sector"] = symbols["sector"].astype(str).str.strip()
    symbols["search_text"] = (
        symbols["symbol"].str.lower() + " " + symbols["name"].str.lower() + " " + symbols["sector"].str.lower()
    )
    return symbols.drop_duplicates(subset=["symbol"]).reset_index(drop=True)


def get_bist_symbols_or_stop() -> pd.DataFrame:
    try:
        return load_bist_symbols()
    except FileNotFoundError:
        st.error("data/bist_symbols.csv bulunamadı.")
        stop_app()
    except Exception:
        st.error("BIST hisse listesi okunamadı. Lütfen CSV dosyasını kontrol edin.")
        stop_app()


def filter_symbols(symbols: pd.DataFrame, query: str) -> pd.DataFrame:
    query = query.strip().lower()
    if not query:
        return symbols

    return symbols[symbols["search_text"].str.contains(query, na=False, regex=False)]


@st.cache_data(show_spinner=False)
def build_symbol_labels(symbols: pd.DataFrame) -> dict[str, str]:
    return {
        row.symbol: f"{row.symbol} - {row.name} ({row.sector})"
        for row in symbols[["symbol", "name", "sector"]].itertuples(index=False)
    }


def symbol_label(symbol: str, symbols: pd.DataFrame) -> str:
    return build_symbol_labels(symbols).get(symbol, symbol)


def render_sidebar() -> str:
    with st.sidebar:
        st.markdown(
            """
            <div class="nova-logo">
                <div class="nova-logo-main">NOVA AI</div>
                <div class="nova-logo-sub">AI Market Intelligence</div>
            </div>
            <div class="nova-sidebar-line"></div>
            """,
            unsafe_allow_html=True,
        )
        if "selected_page" not in st.session_state:
            st.session_state.selected_page = PUBLIC_DASHBOARD_PAGE
        page = st.radio("Menü", PAGES, label_visibility="collapsed", key="selected_page")
        st.markdown('<div class="nova-sidebar-line"></div>', unsafe_allow_html=True)
        if is_authenticated():
            st.caption(f"Oturum: {st.session_state.auth_user}")
            if st.button("Çıkış Yap"):
                logout_current_user()
                st.rerun()
        else:
            st.caption("Smart Scanner için giriş gerekir.")
        st.markdown('<div class="nova-sidebar-line"></div>', unsafe_allow_html=True)
        st.toggle(
            "☀️ Light Mode",
            key="theme_toggle",
            on_change=set_theme_from_toggle,
        )
        st.caption("🌙 Dark Mode / ☀️ Light Mode")
        st.markdown('<div class="nova-sidebar-line"></div>', unsafe_allow_html=True)
        st.caption(DISCLAIMER)
    return page


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
    plus_di = 100 * plus_dm.rolling(window=14).sum() / true_range.rolling(window=14).sum()
    minus_di = 100 * minus_dm.rolling(window=14).sum() / true_range.rolling(window=14).sum()
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, pd.NA)) * 100
    df["ADX14"] = dx.rolling(window=14).mean()

    df["MOMENTUM10"] = df["Close"].pct_change(periods=10) * 100
    df["VOLATILITY20"] = df["Close"].pct_change().rolling(window=20).std() * 100
    df["CHANGE20"] = df["Close"].pct_change(periods=20) * 100

    return df


def calculate_general_score(latest: pd.Series) -> tuple[int, list[str]]:
    score = 0
    reasons = []

    if latest["EMA20"] > latest["EMA50"]:
        score += 30
        reasons.append("EMA20, EMA50'nin üzerinde olduğu için trend pozitif katkı verdi.")

    if latest["MACD"] > 0:
        score += 25
        reasons.append("MACD pozitif olduğu için momentum tarafı destekleyici.")

    if 40 <= latest["RSI14"] <= 65:
        score += 20
        reasons.append("RSI 40-65 aralığında olduğu için sağlıklı bölge puanı eklendi.")
    elif latest["RSI14"] > 70:
        reasons.append("RSI 70 üzerinde; aşırı alım nedeniyle temkin gerektiriyor.")
    elif latest["RSI14"] < 30:
        reasons.append("RSI 30 altında; aşırı satım ve tepki ihtimali izlenebilir.")

    if latest["Close"] > latest["EMA20"]:
        score += 15
        reasons.append("Son kapanış EMA20 üzerinde olduğu için kısa vadeli fiyat gücü var.")

    if latest["DAILY_CHANGE_PCT"] > 0:
        score += 10
        reasons.append("Günlük değişim pozitif olduğu için kısa vadeli destek eklendi.")

    if latest["Close"] < latest["EMA50"]:
        reasons.append("Fiyat EMA50 altına indiği için risk artıyor.")

    if not reasons:
        reasons.append("Belirgin pozitif teknik koşul oluşmadı.")

    return score, reasons


def calculate_subscores(latest: pd.Series) -> dict[str, int]:
    technical = 0
    if latest["EMA20"] > latest["EMA50"]:
        technical += 45
    if latest["Close"] > latest["EMA20"]:
        technical += 35
    if latest["Close"] > latest["EMA50"]:
        technical += 20

    momentum = 0
    if latest["MACD"] > 0:
        momentum += 45
    if latest["MACD"] > latest["MACD_SIGNAL"]:
        momentum += 25
    if 40 <= latest["RSI14"] <= 65:
        momentum += 30
    elif latest["RSI14"] < 30:
        momentum += 12

    volume = 45
    volume_avg = latest.get("VOLUME_AVG20", pd.NA)
    if pd.notna(volume_avg) and volume_avg > 0:
        if latest["Volume"] > volume_avg and latest["DAILY_CHANGE_PCT"] > 0:
            volume = 85
        elif latest["Volume"] > volume_avg:
            volume = 65
        elif latest["DAILY_CHANGE_PCT"] > 0:
            volume = 55

    risk = 100
    if latest["Close"] < latest["EMA50"]:
        risk -= 35
    if latest["EMA20"] < latest["EMA50"]:
        risk -= 25
    if latest["RSI14"] > 70:
        risk -= 20
    if latest["MACD"] < 0:
        risk -= 20
    if latest["RSI14"] < 30:
        risk -= 10

    return {
        "Teknik Skor": max(0, min(100, int(technical))),
        "Momentum Skor": max(0, min(100, int(momentum))),
        "Hacim Skor": max(0, min(100, int(volume))),
        "Risk Skor": max(0, min(100, int(risk))),
    }


def safe_float(value: object, default: float = 0.0) -> float:
    if pd.isna(value):
        return default
    return float(value)


def nova_confidence_index(latest: pd.Series) -> int:
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


def advanced_score_cards(latest: pd.Series, general_score: int, confidence: int) -> dict[str, int]:
    subscores = calculate_subscores(latest)
    adx = safe_float(latest.get("ADX14"))
    volatility = safe_float(latest.get("VOLATILITY20"))
    volume_ratio = safe_float(latest.get("VOLUME_RATIO"), 1.0)
    momentum = safe_float(latest.get("MOMENTUM10"))

    trend_score = 30
    if latest["EMA20"] > latest["EMA50"]:
        trend_score += 30
    if latest["Close"] > latest["EMA20"]:
        trend_score += 20
    if adx >= 25:
        trend_score += 20

    volatility_score = 70
    if volatility > 5:
        volatility_score = 35
    elif volatility > 3:
        volatility_score = 55
    elif 0 < volatility <= 2:
        volatility_score = 85

    fundamental_proxy = 50
    if volume_ratio >= 1:
        fundamental_proxy += 12
    if volatility <= 3:
        fundamental_proxy += 10
    if latest["Close"] > latest["EMA50"]:
        fundamental_proxy += 10

    momentum_score = subscores["Momentum Skor"]
    if momentum > 0:
        momentum_score = min(100, momentum_score + 10)

    return {
        "Teknik Skor": subscores["Teknik Skor"],
        "Temel Skor": clamp_percent(fundamental_proxy),
        "Momentum Skor": clamp_percent(momentum_score),
        "Trend Skor": clamp_percent(trend_score),
        "Hacim Skor": subscores["Hacim Skor"],
        "Risk Skor": subscores["Risk Skor"],
        "Volatilite Skor": clamp_percent(volatility_score),
        "Genel Nova Skoru": clamp_percent((general_score + confidence) / 2),
    }


def expected_holding_period(latest: pd.Series, selected_horizon: str) -> str:
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


def expected_return_potential(latest: pd.Series, resistance_level: float, selected_horizon: str) -> float:
    close = safe_float(latest["Close"])
    atr_pct = safe_float(latest.get("ATR_PCT"))
    volatility = safe_float(latest.get("VOLATILITY20"))
    resistance_gap = max(0.0, ((resistance_level - close) / close) * 100) if close else 0.0
    trend_bonus = 2.0 if latest["EMA20"] > latest["EMA50"] else 0.5
    horizon_multiplier = {
        "Günlük işlem": 0.8,
        "Kısa vade": 1.2,
        "Orta vade": 1.8,
        "Uzun vade": 2.5,
    }.get(selected_horizon, 1.2)
    potential = (atr_pct * horizon_multiplier) + (resistance_gap * 0.55) + trend_bonus - (volatility * 0.25)
    return round(max(1.0, min(35.0, potential)), 1)


def sell_signal_probability(latest: pd.Series, score: int, selected_horizon: str) -> int:
    probability = sell_risk_percent(score, latest, selected_horizon)
    if latest["Close"] < latest["EMA50"]:
        probability += 12
    if latest["MACD"] < 0:
        probability += 8
    if latest["RSI14"] > 70:
        probability += 10
    if safe_float(latest.get("VOLATILITY20")) > 4:
        probability += 8
    return clamp_percent(probability)


def main_decision_label(signal: str, confidence: int, sell_probability: int) -> str:
    if signal == "ALIM İÇİN İZLENEBİLİR" and confidence >= 70 and sell_probability < 45:
        return "AL"
    if sell_probability >= 70:
        return "SAT"
    if confidence >= 60:
        return "TAKİP ET"
    return "BEKLE"


def trade_quality(confidence: int, sell_probability: int) -> str:
    net = confidence - sell_probability
    if net >= 35:
        return "Yüksek"
    if net >= 10:
        return "Orta"
    return "Düşük"


def target_stop_levels(
    latest: pd.Series,
    support_level: float,
    resistance_level: float,
    expected_return: float,
) -> tuple[float, float, float, str]:
    close = safe_float(latest["Close"])
    atr = safe_float(latest.get("ATR14"))
    first_target = max(resistance_level, close * (1 + (expected_return * 0.55 / 100)))
    second_target = max(first_target + atr, close * (1 + expected_return / 100))
    stop_loss = min(support_level, safe_float(latest["EMA50"]))
    downside = max(close - stop_loss, atr, 0.01)
    upside = max(first_target - close, 0.01)
    ratio = f"1:{round(upside / downside, 2)}"
    return first_target, second_target, stop_loss, ratio


def decision_signal(score: int) -> tuple[str, str, str]:
    if score > 75:
        return "AL için izlenebilir", "Pozitif teknik yapı", "nova-signal-buy"
    if score >= 50:
        return "BEKLE / takip et", "Karışık fakat izlenebilir yapı", "nova-signal-watch"
    return "SAT / uzak dur sinyali", "Zayıf ve riskli teknik yapı", "nova-signal-sell"


def score_label(score: int) -> str:
    if score > 75:
        return "Güçlü teknik görünüm"
    if score >= 50:
        return "İzlenebilir"
    return "Zayıf / riskli görünüm"


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


def dashboard_risk_level(latest: pd.Series) -> str:
    if latest["RSI14"] > 70 or latest["Close"] < latest["EMA50"]:
        return "Yüksek"
    if latest["MACD"] < 0 or latest["EMA20"] < latest["EMA50"]:
        return "Orta"
    return "Düşük"


def clamp_percent(value: float) -> int:
    return max(0, min(100, int(round(value))))


def trade_signal(score: int, latest: pd.Series) -> str:
    if score > 75 and 40 <= latest["RSI14"] <= 65 and latest["MACD"] > 0:
        return "ALIM İÇİN İZLENEBİLİR"
    if 50 <= score <= 75 or score > 75:
        return "BEKLE"
    return "UZAK DUR / SAT RİSKİ"


def today_buy_answer(signal: str) -> str:
    if signal == "ALIM İÇİN İZLENEBİLİR":
        return "ALIM İÇİN İZLENEBİLİR"
    if signal == "BEKLE":
        return "BEKLE"
    return "RİSKLİ / UZAK DUR"


def buy_suitability_percent(score: int, latest: pd.Series, horizon: str = "Kısa vade") -> int:
    value = float(score)

    if 40 <= latest["RSI14"] <= 65:
        value += 8
    elif latest["RSI14"] > 70:
        value -= 22
    elif latest["RSI14"] < 30:
        value -= 6

    if latest["MACD"] > 0:
        value += 8
    else:
        value -= 14

    if latest["EMA20"] > latest["EMA50"]:
        value += 6
    else:
        value -= 12

    if latest["Close"] > latest["EMA20"]:
        value += 5
    if latest["Close"] < latest["EMA50"]:
        value -= 24

    if horizon == "Günlük işlem":
        value += 6 if latest["DAILY_CHANGE_PCT"] > 0 else -6
    elif horizon == "Orta vade":
        value += 4 if latest["Close"] > latest["EMA50"] else -8
    elif horizon == "Uzun vade":
        value += 8 if latest["EMA20"] > latest["EMA50"] and latest["Close"] > latest["EMA50"] else -10

    return clamp_percent(value)


def sell_risk_percent(score: int, latest: pd.Series, horizon: str = "Kısa vade") -> int:
    value = 100 - buy_suitability_percent(score, latest, horizon)

    if latest["RSI14"] > 70:
        value += 18
    if latest["Close"] < latest["EMA50"]:
        value += 28
    if latest["MACD"] < 0:
        value += 18
    if latest["EMA20"] < latest["EMA50"]:
        value += 12
    if horizon == "Günlük işlem" and latest["DAILY_CHANGE_PCT"] < 0:
        value += 8

    return clamp_percent(value)


def horizon_score(base_score: int, latest: pd.Series, horizon: str) -> int:
    value = base_score
    if horizon == "Günlük işlem":
        value += 8 if latest["DAILY_CHANGE_PCT"] > 0 else -8
        value += 5 if latest["MACD"] > latest["MACD_SIGNAL"] else -5
    elif horizon == "Orta vade":
        value += 8 if latest["Close"] > latest["EMA50"] else -10
    elif horizon == "Uzun vade":
        value += 10 if latest["EMA20"] > latest["EMA50"] and latest["Close"] > latest["EMA50"] else -12
    return clamp_percent(value)


def follow_window_visual(
    horizon: str,
    score: int,
    confidence: int,
    expected_return: float,
    sell_probability: int,
    latest: pd.Series,
) -> tuple[int, int]:
    horizon_anchor = {
        "Günlük işlem": 18,
        "Kısa vade": 34,
        "Orta vade": 52,
        "Uzun vade": 68,
    }.get(horizon, 45)
    momentum = safe_float(latest.get("MOMENTUM10"))
    volatility = safe_float(latest.get("VOLATILITY20"))
    trend_bonus = 8 if latest["EMA20"] > latest["EMA50"] and latest["Close"] > latest["EMA20"] else -6
    momentum_shift = max(-10, min(10, momentum * 1.6))
    return_shift = max(-6, min(8, (expected_return - 5) * 1.2))
    risk_shift = -max(-6, min(10, (sell_probability - 45) * 0.25))
    score_shift = max(-7, min(7, (score - 60) * 0.16))
    center = horizon_anchor + trend_bonus + momentum_shift + return_shift + risk_shift + score_shift
    uncertainty = (100 - confidence) * 0.18 + max(0, volatility - 2.5) * 4 + max(0, sell_probability - 50) * 0.16
    width = max(12, min(36, 12 + uncertainty))
    start = int(max(2, min(86, center - width / 2)))
    width = int(min(width, 96 - start))
    return start, max(10, width)


def holding_period_to_day_range(text: str) -> tuple[int, int]:
    normalized = str(text).lower()
    numbers = [int(match) for match in re.findall(r"\d+", normalized)]
    if not numbers:
        return 1, 1

    start_day = min(numbers)
    end_day = max(numbers)
    if "ay" in normalized:
        start_day *= 30
        end_day *= 30
    return max(1, start_day), max(1, end_day)


def follow_window_day_range(holding_period: str, start_pct: int, width_pct: int) -> tuple[int, int]:
    min_day, max_day = holding_period_to_day_range(holding_period)
    if max_day <= min_day:
        return min_day, max_day

    end_pct = min(100, start_pct + width_pct)
    day_span = max_day - min_day
    start_day = round(min_day + (day_span * (start_pct / 100)))
    end_day = round(min_day + (day_span * (end_pct / 100)))
    start_day = max(min_day, min(start_day, max_day))
    end_day = max(start_day, min(end_day, max_day))
    return start_day, end_day


def support_resistance(data: pd.DataFrame) -> tuple[float, float]:
    recent_data = data.tail(20)
    return float(recent_data["Low"].min()), float(recent_data["High"].max())


def signal_reason_text(latest: pd.Series, score_reasons: list[str]) -> str:
    core_reasons = []
    if latest["Close"] > latest["EMA20"] and latest["EMA20"] > latest["EMA50"]:
        core_reasons.append("fiyat EMA20 üzerinde ve EMA20, EMA50 üzerinde")
    if 40 <= latest["RSI14"] <= 65:
        core_reasons.append("RSI sağlıklı kabul edilen 40-65 aralığında")
    elif latest["RSI14"] > 70:
        core_reasons.append("RSI 70 üzerinde olduğu için aşırı alım riski var")
    elif latest["RSI14"] < 30:
        core_reasons.append("RSI 30 altında olduğu için aşırı satım ve tepki ihtimali var")
    if latest["MACD"] > 0:
        core_reasons.append("MACD pozitif")
    else:
        core_reasons.append("MACD negatif")
    if latest["Close"] < latest["EMA50"]:
        core_reasons.append("fiyat EMA50 altında olduğu için risk artıyor")

    if core_reasons:
        return "; ".join(core_reasons) + "."
    return " ".join(score_reasons)


def build_analysis(latest: pd.Series, score: int, score_reasons: list[str], signal_text: str) -> str:
    if latest["EMA20"] > latest["EMA50"]:
        trend = "Trend pozitif: EMA20, EMA50'nin üzerinde."
    elif latest["EMA20"] < latest["EMA50"]:
        trend = "Trend negatif: EMA20, EMA50'nin altında."
    else:
        trend = "Trend nötr: EMA20 ve EMA50 birbirine yakın."

    if latest["RSI14"] < 30:
        rsi_text = "RSI 30'un altında; aşırı satım ve tepki ihtimali izlenebilir."
    elif latest["RSI14"] > 70:
        rsi_text = "RSI 70'in üzerinde; aşırı alım nedeniyle dikkat gerekir."
    elif 40 <= latest["RSI14"] <= 65:
        rsi_text = "RSI 40-65 aralığında; sağlıklı bölge görünümü var."
    else:
        rsi_text = "RSI nötr bölgede; tek başına güçlü sinyal üretmiyor."

    if latest["MACD"] > 0:
        momentum = "MACD pozitif; momentum destekleyici."
    else:
        momentum = "MACD negatif; momentum zayıf."

    return (
        f"Güncel sinyal: {signal_text}\n\n"
        f"Neden? Genel skor {score}/100. {signal_reason_text(latest, score_reasons)} "
        f"{trend} {rsi_text} {momentum}\n\n"
        f"Ne zaman alınabilir? {buy_conditions_text(latest)}\n\n"
        f"Ne zaman kaçınılmalı? {sell_or_avoid_text(latest)}"
    )


def buy_conditions_text(latest: pd.Series) -> str:
    checks = [
        ("Trend pozitif", latest["EMA20"] > latest["EMA50"]),
        ("RSI aşırı alımda değil", latest["RSI14"] <= 70),
        ("MACD pozitif", latest["MACD"] > 0),
        ("Fiyat EMA20 üstünde", latest["Close"] > latest["EMA20"]),
    ]
    positive = [label for label, ok in checks if ok]
    missing = [label for label, ok in checks if not ok]

    text = (
        "AL için izlenebilir yapı, trend pozitifken, RSI aşırı alımda değilken, "
        "MACD pozitifken ve fiyat EMA20 üstündeyken güçlenir."
    )
    if positive:
        text += "\n\nSağlanan koşullar: " + ", ".join(positive) + "."
    if missing:
        text += "\n\nHenüz eksik koşullar: " + ", ".join(missing) + "."
    return text


def sell_or_avoid_text(latest: pd.Series) -> str:
    warnings = []
    if latest["EMA20"] < latest["EMA50"]:
        warnings.append("EMA20, EMA50 altına indi.")
    if latest["RSI14"] > 70:
        warnings.append("RSI 70 üzerinde; yorulma riski var.")
    if latest["MACD"] < 0:
        warnings.append("MACD negatife döndü.")
    if latest["Close"] < latest["EMA50"]:
        warnings.append("Fiyat EMA50 altına düştü.")

    text = (
        "Kaçınma veya satış yönlü temkin, EMA20 EMA50 altına indiğinde, RSI 70 üstünde "
        "yorulma gösterdiğinde, MACD negatife döndüğünde veya fiyat EMA50 altına sarktığında artar."
    )
    if warnings:
        text += "\n\nAktif uyarılar: " + " ".join(warnings)
    else:
        text += "\n\nŞu anda ana kaçınma koşulları belirgin şekilde aktif değil."
    return text


@st.cache_data(ttl=900, show_spinner=False)
def create_price_chart(
    data: pd.DataFrame,
    ticker: str,
    period_label: str,
    support_level: float,
    resistance_level: float,
    stop_loss: float | None = None,
    first_target: float | None = None,
    second_target: float | None = None,
    theme_mode: str = "dark",
) -> go.Figure:
    tokens = theme_tokens()
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.72, 0.28],
    )

    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name="Mum",
            increasing_line_color="#22c55e",
            decreasing_line_color="#ef4444",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["EMA20"],
            mode="lines",
            name="EMA20",
            line={"color": "#38bdf8", "width": 1.5},
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["EMA50"],
            mode="lines",
            name="EMA50",
            line={"color": "#f59e0b", "width": 1.5},
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=[support_level] * len(data),
            mode="lines",
            name="Destek (20G)",
            line={"color": "#22c55e", "width": 1.2, "dash": "dash"},
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=[resistance_level] * len(data),
            mode="lines",
            name="Direnç (20G)",
            line={"color": "#ef4444", "width": 1.2, "dash": "dash"},
        ),
        row=1,
        col=1,
    )
    optional_levels = [
        ("Stop", stop_loss, "#ef4444", "dot"),
        ("Hedef 1", first_target, "#22c55e", "dashdot"),
        ("Hedef 2", second_target, "#38bdf8", "dashdot"),
    ]
    for name, value, color, dash in optional_levels:
        if value is None:
            continue
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=[value] * len(data),
                mode="lines",
                name=name,
                line={"color": color, "width": 1.2, "dash": dash},
            ),
            row=1,
            col=1,
        )

    volume_colors = [
        "rgba(34, 197, 94, 0.55)" if close >= open_ else "rgba(239, 68, 68, 0.55)"
        for open_, close in zip(data["Open"], data["Close"])
    ]
    fig.add_trace(
        go.Bar(
            x=data.index,
            y=data["Volume"],
            name="Hacim",
            marker={"color": volume_colors},
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        title=f"{ticker} - {period_label} Mum Grafik ve Hacim",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        margin={"l": 20, "r": 20, "t": 70, "b": 20},
        template=tokens["plot_template"],
        height=650,
        paper_bgcolor=tokens["plot_bg"],
        plot_bgcolor=tokens["plot_bg"],
        font={"color": tokens["text"]},
        xaxis_rangeslider_visible=False,
    )
    fig.update_yaxes(title_text="Fiyat", gridcolor=tokens["grid"], row=1, col=1)
    fig.update_yaxes(title_text="Hacim", gridcolor=tokens["grid"], row=2, col=1)
    fig.update_xaxes(title_text="Tarih", gridcolor=tokens["grid"], row=2, col=1)

    return fig


@st.cache_data(ttl=900, show_spinner=False)
def create_score_gauge(score: int, theme_mode: str = "dark") -> go.Figure:
    tokens = theme_tokens()
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": "/100", "font": {"size": 34, "color": tokens["text"]}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": tokens["muted"]},
                "bar": {"color": tokens["cyan"]},
                "bgcolor": tokens["panel"],
                "borderwidth": 1,
                "bordercolor": tokens["border"],
                "steps": [
                    {"range": [0, 50], "color": "rgba(239, 68, 68, 0.35)"},
                    {"range": [50, 75], "color": "rgba(245, 158, 11, 0.35)"},
                    {"range": [75, 100], "color": "rgba(34, 197, 94, 0.35)"},
                ],
            },
        )
    )
    fig.update_layout(
        height=220,
        margin={"l": 10, "r": 10, "t": 18, "b": 4},
        paper_bgcolor=tokens["plot_bg"],
        plot_bgcolor=tokens["plot_bg"],
        font={"color": tokens["text"]},
    )
    return fig


def timeframe_score(data: pd.DataFrame, window: int) -> int:
    if len(data) < 2:
        return 0

    latest = data.iloc[-1]
    lookback_index = max(0, len(data) - window)
    lookback = data.iloc[lookback_index]
    period_change = ((latest["Close"] - lookback["Close"]) / lookback["Close"]) * 100

    score = 0
    if latest["Close"] > latest["EMA20"]:
        score += 25
    if latest["EMA20"] > latest["EMA50"]:
        score += 25
    if period_change > 0:
        score += 20
    if latest["MACD"] > 0:
        score += 20
    if 40 <= latest["RSI14"] <= 65:
        score += 10
    elif latest["RSI14"] > 70:
        score -= 10

    return max(0, min(100, int(score)))


def build_timeframe_table(data: pd.DataFrame) -> pd.DataFrame:
    latest = data.iloc[-1]
    rows = []

    for label, window in TIMEFRAME_WINDOWS.items():
        score = timeframe_score(data, window)
        signal, _, _ = decision_signal(score)
        trend = trend_text(latest)
        risk = risk_text(latest)

        if signal == "AL için izlenebilir":
            watch = "EMA20 üstü kalıcılık ve MACD pozitifliği"
            caution = "RSI 70 üstüne taşarsa veya hacim zayıflarsa"
        elif signal == "BEKLE / takip et":
            watch = "EMA20-EMA50 kesişimi ve RSI 40-65 dönüşü"
            caution = "Fiyat EMA50 altına sarkarsa"
        else:
            watch = "RSI aşırı satımdan toparlanırsa ve MACD iyileşirse"
            caution = "EMA20, EMA50 altında kalmaya devam ederse"

        rows.append(
            {
                "Vade": label,
                "Sinyal": signal,
                "Skor": score,
                "Trend": trend,
                "Risk": risk,
                "Ne zaman izlenmeli?": watch,
                "Ne zaman dikkat edilmeli?": caution,
            }
        )

    return pd.DataFrame(rows)


def trade_horizon_explanation(signal: str, latest: pd.Series) -> str:
    notes = []
    if latest["EMA20"] > latest["EMA50"]:
        notes.append("EMA20, EMA50 üzerinde; trend pozitif.")
    else:
        notes.append("EMA20, EMA50 altında; trend negatif.")

    if 40 <= latest["RSI14"] <= 65:
        notes.append("RSI sağlıklı bölgede.")
    elif latest["RSI14"] > 70:
        notes.append("RSI 70 üzerinde; alım uygunluğu düşer.")
    elif latest["RSI14"] < 30:
        notes.append("RSI 30 altında; tepki ihtimali olsa da risk izlenmeli.")

    if latest["MACD"] > 0:
        notes.append("MACD pozitif; momentum destekli.")
    else:
        notes.append("MACD negatif; sat riski artar.")

    if latest["Close"] < latest["EMA50"]:
        notes.append("Fiyat EMA50 altında; risk seviyesi yüksek.")

    return f"{signal}. " + " ".join(notes)


def build_trade_horizon_table(
    latest: pd.Series,
    base_score: int,
    confidence: int,
    support_level: float,
    resistance_level: float,
) -> pd.DataFrame:
    rows = []
    for horizon in TRADE_HORIZONS:
        score = horizon_score(base_score, latest, horizon)
        signal = trade_signal(score, latest)
        expected_return = expected_return_potential(latest, resistance_level, horizon)
        sell_probability = sell_signal_probability(latest, score, horizon)
        follow_start, follow_width = follow_window_visual(
            horizon,
            score,
            confidence,
            expected_return,
            sell_probability,
            latest,
        )
        main_decision = main_decision_label(signal, confidence, sell_probability)
        rows.append(
            {
                "Vade": horizon,
                "Sinyal": signal,
                "Nova Skoru": score,
                "Nova AI Güven Endeksi": confidence,
                "Alım Uygunluğu %": buy_suitability_percent(score, latest, horizon),
                "Sat Sinyali Yakma Riski %": sell_probability,
                "Beklenen Taşıma Süresi": expected_holding_period(latest, horizon),
                "Beklenen Getiri %": expected_return,
                "Takip Penceresi Başlangıç %": follow_start,
                "Takip Penceresi Genişlik %": follow_width,
                "Ana Karar": main_decision,
                "Trend": trend_text(latest),
                "Risk": risk_text(latest),
                "Açıklama": trade_horizon_explanation(signal, latest),
            }
        )
    return pd.DataFrame(rows)


def render_score_card(title: str, value: int) -> None:
    st.markdown(
        f"""
        <div class="nova-card">
            <div class="nova-card-title">{title}</div>
            <div class="nova-card-value">{value}/100</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_value_card(title: str, value: str, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="nova-card">
            <div class="nova-card-title">{title}</div>
            <div class="nova-card-value">{value}</div>
            <div class="nova-card-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_decision_center(
    decision: dict[str, object],
) -> None:
    st.markdown("### NOVA AI DECISION CENTER")
    st.markdown(
        f"""
        <div class="nova-signal {decision["signal_class"]}">
            <div class="nova-card-title">NOVA AI DECISION CENTER</div>
            <div class="nova-card-value">Ana Karar: {decision["main_decision"]}</div>
            <div class="nova-card-note">
                Nova AI Güven Endeksi: %{decision["confidence"]}<br>
                İşlem Kalitesi: {decision["quality"]}<br>
                İşlem Vadesi: {decision["horizon"]}<br>
                Beklenen Ortalama Taşıma Süresi: {decision["holding_period"]}<br>
                Beklenen Getiri Potansiyeli: %{decision["expected_return"]}<br>
                Sat Sinyali Oluşma Olasılığı: %{decision["sell_probability"]}<br>
                Risk / Getiri Oranı: {decision["risk_reward"]}<br>
                İlk Hedef Fiyat: {format_number(decision["first_target"])}<br>
                İkinci Hedef Fiyat: {format_number(decision["second_target"])}<br>
                Stop Loss: {format_number(decision["stop_loss"])}<br>
                Destek: {format_number(decision["support"])}<br>
                Direnç: {format_number(decision["resistance"])}
            </div>
            <div class="nova-card-note">{DISCLAIMER}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def create_radar_chart(scores: dict[str, int]) -> go.Figure:
    tokens = theme_tokens()
    labels = ["Teknik", "Temel", "Momentum", "Hacim", "Risk", "Trend", "Volatilite"]
    values = [
        scores["Teknik Skor"],
        scores["Temel Skor"],
        scores["Momentum Skor"],
        scores["Hacim Skor"],
        scores["Risk Skor"],
        scores["Trend Skor"],
        scores["Volatilite Skor"],
    ]
    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=values + [values[0]],
            theta=labels + [labels[0]],
            fill="toself",
            name="NOVA Radar",
            line={"color": tokens["cyan"], "width": 2},
            fillcolor="rgba(37, 99, 235, 0.22)",
        )
    )
    fig.update_layout(
        template=tokens["plot_template"],
        paper_bgcolor=tokens["plot_bg"],
        plot_bgcolor=tokens["plot_bg"],
        font={"color": tokens["text"]},
        height=360,
        margin={"l": 28, "r": 28, "t": 30, "b": 30},
        polar={
            "radialaxis": {"visible": True, "range": [0, 100], "gridcolor": tokens["grid"]},
            "angularaxis": {"gridcolor": tokens["grid"]},
            "bgcolor": tokens["plot_bg"],
        },
        showlegend=False,
    )
    return fig


def render_trade_horizon_cards(trade_table: pd.DataFrame) -> None:
    card_meta = {
        "Günlük işlem": "⚡ Günlük Trade",
        "Kısa vade": "📈 Kısa Vade",
        "Orta vade": "📊 Orta Vade",
        "Uzun vade": "🏦 Uzun Vade",
    }
    columns = st.columns(4)
    for column, (_, row) in zip(columns, trade_table.iterrows()):
        title = card_meta.get(row["Vade"], row["Vade"])
        window_start = int(row.get("Takip Penceresi Başlangıç %", 40))
        window_width = int(row.get("Takip Penceresi Genişlik %", 20))
        with column:
            st.markdown(
                f"""
                <div class="nova-card nova-horizon-card">
                    <div class="nova-card-title">{title}</div>
                    <div class="nova-card-note">AI Güven Endeksi: %{row["Nova AI Güven Endeksi"]}</div>
                    <div class="nova-card-note">Beklenen Getiri: %{row["Beklenen Getiri %"]}</div>
                    <div class="nova-card-note">Taşıma Süresi: {row["Beklenen Taşıma Süresi"]}</div>
                    <div class="nova-follow-label">Takip Penceresi</div>
                    <div class="nova-follow-track">
                        <div class="nova-follow-window" style="left:{window_start}%; width:{window_width}%"></div>
                    </div>
                    <div class="nova-card-note">Sat Riski: %{row["Sat Sinyali Yakma Riski %"]}</div>
                    <div class="nova-horizon-decision">{row["Ana Karar"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_pro_follow_window_detail(selected_horizon: str, selected_trade_row: pd.Series) -> None:
    if not st.session_state.get("yeb_pro_active", False):
        return

    holding_period = str(selected_trade_row["Beklenen Taşıma Süresi"])
    window_start = int(selected_trade_row.get("Takip Penceresi Başlangıç %", 40))
    window_width = int(selected_trade_row.get("Takip Penceresi Genişlik %", 20))
    start_day, end_day = follow_window_day_range(holding_period, window_start, window_width)
    if start_day == end_day:
        range_text = f"{start_day}. işlem günü"
    else:
        range_text = f"{start_day}-{end_day}. işlem günü"

    st.markdown(
        f"""
        <div class="nova-card nova-pro-follow-detail">
            <div>
                <div class="nova-card-title">YEB PRO · AI Takip Detayı</div>
                <div class="nova-card-note">
                    Seçili vade: {escape(selected_horizon)} · Beklenen taşıma süresi: {escape(holding_period)}
                </div>
            </div>
            <div class="nova-pro-follow-value">{escape(range_text)}</div>
            <div class="nova-card-note">
                AI takip penceresi, mevcut skor ve risk değerlerine göre bu vade içinde en kritik izleme bölgesini özetler.
                Net tarih veya kesin al/sat günü değildir.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_main_trade_decision_card(
    selected_horizon: str,
    signal: str,
    suitability: int,
    sell_risk: int,
    latest: pd.Series,
    support_level: float,
    resistance_level: float,
) -> None:
    signal_class = "nova-signal-buy"
    if signal == "BEKLE":
        signal_class = "nova-signal-watch"
    elif signal != "ALIM İÇİN İZLENEBİLİR":
        signal_class = "nova-signal-sell"

    st.markdown(
        f"""
        <div class="nova-signal {signal_class}">
            <div class="nova-card-title">BUGÜN İÇİN ANA KARAR</div>
            <div class="nova-card-value">Ana sinyal: {signal}</div>
            <div class="nova-card-note">
                İşlem vadesi: {selected_horizon}<br>
                Alım uygunluğu: %{suitability}<br>
                Sat sinyali yakma riski: %{sell_risk}<br>
                İzlenecek seviye: EMA20 ({format_number(latest["EMA20"])})<br>
                Stop / risk seviyesi: EMA50 ({format_number(latest["EMA50"])})<br>
                Direnç: son 20 gün zirvesi ({format_number(resistance_level)})<br>
                Destek: son 20 gün dibi ({format_number(support_level)})
            </div>
            <div class="nova-card-note">{DECISION_SUPPORT_DISCLAIMER}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_decision_text_box(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="nova-card">
            <div class="nova-card-title">{title}</div>
            <div class="nova-card-note">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_ai_summary_card(body: str) -> None:
    safe_body = escape(body).replace("\n", "<br>")
    st.markdown(
        f"""
        <div class="nova-card nova-ai-summary-card">
            <div class="nova-card-title">AI ANALİZ ÖZETİ</div>
            <div class="nova-card-note">{safe_body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_today_decision_box(
    signal_text: str,
    signal_detail: str,
    signal_class: str,
    latest: pd.Series,
    support_level: float,
    resistance_level: float,
) -> None:
    st.markdown(
        f"""
        <div class="nova-signal {signal_class}">
            <div class="nova-card-title">BUGÜN NE YAPMALI?</div>
            <div class="nova-card-value">{signal_text}</div>
            <div class="nova-card-note">{signal_detail}</div>
            <div class="nova-card-note">
                Alım için takip seviyesi: {format_number(latest["EMA20"])} (EMA20)<br>
                Risk seviyesi: {dashboard_risk_level(latest)}<br>
                Stop seviyesi: {format_number(latest["EMA50"])} (EMA50)<br>
                Destek: {format_number(support_level)} | Direnç: {format_number(resistance_level)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_number(value: float) -> str:
    return f"{value:,.2f}"


@st.cache_data(ttl=900, show_spinner=False)
def load_market_data(ticker: str, period_label: str) -> pd.DataFrame:
    try:
        raw_data = yf.download(
            ticker,
            period=PERIOD_OPTIONS[period_label],
            interval="1d",
            progress=False,
            auto_adjust=True,
            multi_level_index=False,
            threads=False,
            timeout=5,
        )
    except Exception:
        st.error(
            "Veri çekilemedi. Hisse kodunu, internet bağlantısını veya veri sağlayıcı erişimini "
            "kontrol edin."
        )
        stop_app()

    if raw_data.empty:
        st.error(
            "Veri bulunamadı. Hisse kodu hatalı olabilir, seçilen zaman aralığında veri olmayabilir "
            "veya veri sağlayıcı geçici olarak yanıt vermiyor olabilir."
        )
        stop_app()

    required_columns = {"Open", "High", "Low", "Close", "Volume"}
    if not required_columns.issubset(raw_data.columns):
        st.error("Veri eksik geldi. Mum grafik veya hacim bilgisi alınamadı. Lütfen daha sonra tekrar deneyin.")
        stop_app()

    data = calculate_indicators(raw_data).dropna()
    if data.empty:
        st.error("Teknik göstergeleri hesaplamak için yeterli veri bulunamadı. Daha uzun bir zaman aralığı seçin.")
        stop_app()

    return data


def prepare_scanner_row(ticker: str, raw_data: pd.DataFrame) -> dict[str, object] | None:
    required_columns = {"Open", "High", "Low", "Close", "Volume"}
    if raw_data.empty or not required_columns.issubset(raw_data.columns):
        return None

    data = calculate_indicators(raw_data).dropna()
    if data.empty:
        return None

    latest = data.iloc[-1]
    score, _ = calculate_general_score(latest)
    signal, _, _ = decision_signal(score)
    scanner_signal = trade_signal(score, latest)

    return {
        "Hisse": ticker,
        "Nova Skoru": score,
        "Sinyal": scanner_signal,
        "Alım Uygunluğu %": buy_suitability_percent(score, latest),
        "Sat Sinyali Yakma Riski %": sell_risk_percent(score, latest),
        "Trend": trend_text(latest),
        "RSI": round(float(latest["RSI14"]), 2),
        "Son Fiyat": round(float(latest["Close"]), 2),
        "Günlük %": round(float(latest["DAILY_CHANGE_PCT"]), 2),
        "Risk": risk_text(latest),
        "EMA20": round(float(latest["EMA20"]), 2),
        "EMA50": round(float(latest["EMA50"]), 2),
        "MACD": round(float(latest["MACD"]), 4),
    }


@st.cache_data(ttl=900, show_spinner=False)
def scan_bist_market(tickers: tuple[str, ...]) -> tuple[pd.DataFrame, list[str]]:
    rows = []
    failed_tickers = []

    for ticker in tickers:
        try:
            raw_data = yf.download(
                ticker,
                period="6mo",
                interval="1d",
                progress=False,
                auto_adjust=True,
                multi_level_index=False,
                threads=False,
                timeout=5,
            )
            row = prepare_scanner_row(ticker, raw_data)
        except Exception:
            row = None

        if row is None:
            failed_tickers.append(ticker)
        else:
            rows.append(row)

    table = pd.DataFrame(rows)
    if not table.empty:
        table = table.sort_values("Nova Skoru", ascending=False).reset_index(drop=True)

    return table, failed_tickers


def render_top_stock_card(row: pd.Series) -> None:
    st.markdown(
        f"""
        <div class="nova-card">
            <div class="nova-card-title">{row["Hisse"]}</div>
            <div class="nova-card-value">{int(row["Nova Skoru"])}/100</div>
            <div class="nova-card-note">Sinyal: {row["Sinyal"]}</div>
            <div class="nova-card-note">Risk: {row["Risk"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def scan_badge_class(value: object) -> str:
    if isinstance(value, (int, float)):
        if value <= 35:
            return "positive"
        if value >= 65:
            return "negative"
        return "neutral"

    normalized = str(value).strip().lower()
    if any(token in normalized for token in ["pozitif", "al", "güçlü", "düşük", "low"]):
        return "positive"
    if any(token in normalized for token in ["negatif", "sat", "yüksek", "high"]):
        return "negative"
    try:
        numeric_value = float(normalized.replace("%", "").replace(",", "."))
    except ValueError:
        numeric_value = None
    if numeric_value is not None:
        if numeric_value <= 35:
            return "positive"
        if numeric_value >= 65:
            return "negative"
    return "neutral"


def render_badge(value: object) -> str:
    text = escape(str(value))
    return f'<span class="nova-scan-badge {scan_badge_class(value)}">{text}</span>'


def render_percent_impact_badge(value: object) -> str:
    numeric_value = safe_float(value)
    if numeric_value > 0:
        badge_class = "positive"
        text = f"+%{format_number(numeric_value)}"
    elif numeric_value < 0:
        badge_class = "negative"
        text = f"-%{format_number(abs(numeric_value))}"
    else:
        badge_class = "neutral"
        text = "%0.0"
    return f'<span class="nova-scan-badge {badge_class}">{escape(text)}</span>'


def render_nova_bist_table(table: pd.DataFrame, columns: list[str]) -> None:
    sortable_columns = {"AI Güven Endeksi", "Beklenen Getiri %", "Haber Etkisi %", "Haber Dahil Getiri %"}
    header_cells = []
    for index, column in enumerate(columns):
        if column in sortable_columns:
            header_cells.append(
                f'<th class="nova-sortable" data-sortable="true" data-sort-index="{index}" '
                f'data-column="{escape(column)}" title="Çift tıkla sırala">{escape(column)} <span class="nova-sort-mark">⇅</span></th>'
            )
        else:
            header_cells.append(f"<th>{escape(column)}</th>")
    header = "".join(header_cells)
    rows = []
    for _, row in table[columns].iterrows():
        cells = []
        for column in columns:
            value = row[column]
            if column == "Nova Skoru":
                cells.append(f'<td><span class="nova-score-strong">{int(value)}/100</span></td>')
            elif column == "Haber Etkisi %":
                cells.append(f"<td>{render_percent_impact_badge(value)}</td>")
            elif column in {"Trend", "Sinyal", "Risk"}:
                cells.append(f"<td>{render_badge(value)}</td>")
            elif column in {"RSI", "Son Fiyat", "Günlük %", "Beklenen Getiri %", "Haber Dahil Getiri %"}:
                cells.append(f"<td>{escape(format_number(float(value)))}</td>")
            else:
                cells.append(f"<td>{escape(str(value))}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")

    table_height = min(900, max(220, 92 + (len(rows) * 58)))
    components.html(
        f"""
        <style>
            :root {{
                color-scheme: dark;
            }}
            body {{
                margin: 0;
                background: transparent;
                font-family: "Inter", "Segoe UI", sans-serif;
            }}
            .nova-scan-table-wrap {{
                width: 100%;
                overflow-x: auto;
                border: 1px solid var(--nova-border, rgba(148, 163, 184, 0.20));
                border-radius: var(--nova-radius, 8px);
                background: var(--nova-card-bg, #07111f);
                box-shadow: var(--nova-shadow, 0 18px 42px rgba(2, 6, 23, 0.24));
            }}
            .nova-scan-table {{
                width: 100%;
                border-collapse: collapse;
                min-width: 920px;
                color: var(--nova-text, #e5eefc);
            }}
            .nova-scan-table thead tr {{
                background: rgba(15, 23, 42, 0.92);
            }}
            .nova-scan-table th {{
                padding: 13px 14px;
                color: var(--nova-muted, #93a4bc);
                font-size: 0.74rem;
                line-height: 1.25;
                text-align: left;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                border-bottom: 1px solid var(--nova-border, rgba(148, 163, 184, 0.20));
                white-space: nowrap;
                user-select: none;
            }}
            .nova-scan-table th.nova-sortable {{
                cursor: ns-resize;
            }}
            .nova-scan-table th.nova-sortable:hover,
            .nova-scan-table th.nova-sortable.active {{
                color: var(--nova-text, #e5eefc);
                background: rgba(56, 189, 248, 0.08);
            }}
            .nova-sort-mark {{
                color: var(--nova-cyan, #38bdf8);
                font-size: 0.72rem;
                margin-left: 6px;
                opacity: 0.86;
            }}
            .nova-scan-table td {{
                padding: 14px;
                color: var(--nova-text, #e5eefc);
                font-size: 0.9rem;
                line-height: 1.35;
                border-bottom: 1px solid rgba(148, 163, 184, 0.14);
                vertical-align: middle;
                white-space: nowrap;
            }}
            .nova-scan-table tbody tr {{
                background: rgba(15, 23, 42, 0.34);
                transition: background 160ms ease, transform 160ms ease;
            }}
            .nova-scan-table tbody tr:nth-child(even) {{
                background: rgba(15, 23, 42, 0.20);
            }}
            .nova-scan-table tbody tr:hover {{
                background: rgba(56, 189, 248, 0.11);
            }}
            .nova-score-strong {{
                display: inline-block;
                color: var(--nova-text, #e5eefc);
                font-size: 1.12rem;
                font-weight: 840;
                line-height: 1;
            }}
            .nova-scan-badge {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 76px;
                border-radius: 999px;
                padding: 5px 10px;
                font-size: 0.76rem;
                font-weight: 760;
                line-height: 1;
                border: 1px solid transparent;
            }}
            .nova-scan-badge.positive {{
                color: #bbf7d0;
                background: rgba(34, 197, 94, 0.16);
                border-color: rgba(34, 197, 94, 0.42);
            }}
            .nova-scan-badge.neutral {{
                color: #fde68a;
                background: rgba(245, 158, 11, 0.15);
                border-color: rgba(245, 158, 11, 0.42);
            }}
            .nova-scan-badge.negative {{
                color: #fecaca;
                background: rgba(239, 68, 68, 0.15);
                border-color: rgba(239, 68, 68, 0.40);
            }}
            @media (max-width: 700px) {{
                .nova-scan-table th,
                .nova-scan-table td {{
                    padding: 11px 12px;
                }}
            }}
        </style>
        <div class="nova-scan-table-wrap">
            <table class="nova-scan-table">
                <thead><tr>{header}</tr></thead>
                <tbody>{''.join(rows)}</tbody>
            </table>
        </div>
        <script>
            (() => {{
                const table = document.querySelector(".nova-scan-table");
                if (!table) return;
                const tbody = table.querySelector("tbody");
                const directions = {{}};
                const numericValue = (row, index) => {{
                    const text = row.children[index]?.innerText || "";
                    const normalized = text.replace(",", ".");
                    const match = normalized.match(/-?\\d+(\\.\\d+)?/);
                    return match ? Number.parseFloat(match[0]) : 0;
                }};
                table.querySelectorAll("th[data-sortable='true']").forEach((header) => {{
                    header.addEventListener("dblclick", () => {{
                        const index = Number.parseInt(header.dataset.sortIndex, 10);
                        const column = header.dataset.column;
                        const direction = directions[column] === "desc" ? "asc" : "desc";
                        directions[column] = direction;
                        const rows = Array.from(tbody.querySelectorAll("tr"));
                        rows.sort((left, right) => {{
                            const leftValue = numericValue(left, index);
                            const rightValue = numericValue(right, index);
                            return direction === "desc" ? rightValue - leftValue : leftValue - rightValue;
                        }});
                        rows.forEach((row) => tbody.appendChild(row));
                        table.querySelectorAll("th[data-sortable='true']").forEach((item) => {{
                            item.classList.remove("active");
                            const mark = item.querySelector(".nova-sort-mark");
                            if (mark) mark.textContent = "⇅";
                        }});
                        header.classList.add("active");
                        const mark = header.querySelector(".nova-sort-mark");
                        if (mark) mark.textContent = direction === "desc" ? "↓" : "↑";
                    }});
                }});
            }})();
        </script>
        """,
        height=table_height,
        scrolling=True,
    )


def render_scanner_disclosure() -> None:
    st.markdown("### Bilgilendirme")
    info_col_1, info_col_2 = st.columns(2)
    with info_col_1:
        st.markdown(
            """
            <div class="nova-card nova-info-card">
                <div class="nova-card-title">Veri Kaynağı</div>
                <div class="nova-card-note">Bu sürümde BIST hisse listesi yerel CSV dosyasından okunur.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with info_col_2:
        st.markdown(
            f"""
            <div class="nova-card nova-info-card">
                <div class="nova-card-title">Yasal Bilgilendirme</div>
                <div class="nova-card-note">{DISCLAIMER}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_smart_summary_cards(scanner_table: pd.DataFrame, scanned_count: int, scan_time: str) -> None:
    highest_score = int(scanner_table["Nova Score"].max()) if not scanner_table.empty else 0
    average_score = round(float(scanner_table["Nova Score"].mean()), 1) if not scanner_table.empty else 0

    col_1, col_2, col_3, col_4 = st.columns(4)
    with col_1:
        render_value_card("Taranan Hisse Sayısı", str(scanned_count))
    with col_2:
        render_value_card("Son Tarama Zamanı", scan_time)
    with col_3:
        render_value_card("En Yüksek Nova Skoru", f"{highest_score}/100")
    with col_4:
        render_value_card("Ortalama Nova Skoru", f"{average_score}/100")


def run_smart_market_scan(
    symbol_rows: tuple[tuple[str, str], ...],
    selected_horizon: str,
    max_seconds: int = 60,
) -> tuple[pd.DataFrame, list[str], bool, int]:
    try:
        return nova_scanner.scan_smart_market(
            symbol_rows,
            selected_horizon=selected_horizon,
            max_seconds=max_seconds,
        )
    except TypeError:
        table, failed_tickers, timed_out, scanned_count = nova_scanner.scan_smart_market(
            symbol_rows,
            max_seconds=max_seconds,
        )
        if not table.empty and "Beklenen Taşıma Süresi" in table.columns:
            table = table.copy()
            table["Beklenen Taşıma Süresi"] = nova_analytics.expected_holding_period(
                pd.Series(dtype="float64"),
                selected_horizon,
        )
        return table, failed_tickers, timed_out, scanned_count


def normalize_smart_scanner_table(table: pd.DataFrame | None) -> pd.DataFrame:
    if table is None:
        return pd.DataFrame()
    if table.empty:
        return table
    normalized = table.copy()
    if "Haber Etkisi %" not in normalized.columns:
        normalized["Haber Etkisi %"] = 0.0
    if "Haber Dahil Getiri %" not in normalized.columns:
        if "Beklenen Getiri %" in normalized.columns:
            normalized["Haber Dahil Getiri %"] = normalized["Beklenen Getiri %"]
        else:
            normalized["Haber Dahil Getiri %"] = 0.0
    return normalized


def render_top_50_scroller(table: pd.DataFrame) -> None:
    top_rows = list(table.head(50).iterrows())
    for offset in range(0, len(top_rows), 5):
        columns = st.columns(5)
        for column, (idx, row) in zip(columns, top_rows[offset : offset + 5]):
            rank = int(row.get("Sıra", idx + 1))
            with column:
                with st.container(border=True):
                    st.caption(f"#{rank} | {row['Sonuç']}")
                    st.markdown(f"**{row['Hisse']}**")
                    st.caption(str(row["Şirket"]))
                    st.metric("Nova Skoru", f"{int(row['Nova Score'])}/100")
                    st.caption(f"AI Güven: %{row['AI Güven Endeksi']}")
                    st.caption(f"Risk: %{row['Sat Riski %']}")


def render_market_scanner_page() -> None:
    st.title("Piyasa Tarayıcı")
    st.markdown(
        '<div class="nova-subtitle">Nova BIST hisselerini tarar ve teknik skora göre fırsat listesini oluşturur.</div>',
        unsafe_allow_html=True,
    )
    bist_symbols = get_bist_symbols_or_stop()

    st.markdown("### Taranacak Hisseler")
    scanner_query = st.text_input("Hisse ara", placeholder="Örn: Türk Hava, ASELS", key="scanner_symbol_search")
    filtered_symbols = filter_symbols(bist_symbols, scanner_query)
    if filtered_symbols.empty:
        st.warning("Aramanızla eşleşen BIST hissesi bulunamadı.")
        filtered_symbols = bist_symbols

    scanner_options = filtered_symbols["symbol"].tolist()
    default_symbols = bist_symbols["symbol"].head(50).tolist()
    default_selection = [symbol for symbol in default_symbols if symbol in scanner_options]
    if not default_selection and scanner_options:
        default_selection = scanner_options[:50]
    scanner_symbol_labels = build_symbol_labels(bist_symbols)

    picker_col, action_col = st.columns([3.4, 0.95])
    with picker_col:
        selected_symbols = st.multiselect(
            "Taranacak hisseler",
            scanner_options,
            default=default_selection,
            format_func=lambda symbol: scanner_symbol_labels.get(symbol, symbol),
        )
    with action_col:
        st.markdown('<div class="nova-button-spacer"></div>', unsafe_allow_html=True)
        scan_requested = st.button("Seçili Hisseleri Tara", type="primary")
    if scan_requested:
        st.session_state.scanner_selected_symbols = selected_symbols

    if "scanner_selected_symbols" not in st.session_state:
        st.session_state.scanner_selected_symbols = default_symbols

    symbols_to_scan = st.session_state.scanner_selected_symbols
    if not symbols_to_scan:
        st.info("Tarama için en az bir hisse seçin.")
        return

    with st.spinner("BIST hisseleri taranıyor..."):
        scanner_table, failed_tickers = scan_bist_market(tuple(symbols_to_scan))
    st.session_state.scanner_scan_time = current_timestamp_label()

    if scanner_table.empty:
        st.error("Piyasa taraması için veri alınamadı. Lütfen bağlantıyı kontrol edip tekrar deneyin.")
        return

    st.caption(f"Tarama zamanı: {st.session_state.scanner_scan_time}")

    st.markdown("### 🔥 Bugünün En Güçlü 5 Hissesi")
    top_rows = scanner_table.head(5)
    top_columns = st.columns(5)
    for column, (_, row) in zip(top_columns, top_rows.iterrows()):
        with column:
            render_top_stock_card(row)

    st.markdown("### Nova BIST Tarama Tablosu")
    visible_columns = [
        "Hisse",
        "Nova Skoru",
        "Sinyal",
        "Alım Uygunluğu %",
        "Sat Sinyali Yakma Riski %",
        "Trend",
        "RSI",
        "Son Fiyat",
        "Günlük %",
        "Risk",
    ]
    render_nova_bist_table(scanner_table, visible_columns)

    if failed_tickers:
        st.warning("Veri alınamayan hisseler: " + ", ".join(failed_tickers))

    render_scanner_disclosure()


def render_smart_scanner_page() -> None:
    st.title("🔥 Smart Scanner")
    st.markdown(
        '<div class="nova-subtitle">BIST hisselerini Nova AI karar motoru ile filtreler ve fırsat listesini oluşturur.</div>',
        unsafe_allow_html=True,
    )
    if st.session_state.get("smart_scanner_calc_version") != SMART_SCANNER_CALC_VERSION:
        for key in (
            "smart_scanner_results",
            "smart_scanner_failed_tickers",
            "smart_scanner_scanned_count",
            "smart_scanner_scan_time",
            "smart_scanner_selected_horizon",
        ):
            st.session_state.pop(key, None)
        st.session_state.smart_scanner_calc_version = SMART_SCANNER_CALC_VERSION

    bist_symbols = get_bist_symbols_or_stop()

    symbol_rows_df = bist_symbols[["symbol", "name"]]
    symbol_rows = tuple(symbol_rows_df.itertuples(index=False, name=None))

    scan_mode = st.radio(
        "Tarama modu",
        list(SMART_SCAN_MODES.keys()),
        horizontal=True,
        key="smart_scan_mode",
    )
    scan_limit = SMART_SCAN_MODES[scan_mode]
    target_symbol_rows = symbol_rows[:scan_limit] if scan_limit is not None else symbol_rows
    target_count = len(target_symbol_rows)
    selected_scan_horizon = st.radio(
        "İşlem Vadesi",
        SMART_SCANNER_HORIZONS,
        horizontal=True,
        key="smart_scan_horizon",
    )

    scan_requested = st.button("Piyasayı Yeniden Tara", type="primary")
    if scan_requested:
        with st.spinner("Smart Scanner CSV listesindeki tüm BIST hisselerini tarıyor..."):
            scanner_table, failed_tickers, timed_out, scanned_count = run_smart_market_scan(
                target_symbol_rows,
                selected_scan_horizon,
                max_seconds=60,
            )
        scanner_table = normalize_smart_scanner_table(scanner_table)
        st.caption(f"{scanned_count} / {target_count} hisse tarandı")
        if timed_out:
            st.warning("Tarama süresi uzadı. İlk sonuçlar gösteriliyor.")
        if scanner_table.empty:
            st.error("Smart Scanner için veri alınamadı. Önceki sonuç varsa korunur.")
        else:
            st.session_state.smart_scanner_results = scanner_table
            st.session_state.smart_scanner_failed_tickers = failed_tickers
            st.session_state.smart_scanner_scanned_count = scanned_count
            st.session_state.smart_scanner_scan_time = current_timestamp_label()
            st.session_state.smart_scanner_selected_horizon = selected_scan_horizon
            st.session_state.smart_scanner_calc_version = SMART_SCANNER_CALC_VERSION

    scanner_table = normalize_smart_scanner_table(st.session_state.get("smart_scanner_results", pd.DataFrame()))
    failed_tickers = st.session_state.get("smart_scanner_failed_tickers", [])
    scanned_count = st.session_state.get("smart_scanner_scanned_count", len(symbol_rows))
    scan_time = st.session_state.get("smart_scanner_scan_time", "-")

    if scanner_table is None or scanner_table.empty:
        st.info("Henüz tarama yapılmadı. Piyasayı taramak için butona basın.")
        render_scanner_disclosure()
        return

    render_smart_summary_cards(scanner_table, scanned_count, scan_time)

    trend_filter = st.session_state.get("smart_filter_trend", "Tümü")
    momentum_filter = st.session_state.get("smart_filter_momentum", "Tümü")
    min_score = st.session_state.get("smart_filter_min_score", 0)
    min_confidence = st.session_state.get("smart_filter_min_confidence", 0)
    ema_filter = st.session_state.get("smart_filter_ema", False)
    macd_filter = st.session_state.get("smart_filter_macd", "Tümü")
    rsi_range = st.session_state.get("smart_filter_rsi", (0, 100))
    min_volume_ratio = st.session_state.get("smart_filter_volume", 0.0)
    max_volatility = st.session_state.get("smart_filter_volatility", 15.0)
    filtered_table = nova_scanner.apply_filters(
        scanner_table,
        trend_filter,
        momentum_filter,
        min_score,
        min_confidence,
        ema_filter,
        macd_filter,
        rsi_range,
        min_volume_ratio,
        max_volatility,
    )

    st.markdown("### 🔥 Bugünün En Güçlü 10 Hissesi")
    top_rows = filtered_table.head(10)
    if top_rows.empty:
        st.info("Filtrelere uyan hisse bulunamadı.")
    else:
        top_scan_table = top_rows.rename(columns={"Nova Score": "Nova Skoru", "Sonuç": "Sinyal"})
        render_nova_bist_table(top_scan_table, [
            "Hisse",
            "Nova Skoru",
            "Sinyal",
            "AI Güven Endeksi",
            "Beklenen Getiri %",
            "Haber Etkisi %",
            "Haber Dahil Getiri %",
            "Beklenen Taşıma Süresi",
            "Trend",
        ])

    st.markdown("### Nova BIST Tarama Tablosu")
    smart_table = filtered_table.rename(columns={"Nova Score": "Nova Skoru", "Sonuç": "Sinyal", "Sat Riski %": "Risk"})
    smart_visible_columns = [
        "Hisse",
        "Nova Skoru",
        "Sinyal",
        "AI Güven Endeksi",
        "Beklenen Getiri %",
        "Haber Etkisi %",
        "Haber Dahil Getiri %",
        "Beklenen Taşıma Süresi",
        "Alım Uygunluğu %",
        "Risk",
        "Trend",
    ]
    if smart_table.empty:
        st.info("Filtrelere uyan hisse bulunamadı.")
    else:
        render_nova_bist_table(smart_table, smart_visible_columns)

    with st.expander("🎛 Gelişmiş Filtreler", expanded=False):
        filter_col_1, filter_col_2, filter_col_3, filter_col_4 = st.columns(4)
        with filter_col_1:
            st.selectbox("Trend", ["Tümü", "Pozitif", "Nötr", "Negatif"], key="smart_filter_trend")
            st.slider("Min Nova Score", 0, 100, 0, key="smart_filter_min_score")
        with filter_col_2:
            st.selectbox("Momentum", ["Tümü", "Pozitif", "Negatif"], key="smart_filter_momentum")
            st.slider("Min AI Güven", 0, 100, 0, key="smart_filter_min_confidence")
        with filter_col_3:
            st.checkbox("EMA20 > EMA50", value=False, key="smart_filter_ema")
            st.selectbox("MACD", ["Tümü", "Pozitif", "Negatif"], key="smart_filter_macd")
        with filter_col_4:
            st.slider("RSI Aralığı", 0, 100, (0, 100), key="smart_filter_rsi")
            st.slider("Min Hacim Oranı", 0.0, 3.0, 0.0, 0.1, key="smart_filter_volume")
            st.slider("Maks Volatilite", 0.0, 15.0, 15.0, 0.5, key="smart_filter_volatility")

    if failed_tickers:
        st.caption("Veri alınamayan ve atlanan hisseler: " + ", ".join(failed_tickers))

    render_scanner_disclosure()


def render_dashboard_page() -> None:
    st.title("NOVA AI")
    st.markdown('<div class="nova-subtitle">Analyze Smarter. Decide Better.</div>', unsafe_allow_html=True)
    dashboard_theme_mode = st.session_state.get("theme_mode", "dark")
    bist_symbols = get_bist_symbols_or_stop()

    if "quick_ticker" not in st.session_state:
        st.session_state.quick_ticker = bist_symbols.iloc[0]["symbol"]
    if "manual_ticker" not in st.session_state:
        st.session_state.manual_ticker = st.session_state.quick_ticker

    period_label = DEFAULT_PERIOD_LABEL
    search_col, control_col_1, control_col_2 = st.columns([1.1, 1.35, 1])

    with search_col:
        dashboard_query = st.text_input("Hisse ara", placeholder="Örn: Türk Hava, ASELS")

    filtered_symbols = filter_symbols(bist_symbols, dashboard_query)
    if filtered_symbols.empty:
        st.warning("Aramanızla eşleşen BIST hissesi bulunamadı.")
        filtered_symbols = bist_symbols

    quick_options = filtered_symbols["symbol"].tolist()
    if st.session_state.quick_ticker not in quick_options:
        st.session_state.quick_ticker = quick_options[0]
    dashboard_symbol_labels = build_symbol_labels(bist_symbols)

    with control_col_1:
        st.selectbox(
            "CSV hızlı seçim",
            quick_options,
            key="quick_ticker",
            on_change=sync_manual_ticker,
            format_func=lambda symbol: dashboard_symbol_labels.get(symbol, symbol),
        )

    with control_col_2:
        ticker = st.text_input("Manuel hisse kodu", key="manual_ticker").strip().upper()

    if not ticker:
        st.info("Analiz için bir hisse kodu girin.")
        stop_app()

    data = load_market_data(ticker, period_label)
    st.caption(f"Analiz zamanı: {current_timestamp_label()}")
    latest = data.iloc[-1]
    general_score, score_reasons = calculate_general_score(latest)
    signal_text, signal_detail, signal_class = decision_signal(general_score)
    support_level, resistance_level = support_resistance(data)
    confidence = nova_confidence_index(latest)
    trade_table = build_trade_horizon_table(latest, general_score, confidence, support_level, resistance_level)

    st.markdown("### İşlem Vadeleri")
    render_trade_horizon_cards(trade_table)

    selected_horizon = st.radio(
        "Bu analizi hangi işlem vadesine göre kullanacaksın?",
        TRADE_HORIZONS,
        horizontal=True,
    )

    selected_trade_row = trade_table[trade_table["Vade"] == selected_horizon].iloc[0]
    render_pro_follow_window_detail(selected_horizon, selected_trade_row)
    selected_signal = str(selected_trade_row["Sinyal"])
    selected_score = int(selected_trade_row["Nova Skoru"])
    selected_expected_return = float(selected_trade_row["Beklenen Getiri %"])
    selected_sell_probability = int(selected_trade_row["Sat Sinyali Yakma Riski %"])
    first_target, second_target, stop_loss, risk_reward = target_stop_levels(
        latest,
        support_level,
        resistance_level,
        selected_expected_return,
    )
    main_decision = main_decision_label(selected_signal, confidence, selected_sell_probability)
    decision_class = "nova-signal-buy"
    if main_decision in {"BEKLE", "TAKİP ET"}:
        decision_class = "nova-signal-watch"
    elif main_decision == "SAT":
        decision_class = "nova-signal-sell"

    decision_payload = {
        "signal_class": decision_class,
        "main_decision": main_decision,
        "confidence": confidence,
        "quality": trade_quality(confidence, selected_sell_probability),
        "horizon": selected_horizon,
        "holding_period": selected_trade_row["Beklenen Taşıma Süresi"],
        "expected_return": selected_expected_return,
        "sell_probability": selected_sell_probability,
        "risk_reward": risk_reward,
        "first_target": first_target,
        "second_target": second_target,
        "stop_loss": stop_loss,
        "support": support_level,
        "resistance": resistance_level,
    }
    radar_scores_v12 = nova_analytics.score_breakdown(latest, general_score, confidence)
    nova_decision.render_premium_decision_center(
        decision_payload,
        radar_scores_v12,
        show_diagnostics=False,
    )

    st.markdown("### KPI Kartları")
    kpi_col_1, kpi_col_2, kpi_col_3, kpi_col_4 = st.columns(4)
    with kpi_col_1:
        render_value_card("Nova Score", f"{selected_score}/100")
    with kpi_col_2:
        render_value_card("AI Güven", f"%{confidence}")
    with kpi_col_3:
        render_value_card("Beklenen Getiri", f"%{selected_expected_return}")
    with kpi_col_4:
        render_value_card("Beklenen Taşıma Süresi", str(selected_trade_row["Beklenen Taşıma Süresi"]))

    st.markdown("### Gauge + Teknik Barlar")
    gauge_col, bars_col = st.columns([0.75, 1.65])
    with gauge_col:
        st.plotly_chart(create_score_gauge(general_score, dashboard_theme_mode), use_container_width=True)
    with bars_col:
        nova_decision.render_progress_bars(radar_scores_v12)

    st.markdown("### AI Analiz Özeti")
    decision_col, analysis_col = st.columns([0.85, 1.25])
    with decision_col:
        render_today_decision_box(
            signal_text,
            signal_detail,
            signal_class,
            latest,
            support_level,
            resistance_level,
        )
    with analysis_col:
        render_ai_summary_card(build_analysis(latest, general_score, score_reasons, signal_text))

    st.markdown("### Fiyat Grafiği")
    st.plotly_chart(
        create_price_chart(
            data,
            ticker,
            period_label,
            support_level,
            resistance_level,
            stop_loss,
            first_target,
            second_target,
            dashboard_theme_mode,
        ),
        use_container_width=True,
    )

    st.markdown("### Bilgilendirme")
    info_col_1, info_col_2 = st.columns(2)
    with info_col_1:
        st.markdown(
            """
            <div class="nova-card nova-info-card">
                <div class="nova-card-title">Veri Kaynağı</div>
                <div class="nova-card-note">Bu sürümde BIST hisse listesi yerel CSV dosyasından okunur.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with info_col_2:
        st.markdown(
            f"""
            <div class="nova-card nova-info-card">
                <div class="nova-card-title">Yasal Bilgilendirme</div>
                <div class="nova-card-note">{DISCLAIMER}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_coming_soon_page(page: str) -> None:
    icon, title = page.split(" ", 1)
    st.markdown(
        f"""
        <div class="nova-coming-soon">
            <div class="nova-coming-inner">
                <div class="nova-coming-icon">{icon}</div>
                <div class="nova-coming-title">{title}</div>
                <div class="nova-coming-text">
                    Yakında...<br>
                    Bu modül geliştiriliyor.<br>
                    Nova v1.0 sürümünde aktif olacak.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_login_page() -> bool:
    st.title("Smart Scanner Girişi")
    st.markdown(
        '<div class="nova-subtitle">Smart Scanner ücretsiz üyelik ile kullanılabilir.</div>',
        unsafe_allow_html=True,
    )
    with st.form("smart_scanner_login_form"):
        username = st.text_input("Kullanıcı Adı", key="login_username")
        password = st.text_input("Şifre", type="password", key="login_password")
        submitted = st.form_submit_button("Giriş Yap")

    if not submitted:
        return False

    username_value = str(st.session_state.get("login_username", username)).strip()
    password_value = str(st.session_state.get("login_password", password)).strip()
    user = user_store.authenticate(username_value, password_value)
    if not user:
        normalized_username = user_store.normalize_username(username_value)
        known_user = user_store.USERS.get(normalized_username)
        if known_user and password_value == known_user["password"]:
            user = {"username": normalized_username, "is_pro": bool(known_user.get("is_pro", False))}
    if user:
        st.session_state.is_authenticated = True
        st.session_state.auth_user = user["username"]
        st.session_state.yeb_pro_active = bool(user["is_pro"])
        st.session_state.yeb_data_user = ""
        load_current_user_pro_data()
        st.success("Giriş başarılı.")
        st.rerun()
        return True

    st.error("Kullanıcı adı veya şifre hatalı.")
    return False


def render_pro_locked_page() -> None:
    st.title("YEB PRO")
    st.markdown(
        """
        <div class="nova-coming-soon">
            <div class="nova-coming-inner">
                <div class="nova-coming-icon">⭐</div>
                <div class="nova-coming-title">Bu bölüm YEB Pro üyelerine özeldir.</div>
                <div class="nova-coming-text">Pro modülleri aktif üyelik gerektirir.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Pro erişimi için size verilen kullanıcı adı ve şifre ile giriş yapın.")
    st.button("Pro'ya Geç", type="primary")


def holding_period_to_days(text: str) -> int:
    return holding_period_to_day_range(text)[1]


def build_buy_snapshot(symbol: str, quantity: int) -> dict[str, object]:
    data = load_market_data(symbol, DEFAULT_PERIOD_LABEL)
    latest = data.iloc[-1]
    score, _ = calculate_general_score(latest)
    confidence = nova_confidence_index(latest)
    support_level, resistance_level = support_resistance(data)
    selected_horizon = "Kısa vade"
    expected_return = expected_return_potential(latest, resistance_level, selected_horizon)
    holding_period = expected_holding_period(latest, selected_horizon)
    sell_probability = sell_signal_probability(latest, score, selected_horizon)
    first_target, second_target, stop_loss, risk_reward = target_stop_levels(
        latest,
        support_level,
        resistance_level,
        expected_return,
    )
    now = now_istanbul()
    return {
        "id": f"{symbol}-{now.strftime('%Y%m%d%H%M%S')}",
        "Hisse": symbol,
        "Alış Tarihi": now.date().isoformat(),
        "Alış Saati": now.strftime("%H:%M:%S"),
        "Alış Fiyatı": round(float(latest["Close"]), 2),
        "Lot / Adet": int(quantity),
        "Nova Skoru": int(score),
        "AI Güven": int(confidence),
        "Beklenen Getiri": float(expected_return),
        "Beklenen Taşıma Süresi": holding_period,
        "Taşıma Gün Hedefi": holding_period_to_days(holding_period),
        "Stop Loss": round(float(stop_loss), 2),
        "Hedef 1": round(float(first_target), 2),
        "Hedef 2": round(float(second_target), 2),
        "Sat Riski": int(sell_probability),
        "Risk/Getiri": risk_reward,
        "Analiz Zamanı": now.strftime("%Y-%m-%d %H:%M:%S"),
    }


def position_tracking_row(position: dict[str, object]) -> tuple[dict[str, object], list[str]]:
    symbol = str(position["Hisse"])
    data = load_market_data(symbol, DEFAULT_PERIOD_LABEL)
    latest = data.iloc[-1]
    current_price = round(float(latest["Close"]), 2)
    buy_price = float(position["Alış Fiyatı"])
    stop_loss = float(position["Stop Loss"])
    target_1 = float(position["Hedef 1"])
    target_2 = float(position["Hedef 2"])
    buy_date = datetime.fromisoformat(str(position["Alış Tarihi"]))
    held_days = max(0, (now_istanbul().date() - buy_date.date()).days)
    total_days = int(position.get("Taşıma Gün Hedefi", 1))
    remaining_days = max(0, total_days - held_days)
    pnl_pct = round(((current_price - buy_price) / buy_price) * 100, 2) if buy_price else 0.0
    stop_distance = round(((current_price - stop_loss) / current_price) * 100, 2) if current_price else 0.0
    target_1_distance = round(((target_1 - current_price) / current_price) * 100, 2) if current_price else 0.0
    target_2_distance = round(((target_2 - current_price) / current_price) * 100, 2) if current_price else 0.0
    target_1_progress = round(((current_price - buy_price) / max(target_1 - buy_price, 0.01)) * 100, 2)
    target_2_progress = round(((current_price - buy_price) / max(target_2 - buy_price, 0.01)) * 100, 2)
    sell_risk = int(position["Sat Riski"])

    alerts = []
    if stop_distance <= 2:
        alerts.append("Stop seviyesine yaklaşıldı")
    if held_days >= total_days:
        alerts.append("Taşıma süresi doldu")
    if current_price >= target_1:
        alerts.append("Hedef 1 görüldü")
    if current_price >= target_2:
        alerts.append("Hedef 2 görüldü")
    if sell_risk >= 70:
        alerts.append("Sat riski yükseldi")

    return (
        {
            "Hisse": symbol,
            "Alış fiyatı": buy_price,
            "Güncel fiyat": current_price,
            "Kâr/Zarar %": pnl_pct,
            "Kaç gündür taşınıyor": held_days,
            "Kalan gün": remaining_days,
            "Sat riski %": sell_risk,
            "Stop’a uzaklık %": stop_distance,
            "Hedef 1’e uzaklık %": target_1_distance,
            "Hedef 2’ye uzaklık %": target_2_distance,
            "Hedef 1 ilerleme %": target_1_progress,
            "Hedef 2 ilerleme %": target_2_progress,
            "Taşıma Gün Hedefi": total_days,
            "Uyarılar": ", ".join(alerts) if alerts else "-",
        },
        alerts,
    )


def close_position(position: dict[str, object], sell_price: float, sell_date: object) -> dict[str, object]:
    buy_price = float(position["Alış Fiyatı"])
    buy_date = datetime.fromisoformat(str(position["Alış Tarihi"])).date()
    if hasattr(sell_date, "isoformat"):
        close_date = sell_date
    else:
        close_date = datetime.fromisoformat(str(sell_date)).date()
    held_days = max(0, (close_date - buy_date).days)
    pnl_pct = round(((float(sell_price) - buy_price) / buy_price) * 100, 2) if buy_price else 0.0
    return {
        **position,
        "Satış Fiyatı": round(float(sell_price), 2),
        "Satış Tarihi": close_date.isoformat(),
        "Kâr/Zarar %": pnl_pct,
        "Kaç gün taşındı": held_days,
        "Hedef 1 görüldü mü": "Evet" if float(sell_price) >= float(position["Hedef 1"]) else "Hayır",
        "Hedef 2 görüldü mü": "Evet" if float(sell_price) >= float(position["Hedef 2"]) else "Hayır",
        "Stop çalıştı mı": "Evet" if float(sell_price) <= float(position["Stop Loss"]) else "Hayır",
    }


def position_label(position: dict[str, object]) -> str:
    return f"{position['Hisse']} | {position['Lot / Adet']} lot | {position['Alış Tarihi']}"


def render_pro_buy_page() -> None:
    load_current_user_pro_data()
    st.markdown("### Aldım")
    bist_symbols = get_bist_symbols_or_stop()
    symbol_labels = build_symbol_labels(bist_symbols)
    symbol = st.selectbox(
        "Hisse",
        bist_symbols["symbol"].tolist(),
        format_func=lambda value: symbol_labels.get(value, value),
    )
    quantity = st.number_input("Lot / adet", min_value=1, value=1, step=1)
    if st.button("ALDIM", type="primary"):
        with st.spinner(f"{symbol} için güncel analiz alınıyor..."):
            position = build_buy_snapshot(symbol, int(quantity))
        st.session_state.yeb_open_positions.append(position)
        save_current_user_pro_data()
        st.success(f"{symbol} pozisyonu kaydedildi.")
    st.caption(DISCLAIMER)


def render_pro_positions_page() -> None:
    load_current_user_pro_data()
    st.markdown("### Pozisyon Takibi")
    positions = st.session_state.get("yeb_open_positions", [])
    if not positions:
        st.info("Açık pozisyon yok.")
        return

    st.markdown(
        """
        <style>
            .yeb-position-card {
                border: 1px solid var(--nova-border);
                border-radius: var(--nova-radius);
                background: var(--nova-card-bg);
                box-shadow: var(--nova-shadow);
                padding: 16px;
                overflow: hidden;
                margin-bottom: 14px;
            }
            .yeb-position-top {
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 12px;
                margin-bottom: 14px;
            }
            .yeb-position-symbol {
                color: var(--nova-text);
                font-size: 1.15rem;
                font-weight: 840;
                line-height: 1.2;
            }
            .yeb-position-sub {
                color: var(--nova-muted);
                font-size: 0.82rem;
                margin-top: 3px;
                line-height: 1.35;
            }
            .yeb-pnl {
                border-radius: 999px;
                padding: 7px 11px;
                font-size: 0.84rem;
                font-weight: 820;
                line-height: 1;
                white-space: nowrap;
            }
            .yeb-pnl.positive {
                color: #bbf7d0;
                background: rgba(34, 197, 94, 0.16);
                border: 1px solid rgba(34, 197, 94, 0.42);
            }
            .yeb-pnl.negative {
                color: #fecaca;
                background: rgba(239, 68, 68, 0.15);
                border: 1px solid rgba(239, 68, 68, 0.40);
            }
            .yeb-position-grid {
                display: grid;
                grid-template-columns: repeat(6, minmax(0, 1fr));
                gap: 10px;
                margin: 12px 0 14px;
            }
            .yeb-position-metric.targets {
                grid-column: span 2;
            }
            .yeb-position-metric {
                border: 1px solid rgba(148, 163, 184, 0.16);
                border-radius: var(--nova-radius);
                background: rgba(15, 23, 42, 0.30);
                padding: 11px;
                min-height: 82px;
            }
            .yeb-position-label {
                color: var(--nova-muted);
                font-size: 0.72rem;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                line-height: 1.25;
            }
            .yeb-position-value {
                color: var(--nova-text);
                font-size: 1.03rem;
                font-weight: 780;
                line-height: 1.25;
                margin-top: 7px;
                overflow-wrap: anywhere;
            }
            .yeb-progress-shell {
                height: 9px;
                border-radius: 999px;
                background: rgba(148, 163, 184, 0.18);
                overflow: hidden;
                margin-top: 8px;
            }
            .yeb-progress-fill {
                height: 100%;
                border-radius: 999px;
                background: linear-gradient(90deg, var(--nova-cyan), var(--nova-green));
            }
            .yeb-progress-fill.negative {
                background: linear-gradient(90deg, var(--nova-red), #f97316);
            }
            .yeb-target-line {
                display: grid;
                grid-template-columns: 38px 20px 1fr auto;
                align-items: center;
                gap: 8px;
                margin-top: 9px;
            }
            .yeb-target-name {
                color: var(--nova-text);
                font-size: 0.82rem;
                font-weight: 820;
            }
            .yeb-target-zero {
                color: var(--nova-muted);
                font-size: 0.72rem;
                font-weight: 780;
                text-align: right;
                position: relative;
            }
            .yeb-target-zero::after {
                content: "";
                position: absolute;
                right: -5px;
                top: -4px;
                width: 1px;
                height: 18px;
                background: rgba(148, 163, 184, 0.55);
            }
            .yeb-target-track {
                height: 9px;
                border-radius: 999px;
                background: rgba(148, 163, 184, 0.18);
                overflow: hidden;
            }
            .yeb-target-pct {
                color: var(--nova-muted);
                font-size: 0.78rem;
                font-weight: 720;
                white-space: nowrap;
            }
            .yeb-target-pct.negative {
                color: #fecaca;
            }
            .yeb-detail-grid {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 8px;
                margin-top: 10px;
            }
            .yeb-detail-item {
                border: 1px solid rgba(148, 163, 184, 0.12);
                border-radius: var(--nova-radius);
                background: rgba(2, 6, 23, 0.18);
                padding: 9px 10px;
            }
            .yeb-detail-label {
                color: var(--nova-muted);
                font-size: 0.68rem;
                text-transform: uppercase;
                letter-spacing: 0.04em;
                line-height: 1.25;
            }
            .yeb-detail-value {
                color: var(--nova-text);
                font-size: 0.92rem;
                font-weight: 760;
                line-height: 1.25;
                margin-top: 4px;
            }
            .yeb-alert-row {
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
                margin-top: 10px;
            }
            .yeb-alert-pill {
                color: #fde68a;
                background: rgba(245, 158, 11, 0.14);
                border: 1px solid rgba(245, 158, 11, 0.38);
                border-radius: 999px;
                padding: 6px 10px;
                font-size: 0.78rem;
                font-weight: 720;
                line-height: 1;
            }
            .yeb-alert-pill.empty {
                color: var(--nova-muted);
                background: rgba(148, 163, 184, 0.10);
                border-color: rgba(148, 163, 184, 0.20);
            }
            @media (max-width: 1050px) {
                .yeb-position-grid {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }
                .yeb-position-metric.targets {
                    grid-column: span 2;
                }
                .yeb-detail-grid {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }
            }
            @media (max-width: 560px) {
                .yeb-position-top {
                    flex-direction: column;
                }
                .yeb-position-grid {
                    grid-template-columns: 1fr;
                }
                .yeb-position-metric.targets {
                    grid-column: span 1;
                }
                .yeb-detail-grid {
                    grid-template-columns: 1fr;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    for position in positions:
        row, alerts = position_tracking_row(position)
        progress_pct = min(100, round((row["Kaç gündür taşınıyor"] / max(row["Taşıma Gün Hedefi"], 1)) * 100, 1))
        target_1_progress = float(row["Hedef 1 ilerleme %"])
        target_2_progress = float(row["Hedef 2 ilerleme %"])
        target_1_width = min(100, abs(target_1_progress))
        target_2_width = min(100, abs(target_2_progress))
        target_1_class = "negative" if target_1_progress < 0 else ""
        target_2_class = "negative" if target_2_progress < 0 else ""
        pnl_class = "positive" if float(row["Kâr/Zarar %"]) >= 0 else "negative"
        alert_html = "".join(
            f'<span class="yeb-alert-pill">{escape(alert)}</span>'
            for alert in alerts
        ) or '<span class="yeb-alert-pill empty">Aktif uyarı yok</span>'
        st.markdown(
            f"""
            <div class="yeb-position-card">
                <div class="yeb-position-top">
                    <div>
                        <div class="yeb-position-symbol">{escape(str(row["Hisse"]))}</div>
                        <div class="yeb-position-sub">
                            Alış: {format_number(float(row["Alış fiyatı"]))} • Güncel: {format_number(float(row["Güncel fiyat"]))}
                        </div>
                    </div>
                    <div class="yeb-pnl {pnl_class}">%{format_number(float(row["Kâr/Zarar %"]))}</div>
                </div>
                <div class="yeb-position-grid">
                    <div class="yeb-position-metric targets">
                        <div class="yeb-position-label">Hedefler</div>
                        <div class="yeb-target-line">
                            <div class="yeb-target-name">H1</div>
                            <div class="yeb-target-zero">0</div>
                            <div class="yeb-target-track"><div class="yeb-progress-fill {target_1_class}" style="width:{target_1_width}%"></div></div>
                            <div class="yeb-target-pct {target_1_class}">%{format_number(target_1_progress)} / kalan %{format_number(float(row["Hedef 1’e uzaklık %"]))}</div>
                        </div>
                        <div class="yeb-target-line">
                            <div class="yeb-target-name">H2</div>
                            <div class="yeb-target-zero">0</div>
                            <div class="yeb-target-track"><div class="yeb-progress-fill {target_2_class}" style="width:{target_2_width}%"></div></div>
                            <div class="yeb-target-pct {target_2_class}">%{format_number(target_2_progress)} / kalan %{format_number(float(row["Hedef 2’ye uzaklık %"]))}</div>
                        </div>
                    </div>
                    <div class="yeb-position-metric">
                        <div class="yeb-position-label">Taşıma Süresi</div>
                        <div class="yeb-position-value">{row["Kaç gündür taşınıyor"]} / {row["Taşıma Gün Hedefi"]} gün</div>
                        <div class="yeb-progress-shell"><div class="yeb-progress-fill" style="width:{progress_pct}%"></div></div>
                    </div>
                    <div class="yeb-position-metric">
                        <div class="yeb-position-label">Kalan Gün</div>
                        <div class="yeb-position-value">{row["Kalan gün"]}</div>
                    </div>
                    <div class="yeb-position-metric">
                        <div class="yeb-position-label">Sat Riski</div>
                        <div class="yeb-position-value">%{row["Sat riski %"]}</div>
                    </div>
                    <div class="yeb-position-metric">
                        <div class="yeb-position-label">Stop Uzaklığı</div>
                        <div class="yeb-position-value">%{format_number(float(row["Stop’a uzaklık %"]))}</div>
                    </div>
                </div>
                <div class="yeb-detail-grid">
                    <div class="yeb-detail-item">
                        <div class="yeb-detail-label">Alış Fiyatı</div>
                        <div class="yeb-detail-value">{format_number(float(row["Alış fiyatı"]))}</div>
                    </div>
                    <div class="yeb-detail-item">
                        <div class="yeb-detail-label">Güncel Fiyat</div>
                        <div class="yeb-detail-value">{format_number(float(row["Güncel fiyat"]))}</div>
                    </div>
                    <div class="yeb-detail-item">
                        <div class="yeb-detail-label">Kâr/Zarar</div>
                        <div class="yeb-detail-value">%{format_number(float(row["Kâr/Zarar %"]))}</div>
                    </div>
                    <div class="yeb-detail-item">
                        <div class="yeb-detail-label">Kalan Gün</div>
                        <div class="yeb-detail-value">{row["Kalan gün"]}</div>
                    </div>
                    <div class="yeb-detail-item">
                        <div class="yeb-detail-label">Taşınan Gün</div>
                        <div class="yeb-detail-value">{row["Kaç gündür taşınıyor"]}</div>
                    </div>
                    <div class="yeb-detail-item">
                        <div class="yeb-detail-label">Sat Riski</div>
                        <div class="yeb-detail-value">%{row["Sat riski %"]}</div>
                    </div>
                    <div class="yeb-detail-item">
                        <div class="yeb-detail-label">Stop Uzaklığı</div>
                        <div class="yeb-detail-value">%{format_number(float(row["Stop’a uzaklık %"]))}</div>
                    </div>
                    <div class="yeb-detail-item">
                        <div class="yeb-detail-label">Hedef Uzaklıkları</div>
                        <div class="yeb-detail-value">H1 %{format_number(float(row["Hedef 1’e uzaklık %"]))} / H2 %{format_number(float(row["Hedef 2’ye uzaklık %"]))}</div>
                    </div>
                </div>
                <div class="yeb-alert-row">{alert_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.caption(DISCLAIMER)


def render_pro_sell_page() -> None:
    load_current_user_pro_data()
    st.markdown("### Sattım")
    positions = st.session_state.get("yeb_open_positions", [])
    if not positions:
        st.info("Satılacak açık pozisyon yok.")
        return

    selected_position = st.selectbox("Açık pozisyon", positions, format_func=position_label)
    sell_price = st.number_input("Satış fiyatı", min_value=0.01, value=float(selected_position["Alış Fiyatı"]), step=0.01)
    sell_date = st.date_input("Satış tarihi", value=now_istanbul().date())
    if st.button("SATTIM", type="primary"):
        closed_trade = close_position(selected_position, sell_price, sell_date)
        st.session_state.yeb_open_positions = [
            position for position in positions if position["id"] != selected_position["id"]
        ]
        st.session_state.yeb_closed_trades.append(closed_trade)
        save_current_user_pro_data()
        st.success(f"{selected_position['Hisse']} pozisyonu kapatıldı.")
    st.caption(DISCLAIMER)


def render_trade_journal_page() -> None:
    load_current_user_pro_data()
    st.markdown("### Trade Journal")
    closed_trades = st.session_state.get("yeb_closed_trades", [])
    if not closed_trades:
        st.info("Kapalı işlem yok.")
        return

    for trade in reversed(closed_trades):
        pnl = float(trade.get("Kâr/Zarar %", 0))
        pnl_class = "positive" if pnl >= 0 else "negative"
        st.markdown(
            f"""
            <div class="nova-card yeb-journal-card">
                <div class="yeb-journal-top">
                    <div>
                        <div class="yeb-journal-symbol">{escape(str(trade.get("Hisse", "-")))}</div>
                        <div class="nova-card-note">
                            Alış: {escape(str(trade.get("Alış Tarihi", "-")))} · Satış: {escape(str(trade.get("Satış Tarihi", "-")))}
                        </div>
                    </div>
                    <div class="yeb-journal-pnl {pnl_class}">%{format_number(pnl)}</div>
                </div>
                <div class="yeb-journal-grid">
                    <div><span>Alış Fiyatı</span><strong>{format_number(float(trade.get("Alış Fiyatı", 0)))}</strong></div>
                    <div><span>Satış Fiyatı</span><strong>{format_number(float(trade.get("Satış Fiyatı", 0)))}</strong></div>
                    <div><span>Taşınan Gün</span><strong>{escape(str(trade.get("Kaç gün taşındı", 0)))}</strong></div>
                    <div><span>Hedef 1</span><strong>{escape(str(trade.get("Hedef 1 görüldü mü", "-")))}</strong></div>
                    <div><span>Hedef 2</span><strong>{escape(str(trade.get("Hedef 2 görüldü mü", "-")))}</strong></div>
                    <div><span>Stop</span><strong>{escape(str(trade.get("Stop çalıştı mı", "-")))}</strong></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.caption(DISCLAIMER)


def render_yeb_pro_page() -> None:
    if not has_pro_access():
        render_pro_locked_page()
        return

    load_current_user_pro_data()
    st.title("YEB PRO")
    module = st.radio(
        "Pro Menü",
        PRO_MODULES,
        index=PRO_MODULES.index(DEFAULT_PRO_MODULE),
        horizontal=True,
        key="yeb_pro_module",
    )
    if module == "Aldım":
        render_pro_buy_page()
    elif module == "Sattım":
        render_pro_sell_page()
    elif module == "Pozisyon Takibi":
        render_pro_positions_page()
    elif module == "Trade Journal":
        render_trade_journal_page()
    else:
        render_coming_soon_page(f"⭐ {module}")


def render_page(page: str) -> None:
    if page == PUBLIC_DASHBOARD_PAGE:
        render_dashboard_page()
    elif page == SMART_SCANNER_PAGE:
        if not is_authenticated() and not render_login_page():
            return
        render_smart_scanner_page()
    elif page == YEB_PRO_PAGE:
        render_yeb_pro_page()
    else:
        render_coming_soon_page(page)


def main() -> None:
    st.set_page_config(
        page_title="NOVA AI",
        page_icon="N",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_theme_state()
    init_access_state()
    apply_terminal_theme()
    selected_page = render_sidebar()
    render_page(selected_page)


if __name__ == "__main__":
    main()
