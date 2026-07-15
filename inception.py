from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd

SCHEMA_VERSION = 1
ISTANBUL_TIMEZONE = ZoneInfo("Europe/Istanbul")
HORIZON_DAYS = {"1-5 gün": 5, "Günlük işlem": 5, "5-10 gün": 10, "Kısa vade": 10,
                "10-30 gün": 30, "1-2 ay": 44, "Orta vade": 44, "2-4 ay": 88, "Uzun vade": 126}


def trading_days(start: str, end: datetime) -> int:
    try:
        first = pd.Timestamp(start).date()
    except (TypeError, ValueError):
        return 0
    return max(0, len(pd.bdate_range(first, end.date())) - 1)


def completed_market_sessions_since_added(raw_data: pd.DataFrame, added_at: str, updated_at: datetime) -> int:
    """Count completed exchange bars strictly after the tracking date."""
    try:
        added = pd.Timestamp(added_at)
        if added.tzinfo is None:
            added = added.tz_localize(ISTANBUL_TIMEZONE)
        else:
            added = added.tz_convert(ISTANBUL_TIMEZONE)
    except (TypeError, ValueError):
        return 0
    current = pd.Timestamp(updated_at)
    if current.tzinfo is None:
        current = current.tz_localize(ISTANBUL_TIMEZONE)
    else:
        current = current.tz_convert(ISTANBUL_TIMEZONE)
    index = pd.DatetimeIndex(raw_data.index)
    if index.tz is not None:
        index = index.tz_convert(ISTANBUL_TIMEZONE).tz_localize(None)
    session_dates = pd.DatetimeIndex(index).normalize().unique()
    completed_dates = [date for date in session_dates if date.date() > added.date()]
    current_session_is_incomplete = current.weekday() < 5 and current.hour < 18
    if current_session_is_incomplete:
        completed_dates = [date for date in completed_dates if date.date() < current.date()]
    return len(completed_dates)


def create_record(snapshot: dict, source: str, added_at: datetime) -> dict:
    symbol = str(snapshot["symbol"]).upper()
    critical_start = snapshot.get("critical_window_start")
    critical_end = snapshot.get("critical_window_end")
    if source == "Smart Scanner":
        try:
            critical_start, critical_end = int(critical_start), int(critical_end)
        except (TypeError, ValueError) as exc:
            raise ValueError("Smart Scanner Inception kaydı geçerli kritik pencere gerektirir.") from exc
        if critical_start < 1 or critical_end < critical_start:
            raise ValueError("Smart Scanner Inception kritik penceresi geçersizdir.")
    return {
        "id": uuid4().hex, "schema_version": SCHEMA_VERSION, "symbol": symbol,
        "source": source, "status": "active", "added_at": added_at.isoformat(),
        "market_data_time": snapshot.get("market_data_time"), "horizon": snapshot.get("horizon", "1-5 gün"),
        "initial": {
            "price": float(snapshot["price"]), "expected_return": float(snapshot["expected_return"]),
            "target_1": float(snapshot["target_1"]), "target_2": snapshot.get("target_2"),
            "stop_loss": float(snapshot["stop_loss"]), "nova_score": int(snapshot.get("nova_score", 0)),
            "confidence": int(snapshot.get("confidence", 0)), "indicators": dict(snapshot.get("indicators", {})),
            "sector": snapshot.get("sector", "Bilinmiyor"), "market_state": snapshot.get("market_state", "Bilinmiyor"),
            "critical_window_start": critical_start,
            "critical_window_end": critical_end,
        },
        "dynamic": {},
    }


def add_record(active: list[dict], snapshot: dict, source: str, added_at: datetime) -> tuple[list[dict], bool]:
    symbol = str(snapshot["symbol"]).upper()
    if any(str(row.get("symbol", "")).upper() == symbol and row.get("status", "active") == "active" for row in active):
        return active, False
    return [*active, create_record(snapshot, source, added_at)], True


