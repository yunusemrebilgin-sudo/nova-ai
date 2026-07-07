import streamlit as st


def available_themes() -> tuple[str, str]:
    return "dark", "light"


def init_theme_state() -> None:
    if "theme_mode" not in st.session_state:
        st.session_state.theme_mode = "dark"
    if "theme_toggle" not in st.session_state:
        st.session_state.theme_toggle = st.session_state.theme_mode == "light"


def is_dark_theme() -> bool:
    return st.session_state.get("theme_mode", "dark") == "dark"


def set_theme_from_toggle() -> None:
    st.session_state.theme_mode = "light" if st.session_state.theme_toggle else "dark"


def theme_tokens() -> dict[str, str]:
    if is_dark_theme():
        return {
            "bg": "#020617",
            "panel": "#07111f",
            "panel_2": "#0b1628",
            "border": "#1f2a44",
            "text": "#e5edf7",
            "muted": "#8da2bf",
            "cyan": "#38bdf8",
            "green": "#22c55e",
            "amber": "#f59e0b",
            "red": "#ef4444",
            "app_background": "radial-gradient(circle at 18% 0%, rgba(14, 165, 233, 0.14), transparent 28%), linear-gradient(180deg, #020617 0%, #030712 100%)",
            "sidebar_background": "linear-gradient(180deg, #020617 0%, #07111f 100%)",
            "card_background": "linear-gradient(180deg, rgba(15, 23, 42, 0.94), rgba(7, 17, 31, 0.94))",
            "coming_background": "linear-gradient(180deg, rgba(15, 23, 42, 0.92), rgba(7, 17, 31, 0.92))",
            "input_bg": "#07111f",
            "input_border": "#24324d",
            "plot_template": "plotly_dark",
            "plot_bg": "#07111f",
            "grid": "#1f2a44",
        }

    return {
        "bg": "#f8fafc",
        "panel": "#ffffff",
        "panel_2": "#f1f5f9",
        "border": "#dbe3ef",
        "text": "#0f172a",
        "muted": "#475569",
        "cyan": "#2563eb",
        "green": "#16a34a",
        "amber": "#d97706",
        "red": "#dc2626",
        "app_background": "linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)",
        "sidebar_background": "linear-gradient(180deg, #ffffff 0%, #f1f5f9 100%)",
        "card_background": "linear-gradient(180deg, #ffffff, #f8fafc)",
        "coming_background": "linear-gradient(180deg, #ffffff, #f8fafc)",
        "input_bg": "#ffffff",
        "input_border": "#cbd5e1",
        "plot_template": "plotly_white",
        "plot_bg": "#ffffff",
        "grid": "#e2e8f0",
    }


