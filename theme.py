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

            [data-testid="stButton"] > button,
            [data-testid="stFormSubmitButton"] > button {
                min-height: 2.65rem;
                border: 1px solid var(--nova-input-border) !important;
                border-radius: 9px !important;
                background: linear-gradient(180deg, var(--nova-panel-2), var(--nova-panel)) !important;
                color: var(--nova-text) !important;
                font-weight: 720 !important;
                letter-spacing: 0.01em;
                box-shadow: 0 7px 18px rgba(0, 0, 0, 0.14);
                opacity: 1 !important;
                transition: border-color 160ms ease, transform 160ms ease, box-shadow 160ms ease;
            }

            [data-testid="stButton"] > button p,
            [data-testid="stButton"] > button span,
            [data-testid="stFormSubmitButton"] > button p,
            [data-testid="stFormSubmitButton"] > button span {
                color: inherit !important;
                opacity: 1 !important;
            }

            [data-testid="stButton"] > button:hover,
            [data-testid="stFormSubmitButton"] > button:hover {
                border-color: var(--nova-cyan) !important;
                color: var(--nova-cyan) !important;
                box-shadow: 0 9px 22px rgba(14, 165, 233, 0.18);
                transform: translateY(-1px);
            }

            [data-testid="stButton"] > button[kind="primary"],
            [data-testid="stButton"] > button[data-testid="stBaseButton-primary"],
            [data-testid="stFormSubmitButton"] > button[kind="primary"] {
                border-color: var(--nova-cyan) !important;
                background: linear-gradient(135deg, #0891b2, #2563eb) !important;
                color: #ffffff !important;
            }

            [data-testid="stButton"] > button:disabled {
                border-color: var(--nova-border) !important;
                background: var(--nova-panel-2) !important;
                color: var(--nova-muted) !important;
                box-shadow: none;
                transform: none;
                opacity: 0.78 !important;
            }

            .st-key-selected_page {
                width: 100% !important;
                margin: 0 0 0.75rem;
                padding: 0 !important;
            }

            .st-key-selected_page [data-testid="stRadio"],
            .st-key-selected_page [data-testid="stRadio"] > div {
                width: 100% !important;
                max-width: none !important;
            }

            .st-key-selected_page div[role="radiogroup"] {
                display: grid !important;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 5px;
                width: 100% !important;
                max-width: none !important;
                padding: 6px;
                border: 1px solid var(--nova-border);
                border-radius: 14px;
                background: rgba(7, 17, 31, 0.78);
                box-shadow: 0 12px 30px rgba(0, 0, 0, 0.16), inset 0 1px 0 rgba(255, 255, 255, 0.035);
            }

            .st-key-selected_page label[data-baseweb="radio"] {
                width: 100%;
                min-width: 0 !important;
                min-height: 48px;
                display: flex !important;
                align-items: center;
                justify-content: center;
                margin: 0 !important;
                padding: 10px 14px !important;
                border: 1px solid transparent;
                border-radius: 10px;
                background: transparent;
                color: var(--nova-text) !important;
                box-shadow: none;
                cursor: pointer;
                opacity: 0.72;
                transition: border-color 160ms ease, background 160ms ease, opacity 160ms ease;
            }

            .st-key-selected_page label[data-baseweb="radio"] > div:first-child {
                display: none !important;
            }

            .st-key-selected_page label[data-baseweb="radio"] p,
            .st-key-selected_page label[data-baseweb="radio"] span,
            .st-key-selected_page label[data-baseweb="radio"] * {
                width: 100%;
                margin: 0 !important;
                color: var(--nova-text) !important;
                font-size: 0.88rem;
                font-weight: 740;
                line-height: 1.2;
                text-align: center;
                white-space: normal;
            }

            .st-key-selected_page label[data-baseweb="radio"]:hover {
                border-color: rgba(56, 189, 248, 0.18);
                background: rgba(56, 189, 248, 0.07);
                opacity: 1;
            }

            .st-key-selected_page label[data-baseweb="radio"]:has(input:checked) {
                border-color: rgba(56, 189, 248, 0.46);
                background: linear-gradient(135deg, rgba(8, 145, 178, 0.3), rgba(37, 99, 235, 0.26));
                color: var(--nova-text) !important;
                box-shadow: 0 7px 20px rgba(14, 165, 233, 0.13), inset 0 1px 0 rgba(255, 255, 255, 0.06);
                opacity: 1;
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

            [data-testid="stSidebar"] button,
            [data-testid="collapsedControl"],
            [data-testid="collapsedControl"] button {
                color: var(--nova-text) !important;
                opacity: 1 !important;
            }

            [data-testid="stSidebar"] button svg,
            [data-testid="collapsedControl"] svg,
            [data-testid="collapsedControl"] button svg {
                color: var(--nova-text) !important;
                fill: var(--nova-text) !important;
                stroke: var(--nova-text) !important;
                opacity: 1 !important;
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
                padding-top: 0.75rem;
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

            h1 a,
            h2 a,
            h3 a,
            h1 svg,
            h2 svg,
            h3 svg {
                color: var(--nova-muted) !important;
                fill: var(--nova-muted) !important;
                opacity: 0.85 !important;
            }

            div[role="radiogroup"] label,
            div[role="radiogroup"] label p,
            div[role="radiogroup"] label span {
                color: var(--nova-text) !important;
                opacity: 1 !important;
            }

            div[role="radiogroup"] label:hover p,
            div[role="radiogroup"] label:hover span {
                color: var(--nova-text) !important;
            }

            h3 {
                font-weight: 740 !important;
                margin-top: 1.05rem !important;
                margin-bottom: 0.55rem !important;
            }

            h4 {
                font-size: clamp(1.18rem, 2.2vw, 1.5rem) !important;
                font-weight: 760 !important;
                margin-top: 1rem !important;
                margin-bottom: 0.6rem !important;
                letter-spacing: -0.015em;
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

            .nova-header-logo {
                padding: 0.1rem 0 !important;
            }

            .nova-header-logo .nova-logo-main {
                font-size: 1.12rem;
                letter-spacing: 0.035em;
            }

            .nova-header-logo .nova-logo-sub {
                font-size: 0.68rem;
            }

            .st-key-brand_refresh button {
                min-height: 2.4rem !important;
                padding: 0 !important;
                border: 0 !important;
                background: transparent !important;
                box-shadow: none !important;
                color: var(--nova-text) !important;
                transform: none !important;
            }

            .st-key-brand_refresh button:hover {
                color: var(--nova-cyan) !important;
                border: 0 !important;
                background: transparent !important;
                box-shadow: none !important;
                transform: none !important;
            }

            .st-key-brand_refresh button p,
            .st-key-brand_refresh button span {
                color: inherit !important;
                font-size: clamp(1.55rem, 3vw, 2.15rem) !important;
                font-weight: 880 !important;
                letter-spacing: 0.12em !important;
                line-height: 1 !important;
                text-align: center !important;
                text-shadow: 0 0 24px rgba(56, 189, 248, 0.14);
            }

            .nova-header-brand-marker {
                margin-top: 0.28rem;
                color: var(--nova-muted);
                font-size: 0.54rem;
                font-weight: 680;
                letter-spacing: 0.2em;
                text-align: center;
                white-space: nowrap;
            }

            .nova-header-spacer {
                width: 100%;
                height: 1px;
            }

            .nova-account-chip {
                display: flex;
                align-items: center;
                gap: 9px;
                width: fit-content;
                max-width: 100%;
                margin-top: 0.28rem;
                padding: 7px 10px;
                border: 1px solid var(--nova-border);
                border-radius: 999px;
                background: var(--nova-panel-2);
                white-space: nowrap;
            }

            .nova-account-chip strong {
                color: var(--nova-text);
                font-size: 0.76rem;
            }

            .nova-account-chip span {
                color: var(--nova-muted);
                font-size: 0.68rem;
            }

            .st-key-account_menu {
                width: 100% !important;
                min-width: 150px !important;
            }

            .st-key-account_menu > div,
            .st-key-account_menu button {
                width: 100% !important;
                min-width: 150px !important;
                height: 2.55rem !important;
                min-height: 2.55rem !important;
                white-space: nowrap !important;
                word-break: keep-all !important;
                writing-mode: horizontal-tb !important;
            }

            .st-key-account_menu button,
            .st-key-account_menu [data-testid="stPopover"] button,
            .st-key-account_menu [data-testid="stBaseButton-primary"] {
                border: 1px solid var(--nova-input-border) !important;
                background: linear-gradient(135deg, #075985, #1d4ed8) !important;
                color: #ffffff !important;
                box-shadow: 0 7px 18px rgba(0, 0, 0, 0.14) !important;
                opacity: 1 !important;
            }

            .st-key-account_menu button:hover,
            .st-key-account_menu [data-testid="stPopover"] button:hover,
            .st-key-account_menu [data-testid="stBaseButton-primary"]:hover {
                border-color: var(--nova-cyan) !important;
                background: linear-gradient(135deg, #0369a1, #2563eb) !important;
                color: #ffffff !important;
            }

            .st-key-account_menu button p,
            .st-key-account_menu button span,
            .st-key-account_menu button div {
                width: auto !important;
                color: #ffffff !important;
                white-space: nowrap !important;
                word-break: keep-all !important;
                writing-mode: horizontal-tb !important;
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

            .nova-horizon-card {
                gap: 2px;
            }

            .nova-follow-label {
                color: var(--nova-muted);
                font-size: 0.68rem;
                line-height: 1.2;
                letter-spacing: 0.06em;
                text-transform: uppercase;
                margin-top: 8px;
                white-space: nowrap;
            }

            .nova-follow-track {
                position: relative;
                width: 100%;
                height: 8px;
                border-radius: 999px;
                background: rgba(148, 163, 184, 0.20);
                border: 1px solid rgba(148, 163, 184, 0.18);
                overflow: hidden;
                margin: 6px 0 4px;
            }

            .nova-follow-window {
                position: absolute;
                top: 1px;
                bottom: 1px;
                min-width: 10px;
                border-radius: 999px;
                background: linear-gradient(90deg, var(--nova-green), var(--nova-cyan));
                box-shadow: 0 0 12px rgba(34, 197, 94, 0.25);
            }

            .nova-horizon-decision {
                color: var(--nova-text);
                font-size: 0.9rem;
                font-weight: 780;
                line-height: 1.25;
                margin-top: 8px;
                overflow-wrap: anywhere;
            }

            .nova-pro-follow-detail {
                display: grid;
                grid-template-columns: minmax(0, 1fr) auto;
                gap: 10px 16px;
                align-items: center;
                margin-top: 0.25rem;
                border-color: rgba(56, 189, 248, 0.34);
                background:
                    linear-gradient(135deg, rgba(56, 189, 248, 0.10), rgba(34, 197, 94, 0.07)),
                    var(--nova-card-bg);
            }

            .nova-pro-follow-value {
                color: var(--nova-text);
                font-size: 1.18rem;
                font-weight: 820;
                line-height: 1.2;
                padding: 0.56rem 0.72rem;
                border-radius: var(--nova-radius);
                background: rgba(56, 189, 248, 0.10);
                border: 1px solid rgba(56, 189, 248, 0.26);
                white-space: nowrap;
            }

            .nova-info-card {
                min-height: 112px;
            }

            .nova-ai-summary-card {
                min-height: 100%;
            }

            .nova-ai-summary-card .nova-card-note {
                line-height: 1.5;
            }

            .dc-metric-card {
                min-height: 76px;
                padding: 12px 14px;
                justify-content: center;
            }

            .dc-metric-card .nova-card-title {
                font-size: 0.68rem;
                line-height: 1.2;
                margin: 0;
            }

            .dc-metric-card .nova-card-value {
                font-size: 1.08rem;
                line-height: 1.18;
                margin-top: 6px;
            }

            .nova-button-spacer {
                height: 1.72rem;
            }

            .nova-selected-asset {
                display: grid;
                grid-template-columns: minmax(120px, 1.05fr) minmax(155px, 0.9fr) minmax(175px, 1fr);
                gap: 12px;
                align-items: center;
                margin: 0.55rem 0 0.8rem;
                padding: 12px 15px;
                border: 1px solid var(--nova-border);
                border-radius: 10px;
                background: linear-gradient(110deg, var(--nova-panel-2), var(--nova-panel));
                box-shadow: var(--nova-shadow);
            }

            .nova-selected-symbol {
                color: var(--nova-text);
                font-size: 1.05rem;
                font-weight: 820;
                line-height: 1.2;
                white-space: nowrap;
            }

            .nova-selected-name,
            .nova-selected-price span,
            .nova-selected-time span {
                display: block;
                margin-top: 4px;
                color: var(--nova-muted);
                font-size: 0.72rem;
                line-height: 1.3;
            }

            .nova-selected-price strong,
            .nova-selected-time strong {
                display: inline-block;
                margin-top: 5px;
                color: var(--nova-text);
                font-size: 0.94rem;
                font-weight: 760;
            }

            .nova-selected-price strong {
                font-size: clamp(1.25rem, 2vw, 1.65rem);
                font-weight: 850;
                letter-spacing: -0.025em;
                text-shadow: 0 0 18px rgba(56, 189, 248, 0.16);
            }

            .nova-selected-price b {
                display: inline-block;
                margin-left: 10px;
                padding: 5px 9px;
                border-radius: 999px;
                font-size: 0.9rem;
                font-weight: 820;
                line-height: 1;
                animation: novaQuoteFramePulse 1.45s ease-out infinite;
            }

            .nova-price-up {
                --nova-quote-pulse: rgba(52, 211, 153, 0.34);
                color: #34d399;
                border: 1px solid rgba(52, 211, 153, 0.32);
                background: rgba(52, 211, 153, 0.12);
                box-shadow: 0 0 16px rgba(52, 211, 153, 0.1);
            }

            .nova-price-down {
                --nova-quote-pulse: rgba(251, 113, 133, 0.34);
                color: #fb7185;
                border: 1px solid rgba(251, 113, 133, 0.32);
                background: rgba(251, 113, 133, 0.12);
                box-shadow: 0 0 16px rgba(251, 113, 133, 0.1);
            }

            @keyframes novaQuoteFramePulse {
                0%, 100% {
                    opacity: 1;
                    transform: scale(1);
                    filter: brightness(1);
                    box-shadow: 0 0 0 0 var(--nova-quote-pulse);
                }
                50% {
                    opacity: 1;
                    transform: scale(1);
                    filter: brightness(1);
                    box-shadow: 0 0 0 6px rgba(0, 0, 0, 0);
                }
            }

            @media (prefers-reduced-motion: reduce) {
                .nova-selected-price b {
                    animation: none;
                }
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

            .yeb-journal-card {
                margin-bottom: 0.8rem;
            }

            .yeb-journal-top {
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 12px;
            }

            .yeb-journal-symbol {
                color: var(--nova-text);
                font-size: 1.05rem;
                font-weight: 850;
                overflow-wrap: anywhere;
            }

            .yeb-journal-pnl {
                border: 1px solid rgba(148, 163, 184, 0.22);
                border-radius: 8px;
                padding: 0.45rem 0.65rem;
                font-weight: 850;
                white-space: nowrap;
            }

            .yeb-journal-pnl.positive {
                background: rgba(34, 197, 94, 0.10);
                border-color: rgba(34, 197, 94, 0.30);
                color: var(--nova-green);
            }

            .yeb-journal-pnl.negative {
                background: rgba(239, 68, 68, 0.10);
                border-color: rgba(239, 68, 68, 0.30);
                color: var(--nova-red);
            }

            .yeb-journal-grid {
                display: grid;
                grid-template-columns: repeat(6, minmax(0, 1fr));
                gap: 8px;
                margin-top: 12px;
            }

            .yeb-journal-grid div {
                min-width: 0;
                border: 1px solid rgba(148, 163, 184, 0.14);
                border-radius: 8px;
                background: rgba(148, 163, 184, 0.07);
                padding: 10px;
            }

            .yeb-journal-grid span {
                display: block;
                color: var(--nova-muted);
                font-size: 0.66rem;
                letter-spacing: 0.06em;
                text-transform: uppercase;
                overflow-wrap: anywhere;
            }

            .yeb-journal-grid strong {
                display: block;
                color: var(--nova-text);
                font-size: 0.9rem;
                margin-top: 4px;
                overflow-wrap: anywhere;
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

                [data-testid="stHorizontalBlock"]:has(.nova-header-brand-marker) {
                    display: grid !important;
                    grid-template-columns: minmax(24px, 0.28fr) minmax(190px, 1fr) minmax(150px, 0.28fr);
                    gap: 8px !important;
                    align-items: center;
                }

                [data-testid="stHorizontalBlock"]:has(.nova-header-brand-marker) > [data-testid="column"] {
                    width: 100% !important;
                    min-width: 0 !important;
                    flex: initial !important;
                }

                [data-testid="stSidebar"] {
                    min-width: 0;
                    max-width: 100%;
                }

                .nova-pro-follow-detail {
                    grid-template-columns: 1fr;
                }

                .st-key-selected_page div[role="radiogroup"] {
                    grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
                    gap: 3px;
                    padding: 4px;
                    border-radius: 11px;
                }

                .st-key-selected_page label[data-baseweb="radio"] {
                    min-height: 44px;
                    padding: 7px 3px !important;
                    border-radius: 8px;
                }

                .st-key-selected_page label[data-baseweb="radio"] p,
                .st-key-selected_page label[data-baseweb="radio"] span,
                .st-key-selected_page label[data-baseweb="radio"] * {
                    font-size: 0.66rem;
                }

                .nova-pro-follow-value {
                    width: fit-content;
                    white-space: normal;
                }

                .yeb-journal-grid {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }

                .yeb-journal-top {
                    flex-direction: column;
                }
            }

            @media (max-width: 600px) {
                [data-testid="stHorizontalBlock"]:has(.nova-header-brand-marker) {
                    grid-template-columns: 8px minmax(150px, 1fr) minmax(112px, 0.48fr);
                }

                .st-key-account_menu,
                .st-key-account_menu > div,
                .st-key-account_menu button {
                    min-width: 112px !important;
                }

                .st-key-account_menu button p,
                .st-key-account_menu button span {
                    font-size: 0.68rem !important;
                }

                .nova-selected-asset {
                    grid-template-columns: 1fr 1fr;
                    gap: 10px;
                }

                .nova-selected-identity {
                    grid-column: 1 / -1;
                }
            }

            @media (min-width: 700px) and (max-width: 900px) {
                [data-testid="stMain"] {
                    margin-left: 300px;
                    width: calc(100% - 300px);
                }

                [data-testid="stMainBlockContainer"] {
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

                .dc-metric-card {
                    min-height: 68px;
                    padding: 10px 12px;
                }

                .yeb-journal-grid {
                    grid-template-columns: 1fr;
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
