from html import escape

import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from utils import DISCLAIMER, format_number


def _tokens() -> dict[str, str]:
    if st.session_state.get("theme_mode", "dark") == "light":
        return {
            "template": "plotly_white",
            "text": "#0f172a",
            "muted": "#475569",
            "panel": "#ffffff",
            "panel_2": "#f8fafc",
            "border": "#dbe3ef",
            "grid": "#e2e8f0",
            "accent": "#2563eb",
            "shadow": "rgba(15, 23, 42, 0.12)",
        }
    return {
        "template": "plotly_dark",
        "text": "#e5edf7",
        "muted": "#8da2bf",
        "panel": "#07111f",
        "panel_2": "#0b1628",
        "border": "#1f2a44",
        "grid": "#1f2a44",
        "accent": "#38bdf8",
        "shadow": "rgba(0, 0, 0, 0.28)",
    }


def _component_css() -> str:
    tokens = _tokens()
    return f"""
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            margin: 0;
            background: transparent;
            color: {tokens["text"]};
            font-family: "Inter", "Segoe UI", Arial, sans-serif;
            width: 100%;
            max-width: 100%;
            overflow-x: hidden;
        }}
        .stack {{
            display: grid;
            gap: 10px;
            width: 100%;
            min-width: 0;
        }}
        .card, .signal {{
            width: 100%;
            min-width: 0;
            height: auto;
            border: 1px solid {tokens["border"]};
            border-radius: 8px;
            padding: 14px;
            background: linear-gradient(180deg, {tokens["panel"]}, {tokens["panel_2"]});
            box-shadow: 0 12px 28px {tokens["shadow"]}, inset 0 1px 0 rgba(255,255,255,0.06);
            overflow: visible;
            overflow-wrap: anywhere;
            word-break: break-word;
            white-space: normal;
            hyphens: auto;
            line-height: 1.45;
        }}
        .signal.buy {{
            border-color: rgba(34, 197, 94, 0.58);
            background: rgba(34, 197, 94, 0.10);
        }}
        .signal.watch {{
            border-color: rgba(245, 158, 11, 0.62);
            background: rgba(245, 158, 11, 0.10);
        }}
        .signal.sell {{
            border-color: rgba(239, 68, 68, 0.58);
            background: rgba(239, 68, 68, 0.10);
        }}
        .label {{
            color: {tokens["muted"]};
            font-size: 11px;
            line-height: 1.25;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            overflow-wrap: anywhere;
            word-break: break-word;
        }}
        .value {{
            color: {tokens["text"]};
            margin-top: 5px;
            font-size: clamp(15px, 2.2vw, 21px);
            line-height: 1.22;
            font-weight: 780;
            overflow-wrap: anywhere;
            white-space: normal;
            word-break: break-word;
        }}
        .note {{
            color: {tokens["muted"]};
            margin-top: 8px;
            font-size: 13px;
            line-height: 1.48;
            overflow-wrap: anywhere;
            white-space: normal;
            word-break: break-word;
        }}
        .holding {{
            border-color: rgba(56, 189, 248, 0.58);
            background: rgba(56, 189, 248, 0.11);
        }}
        .holding .big {{
            color: {tokens["text"]};
            font-size: clamp(22px, 4.6vw, 34px);
            line-height: 1.12;
            font-weight: 860;
            margin-top: 8px;
            overflow-wrap: anywhere;
            word-break: break-word;
        }}
        @media (max-width: 520px) {{
            .card, .signal {{
                padding: 12px;
            }}
            .value {{
                font-size: 17px;
            }}
            .note {{
                font-size: 12.5px;
            }}
        }}
    </style>
    """