def apply_terminal_theme() -> None:
    tokens = theme_tokens()
    css = """
        <style>
            :root {
                --nova-bg: __BG__;
                --nova-panel: __PANEL__;
                --nova-panel-2: __PANEL_2__;
                --nova-border: __BORDER__;
                --nova-text: __TEXT__;
                --nova-muted: __MUTED__;
                --nova-green: __GREEN__;
                --nova-amber: __AMBER__;
                --nova-red: __RED__;
                --nova-cyan: __CYAN__;
                --nova-card-bg: __CARD_BACKGROUND__;
                --nova-input-bg: __INPUT_BG__;
                --nova-input-border: __INPUT_BORDER__;
                --nova-radius: 8px;
                --nova-card-padding: 16px;
                --nova-shadow: 0 14px 34px rgba(15, 23, 42, 0.14), inset 0 1px 0 rgba(255,255,255,0.06);
                --nova-section-gap: 0.9rem;
            }

            .stApp {
                background: __APP_BACKGROUND__;
                color: var(--nova-text);
            }

            [data-testid="stHeader"] {
                background: rgba(2, 6, 23, 0);
            }

            [data-testid="stSidebar"] {
                background: __SIDEBAR_BACKGROUND__;
                border-right: 1px solid var(--nova-border);
                min-width: 220px;
                max-width: 240px;
            }

            [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
                padding-top: 1.2rem;
                overflow-x: hidden;
            }

            [data-testid="stSidebar"] h1,
            [data-testid="stSidebar"] h2,
            [data-testid="stSidebar"] h3,
            [data-testid="stSidebar"] p,
            [data-testid="stSidebar"] label,
            [data-testid="stSidebar"] .stMarkdown {
                color: var(--nova-text) !important;
            }

            [data-testid="stSidebar"] .stRadio > label {
                display: none;
            }

            [data-testid="stSidebar"] div[role="radiogroup"] {
                gap: 0.25rem;
            }

            [data-testid="stSidebar"] div[role="radiogroup"] label {
                border: 1px solid transparent;
                border-radius: var(--nova-radius);
                padding: 0.58rem 0.7rem;
                margin-bottom: 0.2rem;
                background: rgba(15, 23, 42, 0.2);
                min-width: 0;
                white-space: normal;
                overflow-wrap: anywhere;
            }

            [data-testid="stSidebar"] div[role="radiogroup"] label:hover {
                background: rgba(56, 189, 248, 0.08);
                border-color: rgba(56, 189, 248, 0.25);
            }

            [data-testid="stSidebar"] div[role="radiogroup"] label[data-baseweb="radio"] > div:first-child {
                display: none;
            }

            .block-container {
                padding-top: 1.25rem;
                padding-bottom: 1.5rem;
                max-width: 1680px;
            }

            h1, h2, h3, label, .stMarkdown, .stCaptionContainer {
                color: var(--nova-text) !important;
            }

            h1 {
                font-size: 2.45rem !important;
                font-weight: 820 !important;
                letter-spacing: 0 !important;
            }

            h3 {
                font-weight: 740 !important;
                margin-top: 1.05rem !important;
                margin-bottom: 0.55rem !important;
            }

            .nova-logo {
                padding: 0.35rem 0.15rem 1rem;
                min-width: 0;
            }

            .nova-logo-main {
                color: var(--nova-text);
                font-size: 1.45rem;
                font-weight: 850;
                letter-spacing: 0.04em;
                overflow-wrap: anywhere;
            }

            .nova-logo-sub {
                color: var(--nova-muted);
                font-size: 0.78rem;
                margin-top: 0.12rem;
                overflow-wrap: anywhere;
            }

            .nova-sidebar-line {
                height: 1px;
                background: var(--nova-border);
                margin: 0.75rem 0 1rem;
            }

            .nova-subtitle {
                margin-top: -0.6rem;
                margin-bottom: 0.75rem;
                color: var(--nova-muted);
                font-size: 1.05rem;
                line-height: 1.45;
                overflow-wrap: anywhere;
            }

            [data-testid="stVerticalBlock"] {
                gap: var(--nova-section-gap);
            }

            [data-testid="stHorizontalBlock"] {
                gap: 0.85rem;
                align-items: stretch;
            }

            .nova-card,
            .nova-mini-card,
            .nova-signal,
            [data-testid="stMetric"] {
                background: var(--nova-card-bg);
                border: 1px solid var(--nova-border);
                border-radius: var(--nova-radius);
                box-shadow: var(--nova-shadow);
                backdrop-filter: blur(10px);
                color: var(--nova-text);
                min-width: 0;
                width: 100%;
                overflow: visible;
                overflow-wrap: anywhere;
                word-break: normal;
                white-space: normal;
            }

            .nova-card {
                padding: var(--nova-card-padding);
                min-height: 100%;
                display: flex;
                flex-direction: column;
                justify-content: flex-start;
            }

            .nova-card + .nova-card {
                margin-top: 0.75rem;
            }

            .nova-card-title {
                color: var(--nova-muted);
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin-bottom: 8px;
                line-height: 1.3;
                white-space: normal;
                overflow-wrap: anywhere;
            }

            .nova-card-value {
                color: var(--nova-text);
                font-size: clamp(1.05rem, 1.65vw, 1.45rem);
                font-weight: 760;
                line-height: 1.25;
                white-space: normal;
                overflow-wrap: anywhere;
            }

            .nova-card-note {
                color: var(--nova-muted);
                font-size: 0.86rem;
                margin-top: 6px;
                line-height: 1.55;
                white-space: normal;
                overflow-wrap: anywhere;
            }

            .nova-info-card {
                min-height: 112px;
            }

            .nova-signal {
                padding: 18px;
                margin-top: 0.75rem;
            }

            .nova-signal-buy {
                border-color: rgba(34, 197, 94, 0.5);
                background: rgba(34, 197, 94, 0.09);
            }

            .nova-signal-watch {
                border-color: rgba(245, 158, 11, 0.55);
                background: rgba(245, 158, 11, 0.09);
            }

            .nova-signal-sell {
                border-color: rgba(239, 68, 68, 0.5);
                background: rgba(239, 68, 68, 0.09);
            }

            .nova-signal-label {
                color: var(--nova-text);
                font-size: clamp(1.1rem, 1.8vw, 1.5rem);
                font-weight: 820;
                line-height: 1.25;
                white-space: normal;
                overflow-wrap: anywhere;
            }

            [data-testid="column"] {
                min-width: 0;
                display: flex;
                flex-direction: column;
            }

            [data-testid="column"] > div,
            [data-testid="stVerticalBlock"] > div:has(> .nova-card),
            [data-testid="stVerticalBlock"] > div:has(> .nova-signal) {
                min-width: 0;
            }

            [data-testid="column"] [data-testid="stMarkdownContainer"]:has(.nova-card),
            [data-testid="column"] [data-testid="stMarkdownContainer"]:has(.nova-signal) {
                height: 100%;
            }

            .nova-mini-card {
                padding: 12px;
            }

            .nova-mini-label {
                color: var(--nova-muted);
                font-size: 0.72rem;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                line-height: 1.25;
            }

            .nova-mini-value {
                color: var(--nova-text);
                font-size: clamp(0.98rem, 1.4vw, 1.18rem);
                font-weight: 780;
                line-height: 1.25;
                margin-top: 4px;
                white-space: normal;
                overflow-wrap: anywhere;
            }

            .nova-holding-card {
                border-color: rgba(56, 189, 248, 0.5);
                background: rgba(56, 189, 248, 0.10);
            }

            .nova-holding-value {
                color: var(--nova-text);
                font-size: clamp(1.35rem, 2.4vw, 2rem);
                font-weight: 860;
                line-height: 1.18;
                white-space: normal;
                overflow-wrap: anywhere;
            }

            .nova-chart-panel,
            [data-testid="stPlotlyChart"],
            [data-testid="stPlotlyChart"] > div {
                min-width: 0;
                max-width: 100%;
            }

            .nova-coming-soon {
                min-height: 58vh;
                display: flex;
                align-items: center;
                justify-content: center;
                border: 1px solid var(--nova-border);
                border-radius: var(--nova-radius);
                background: __COMING_BACKGROUND__;
            }

            .nova-coming-inner {
                text-align: center;
                max-width: 560px;
                padding: 2rem;
            }

            .nova-coming-icon {
                font-size: 3rem;
                margin-bottom: 0.75rem;
            }

            .nova-coming-title {
                font-size: 1.8rem;
                font-weight: 820;
                margin-bottom: 0.45rem;
                overflow-wrap: anywhere;
            }

            .nova-coming-text {
                color: var(--nova-muted);
                font-size: 1rem;
                line-height: 1.65;
                overflow-wrap: anywhere;
            }

            .stTextInput input,
            .stNumberInput input,
            .stSelectbox div[data-baseweb="select"] > div,
            .stMultiSelect div[data-baseweb="select"] > div {
                background-color: var(--nova-input-bg) !important;
                border-color: var(--nova-input-border) !important;
                color: var(--nova-text) !important;
            }

            .stTextInput input::placeholder,
            .stNumberInput input::placeholder {
                color: var(--nova-muted) !important;
            }

            div[data-baseweb="popover"],
            ul[role="listbox"] {
                background: var(--nova-panel) !important;
                color: var(--nova-text) !important;
            }

            [data-testid="stMetric"] {
                padding: 14px 16px;
                min-height: 96px;
                display: flex;
                flex-direction: column;
                justify-content: center;
            }

            [data-testid="stMetricLabel"] {
                color: var(--nova-muted) !important;
                white-space: normal !important;
                overflow-wrap: anywhere !important;
            }

            [data-testid="stMetricValue"] {
                color: var(--nova-text) !important;
                white-space: normal !important;
                overflow-wrap: anywhere !important;
                font-size: clamp(1.05rem, 1.9vw, 1.6rem) !important;
            }

            [data-testid="stDataFrame"] {
                border: 1px solid var(--nova-border);
                border-radius: var(--nova-radius);
                overflow: auto;
                max-width: 100%;
                background: var(--nova-panel);
                box-shadow: 0 10px 28px rgba(15, 23, 42, 0.10);
            }

            [data-testid="stDataFrame"] * {
                color: inherit;
            }

            [data-testid="stAlert"] {
                background-color: var(--nova-panel-2);
                color: var(--nova-text);
                border: 1px solid var(--nova-border);
                border-radius: var(--nova-radius);
                padding-top: 0.7rem;
                padding-bottom: 0.7rem;
            }

            @media (max-width: 900px) {
                .block-container {
                    padding-left: 0.85rem;
                    padding-right: 0.85rem;
                }

                h1 {
                    font-size: 2rem !important;
                }

                [data-testid="column"] {
                    width: 100% !important;
                    flex: 1 1 100% !important;
                }

                [data-testid="stHorizontalBlock"] {
                    gap: 0.85rem;
                    flex-wrap: wrap;
                }

                [data-testid="stSidebar"] {
                    min-width: 0;
                    max-width: 100%;
                }
            }

            @media (max-width: 520px) {
                .block-container {
                    padding-top: 1rem;
                }

                .nova-card,
                .nova-signal,
                [data-testid="stMetric"] {
                    padding: 12px;
                }

                .nova-card-title {
                    font-size: 0.72rem;
                }

                .nova-card-value,
                .nova-signal-label {
                    font-size: 1.08rem;
                }

                [data-testid="stPlotlyChart"] {
                    overflow-x: auto;
                }
            }
        </style>
    """
    for key, value in tokens.items():
        css = css.replace(f"__{key.upper()}__", value)
    st.markdown(css, unsafe_allow_html=True)