def update_record(record: dict, row: dict, raw_data: pd.DataFrame, updated_at: datetime) -> dict:
    result = {**record, "initial": dict(record["initial"]), "dynamic": dict(record.get("dynamic", {}))}
    initial = result["initial"]
    price = float(row["Son Fiyat"])
    start_price = float(initial["price"])
    target = float(initial["target_1"])
    stop = float(initial["stop_loss"])
    highs = raw_data["High"].dropna().astype(float)
    lows = raw_data["Low"].dropna().astype(float)
    elapsed = completed_market_sessions_since_added(raw_data, result["added_at"], updated_at)
    horizon_days = HORIZON_DAYS.get(str(result.get("horizon")), 5)
    high = float(highs.max()) if not highs.empty else price
    low = float(lows.min()) if not lows.empty else price
    result["dynamic"] = {
        "price": price, "expected_return": float(row["Beklenen Getiri %"]), "technical_target": float(row["Direnç"]),
        "technical_view": row.get("Trend", "Nötr"), "return_pct": round((price / start_price - 1) * 100, 2),
        "target_progress_pct": round((price - start_price) / max(target - start_price, .0001) * 100, 2),
        "target_remaining_pct": round((target / price - 1) * 100, 2), "stop_remaining_pct": round((price / stop - 1) * 100, 2),
        "highest": high, "lowest": low, "max_favorable_pct": round((high / start_price - 1) * 100, 2),
        "max_adverse_pct": round((low / start_price - 1) * 100, 2), "elapsed_days": elapsed,
        "horizon_day": f"{min(elapsed, horizon_days)}/{horizon_days}", "remaining_days": max(0, horizon_days - elapsed),
        "nova_score": int(row["Nova Score"]), "confidence": int(row["AI Güven Endeksi"]),
        "updated_at": updated_at.isoformat(), "market_data_time": row.get("_market_data_time"), "data_status": "current",
        "target_touched": bool((highs >= target).any()), "stop_touched": bool((lows <= stop).any()),
    }
    if result["dynamic"]["target_touched"] and result["dynamic"]["stop_touched"]:
        result["dynamic"]["touch_order"] = "Aynı periyotta hedef ve stop teması; sıralama belirsiz"
    return result


def complete_record(record: dict, reason: str, completed_at: datetime) -> dict:
    result = {**record, "status": "completed", "completed_at": completed_at.isoformat(), "completion_reason": reason}
    dynamic, initial = result.get("dynamic", {}), result["initial"]
    actual = float(dynamic.get("return_pct", 0))
    result["outcome"] = {
        "end_price": dynamic.get("price", initial["price"]), "highest": dynamic.get("highest"), "lowest": dynamic.get("lowest"),
        "max_favorable_pct": dynamic.get("max_favorable_pct", 0), "max_adverse_pct": dynamic.get("max_adverse_pct", 0),
        "target_reached": bool(dynamic.get("target_touched")), "stop_reached": bool(dynamic.get("stop_touched")),
        "actual_return": actual, "initial_expected_return": initial["expected_return"],
        "expected_actual_gap": round(float(initial["expected_return"]) - actual, 2),
        "result_class": "positive" if actual > 0 else "negative" if actual < 0 else "neutral",
        "touch_order": dynamic.get("touch_order"),
    }
    return result


def automatic_completion_reason(record: dict) -> str | None:
    dynamic = record.get("dynamic", {})
    if dynamic.get("target_touched") and dynamic.get("stop_touched"):
        return "Aynı periyotta hedef ve stop teması; sıralama belirsiz"
    if dynamic.get("target_touched"):
        return "İlk hedef gerçekleşti"
    if dynamic.get("stop_touched"):
        return "Stop seviyesi gerçekleşti"
    if dynamic.get("remaining_days") == 0:
        return "Vade sona erdi"
    return None


def report_metrics(history: list[dict], active_count: int = 0) -> dict:
    rows = [r for r in history if r.get("outcome")]
    def avg(values): return round(sum(values) / len(values), 2) if values else 0.0
    total = len(rows)
    target = sum(bool(r["outcome"].get("target_reached")) for r in rows)
    positive = sum(float(r["outcome"].get("actual_return", 0)) > 0 for r in rows)
    negative = sum(float(r["outcome"].get("actual_return", 0)) < 0 for r in rows)
    stop = sum(bool(r["outcome"].get("stop_reached")) for r in rows)
    return {"total": total, "active": active_count, "target_count": target, "target_rate": round(target / total * 100, 1) if total else 0,
            "positive_count": positive, "positive_rate": round(positive / total * 100, 1) if total else 0,
            "negative_count": negative, "negative_rate": round(negative / total * 100, 1) if total else 0,
            "stop_rate": round(stop / total * 100, 1) if total else 0,
            "expired_count": sum(r.get("completion_reason") == "Vade sona erdi" for r in rows),
            "avg_expected": avg([float(r["outcome"].get("initial_expected_return", 0)) for r in rows]),
            "avg_actual": avg([float(r["outcome"].get("actual_return", 0)) for r in rows]),
            "avg_gap": avg([float(r["outcome"].get("expected_actual_gap", 0)) for r in rows]),
            "avg_absolute_deviation": avg([abs(float(r["outcome"].get("expected_actual_gap", 0))) for r in rows]),
            "avg_favorable": avg([float(r["outcome"].get("max_favorable_pct", 0)) for r in rows]),
            "avg_adverse": avg([float(r["outcome"].get("max_adverse_pct", 0)) for r in rows]),
            "avg_target_days": avg([float(r.get("dynamic", {}).get("elapsed_days", 0)) for r in rows if r["outcome"].get("target_reached")]),
            "direction_accuracy": round(sum(float(r["outcome"].get("actual_return", 0)) > 0 for r in rows) / total * 100, 1) if total else 0}


def group_metrics(history: list[dict], key) -> list[dict]:
    groups = {}
    for record in history:
        groups.setdefault(key(record), []).append(record)
    return [{"Grup": name, **report_metrics(records)} for name, records in sorted(groups.items())]