def _render_html(body: str, height: int) -> None:
    components.html(_component_css() + body, height=height, scrolling=True)


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
    <div class="card {extra_class}">
        <div class="label">{escape(label)}</div>
        <div class="value">{escape(value)}</div>
    </div>
    """


def _metric_card(label: str, value: str) -> str:
    return f"""
    <div class="dc-metric-card">
        <div class="label">{escape(label)}</div>
        <div class="value">{escape(value)}</div>
    </div>
    """


def _render_metric_grid(cards: str) -> None:
    tokens = _tokens()
    st.markdown(
        f"""
        <style>
            .dc-metric-grid {{
                display: grid;
                grid-template-columns: repeat(5, minmax(0, 1fr));
                gap: 10px;
                width: 100%;
                min-width: 0;
                margin: 0.65rem 0 0.35rem;
            }}
            .dc-metric-card {{
                min-width: 0;
                min-height: 104px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                border: 1px solid {tokens["border"]};
                border-radius: 8px;
                padding: 14px;
                background: linear-gradient(180deg, {tokens["panel"]}, {tokens["panel_2"]});
                box-shadow: 0 12px 28px {tokens["shadow"]}, inset 0 1px 0 rgba(255,255,255,0.06);
                overflow-wrap: anywhere;
                word-break: break-word;
            }}
            .dc-metric-card .label {{
                color: {tokens["muted"]};
                font-size: 11px;
                line-height: 1.25;
                letter-spacing: 0.06em;
                text-transform: uppercase;
                overflow-wrap: anywhere;
            }}
            .dc-metric-card .value {{
                color: {tokens["text"]};
                margin-top: 7px;
                font-size: clamp(18px, 2vw, 26px);
                line-height: 1.18;
                font-weight: 820;
                overflow-wrap: anywhere;
            }}
            @media (max-width: 520px) {{
                .dc-metric-grid {{
                    grid-template-columns: 1fr;
                }}
                .dc-metric-card {{
                    min-height: 82px;
                    padding: 12px;
                }}
            }}
            @media (min-width: 521px) and (max-width: 980px) {{
                .dc-metric-grid {{
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }}
            }}
        </style>
        <div class="dc-metric-grid">{cards}</div>
        """,
        unsafe_allow_html=True,
    )


def render_premium_decision_center(decision: dict[str, object], scores: dict[str, int]) -> None:
    title = {
        "AL": "🟢 GÜÇLÜ ALIM",
        "TAKİP ET": "🟡 TAKİP ET",
        "BEKLE": "🟡 BEKLE",
        "SAT": "🔴 SAT RİSKİ",
    }.get(str(decision["main_decision"]), "🟡 BEKLE")
    signal_class = decision.get("signal_class", "nova-signal-watch")
    component_class = "signal watch"
    if signal_class == "nova-signal-buy":
        component_class = "signal buy"
    elif signal_class == "nova-signal-sell":
        component_class = "signal sell"

    mini_cards = "".join(
        [
            _mini_card("Ana Karar", str(decision["main_decision"])),
            _mini_card("AI Güven Endeksi", f"%{decision['confidence']}"),
            _mini_card("Beklenen Taşıma Süresi", str(decision["holding_period"]), "holding"),
            _mini_card("Sat Riski", f"%{decision['sell_probability']}"),
            _mini_card("Stop Loss", format_number(float(decision["stop_loss"]))),
        ]
    )

    center_html = f"""
    <div class="stack">
        <div class="{component_class}">
            <div class="label">NOVA AI DECISION CENTER</div>
            <div class="value">{escape(title)}</div>
            <div class="note">
                İşlem Kalitesi: {escape(str(decision["quality"]))}<br>
                İşlem Vadesi: {escape(str(decision["horizon"]))}<br>
                Beklenen Getiri: %{escape(str(decision["expected_return"]))}<br>
                Risk / Getiri: {escape(str(decision["risk_reward"]))}
            </div>
            <div class="note">{escape(DISCLAIMER)}</div>
        </div>
        <div class="card holding">
            <div class="label">⏳ Beklenen Taşıma Süresi</div>
            <div class="big">{escape(str(decision["holding_period"]))}</div>
            <div class="note">Kesin satış günü değildir, teknik verilere göre tahmini işlem vadesidir.</div>
        </div>
        <div class="card">
            <div class="label">AI Yorumu</div>
            <div class="note">{escape(ai_comment(decision, scores))}</div>
        </div>
    </div>
    """

    left_col, center_col, right_col = st.columns([0.7, 1.05, 1.35])
    with left_col:
        _render_html(f'<div class="stack">{mini_cards}</div>', height=430)
    with center_col:
        _render_html(center_html, height=540)
    with right_col:
        st.plotly_chart(confidence_gauge(int(decision["confidence"])), width="stretch")
        render_progress_bars(scores)

    metric_cards = "".join(
        [
            _metric_card("Beklenen Getiri", f"%{decision['expected_return']}"),
            _metric_card("Stop Loss", format_number(float(decision["stop_loss"]))),
            _metric_card("İlk Hedef", format_number(float(decision["first_target"]))),
            _metric_card("İkinci Hedef", format_number(float(decision["second_target"]))),
            _metric_card("Risk / Getiri", str(decision["risk_reward"])),
        ]
    )
    _render_metric_grid(metric_cards)

    st.plotly_chart(radar_chart(scores), width="stretch")
