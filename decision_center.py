import plotly.graph_objects as go
import streamlit as st

from utils import DISCLAIMER, format_number


def _tokens() -> dict[str, str]:
    if st.session_state.get("theme_mode", "dark") == "light":
        return {
            "template": "plotly_white",
            "text": "#0f172a",
            "panel": "#ffffff",
            "grid": "#e2e8f0",
            "accent": "#2563eb",
        }
    return {
        "template": "plotly_dark",
        "text": "#e5edf7",
        "panel": "#07111f",
        "grid": "#1f2a44",
        "accent": "#38bdf8",
    }


def confidence_gauge(value: int) -> go.Figure:
    tokens = _tokens()
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": "/100", "font": {"size": 36, "color": tokens["text"]}},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": tokens["accent"]},
                "steps": [
                    {"range": [0, 40], "color": "rgba(239, 68, 68, 0.35)"},
                    {"range": [40, 70], "color": "rgba(245, 158, 11, 0.35)"},
                    {"range": [70, 100], "color": "rgba(34, 197, 94, 0.35)"},
                ],
            },
        )
    )
    fig.update_layout(
        height=265,
        margin={"l": 12, "r": 12, "t": 20, "b": 8},
        template=tokens["template"],
        paper_bgcolor=tokens["panel"],
        font={"color": tokens["text"]},
    )
    return fig


def radar_chart(scores: dict[str, int]) -> go.Figure:
    tokens = _tokens()
    labels = ["Trend", "Teknik", "Momentum", "Hacim", "Risk", "Volatilite", "Temel"]
    values = [
        scores["Trend"],
        scores["Teknik"],
        scores["Momentum"],
        scores["Hacim"],
        scores["Risk"],
        scores["Volatilite"],
        scores["Temel"],
    ]
    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=values + [values[0]],
            theta=labels + [labels[0]],
            fill="toself",
            line={"color": tokens["accent"], "width": 2},
            fillcolor="rgba(37, 99, 235, 0.22)",
        )
    )
    fig.update_layout(
        height=360,
        template=tokens["template"],
        paper_bgcolor=tokens["panel"],
        font={"color": tokens["text"]},
        polar={
            "radialaxis": {"visible": True, "range": [0, 100], "gridcolor": tokens["grid"]},
            "angularaxis": {"gridcolor": tokens["grid"]},
            "bgcolor": tokens["panel"],
        },
        showlegend=False,
        margin={"l": 24, "r": 24, "t": 24, "b": 24},
    )
    return fig


def ai_comment(decision: dict[str, object], scores: dict[str, int]) -> str:
    parts = []
    parts.append("Trend güçlü." if scores["Trend"] >= 70 else "Trend henüz tam güçlenmiş değil.")
    parts.append("EMA yapısı olumlu." if scores["Teknik"] >= 65 else "EMA yapısı temkinli izlenmeli.")
    parts.append("Momentum pozitif." if scores["Momentum"] >= 60 else "Momentum tarafında zayıflama riski var.")
    parts.append("Hacim destekliyor." if scores["Hacim"] >= 60 else "Hacim desteği sınırlı.")
    if decision["main_decision"] in {"AL", "TAKİP ET"}:
        parts.append("Yeni alımlar için uygun görünüm izlenebilir.")
    else:
        parts.append("Yeni işlem için riskler net biçimde izlenmeli.")
    return " ".join(parts)


def render_progress_bars(scores: dict[str, int]) -> None:
    for label in ["Trend", "Momentum", "Hacim", "Risk", "Volatilite", "ADX"]:
        st.progress(scores[label], text=f"{label}: %{scores[label]}")


def _mini_card(label: str, value: str, extra_class: str = "") -> str:
    return f"""
    <div class="nova-mini-card {extra_class}">
        <div class="nova-mini-label">{label}</div>
        <div class="nova-mini-value">{value}</div>
    </div>
    """


def render_premium_decision_center(decision: dict[str, object], scores: dict[str, int]) -> None:
    title = {
        "AL": "🟢 GÜÇLÜ ALIM",
        "TAKİP ET": "🟡 TAKİP ET",
        "BEKLE": "🟡 BEKLE",
        "SAT": "🔴 SAT RİSKİ",
    }.get(str(decision["main_decision"]), "🟡 BEKLE")
    signal_class = decision.get("signal_class", "nova-signal-watch")

    mini_cards = "".join(
        [
            _mini_card("Ana Karar", str(decision["main_decision"])),
            _mini_card("AI Güven Endeksi", f"%{decision['confidence']}"),
            _mini_card("Beklenen Taşıma Süresi", str(decision["holding_period"]), "nova-holding-card"),
            _mini_card("Sat Riski", f"%{decision['sell_probability']}"),
            _mini_card("Stop Loss", format_number(float(decision["stop_loss"]))),
        ]
    )
    left_col, center_col, right_col = st.columns([0.7, 1.05, 1.35])
    with left_col:
        st.markdown(f'<div class="nova-vertical-stack">{mini_cards}</div>', unsafe_allow_html=True)
    with center_col:
        st.markdown(
            f"""
            <div class="nova-signal {signal_class}">
                <div class="nova-card-title">NOVA AI DECISION CENTER</div>
                <div class="nova-card-value">{title}</div>
                <div class="nova-card-note">
                    İşlem Kalitesi: {decision["quality"]}<br>
                    İşlem Vadesi: {decision["horizon"]}<br>
                    Beklenen Getiri: %{decision["expected_return"]}<br>
                    Risk / Getiri: {decision["risk_reward"]}
                </div>
                <div class="nova-card-note">{DISCLAIMER}</div>
            </div>
            <div class="nova-card nova-holding-card">
                <div class="nova-card-title">⏳ Beklenen Taşıma Süresi</div>
                <div class="nova-holding-value">{decision["holding_period"]}</div>
                <div class="nova-card-note">Kesin satış günü değildir, teknik verilere göre tahmini işlem vadesidir.</div>
            </div>
            <div class="nova-card">
                <div class="nova-card-title">AI Yorumu</div>
                <div class="nova-card-note">{ai_comment(decision, scores)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right_col:
        st.plotly_chart(confidence_gauge(int(decision["confidence"])), width="stretch")
        render_progress_bars(scores)
        metric_cols = st.columns(2)
        values = [
            ("🎯 Beklenen Getiri", f"%{decision['expected_return']}"),
            ("🛑 Stop Loss", format_number(float(decision["stop_loss"]))),
            ("🎯 İlk Hedef", format_number(float(decision["first_target"]))),
            ("🚀 İkinci Hedef", format_number(float(decision["second_target"]))),
            ("⚠ Sat Riski", f"%{decision['sell_probability']}"),
            ("💰 Risk / Getiri", str(decision["risk_reward"])),
        ]
        for idx, (label, value) in enumerate(values):
            with metric_cols[idx % 2]:
                st.metric(label, value)
        st.plotly_chart(radar_chart(scores), width="stretch")
