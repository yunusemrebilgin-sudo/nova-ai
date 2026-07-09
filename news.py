from __future__ import annotations

import math
from typing import Any

import streamlit as st
import yfinance as yf


LIVE_NEWS_IMPACT_ENABLED = False


POSITIVE_NEWS_KEYWORDS = (
    "anlaşma",
    "artış",
    "büyüme",
    "capacity",
    "contract",
    "dividend",
    "export",
    "growth",
    "ihale",
    "investment",
    "kâr",
    "kar",
    "kapasite",
    "new order",
    "pozitif",
    "profit",
    "record",
    "sözleşme",
    "temettü",
    "upgrade",
    "yatırım",
)

NEGATIVE_NEWS_KEYWORDS = (
    "borç",
    "ceza",
    "dava",
    "decline",
    "downgrade",
    "düşüş",
    "fine",
    "iptal",
    "lawsuit",
    "loss",
    "negatif",
    "probe",
    "risk",
    "soruşturma",
    "zarar",
)


def module_status() -> str:
    return "Haber etkisi metrik olarak aktif. Haber bulunamazsa etki %0.0 kabul edilir."


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_symbol_news(symbol: str) -> list[dict[str, Any]]:
    try:
        news_items = yf.Ticker(symbol).news
    except Exception:
        return []
    if not isinstance(news_items, list):
        return []
    return news_items[:6]


def _headline_text(item: dict[str, Any]) -> str:
    content = item.get("content") if isinstance(item.get("content"), dict) else {}
    title = item.get("title") or content.get("title") or ""
    summary = item.get("summary") or content.get("summary") or ""
    return f"{title} {summary}".strip().lower()


def news_impact_percent(symbol: str, company_name: str = "") -> float:
    if not LIVE_NEWS_IMPACT_ENABLED:
        return 0.0

    news_items = fetch_symbol_news(symbol)
    if not news_items:
        return 0.0

    score = 0.0
    matched_items = 0
    company_hint = company_name.lower().strip()
    for item in news_items:
        text = _headline_text(item)
        if not text:
            continue
        if company_hint and company_hint.split()[0] not in text and symbol.split(".")[0].lower() not in text:
            relevance_weight = 0.65
        else:
            relevance_weight = 1.0
        positive_hits = sum(1 for keyword in POSITIVE_NEWS_KEYWORDS if keyword in text)
        negative_hits = sum(1 for keyword in NEGATIVE_NEWS_KEYWORDS if keyword in text)
        if positive_hits or negative_hits:
            matched_items += 1
        score += (positive_hits - negative_hits) * relevance_weight

    if score == 0:
        return 0.0

    confidence_decay = min(1.0, 0.45 + matched_items * 0.18)
    raw_impact = math.tanh(score / 4.0) * confidence_decay
    if raw_impact >= 0:
        return round(min(3.0, raw_impact * 3.0), 1)
    return round(max(-4.0, raw_impact * 4.0), 1)
