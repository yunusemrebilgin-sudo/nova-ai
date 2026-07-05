DISCLAIMER = "Bu platform yalnızca karar destek amaçlıdır. Kesin yatırım tavsiyesi vermez."


def clamp_percent(value: float) -> int:
    return max(0, min(100, int(round(value))))


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value != value:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def format_number(value: float) -> str:
    return f"{value:,.2f}"
