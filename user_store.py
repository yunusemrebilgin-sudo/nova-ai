from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests


USERS = {
    "demo": {"password": "demo123", "is_pro": True},
    "kullanici1": {"password": "yeb2026-01", "is_pro": True},
    "kullanici2": {"password": "yeb2026-02", "is_pro": True},
    "kullanici3": {"password": "yeb2026-03", "is_pro": True},
    "kullanici4": {"password": "yeb2026-04", "is_pro": True},
    "kullanici5": {"password": "yeb2026-05", "is_pro": True},
    "kullanici6": {"password": "yeb2026-06", "is_pro": True},
    "kullanici7": {"password": "yeb2026-07", "is_pro": True},
    "kullanici8": {"password": "yeb2026-08", "is_pro": True},
    "kullanici9": {"password": "yeb2026-09", "is_pro": True},
    "kullanici10": {"password": "yeb2026-10", "is_pro": True},
}

DATA_ROOT = Path("data/user_data")
SUPABASE_URL = ""
SUPABASE_SERVICE_ROLE_KEY = ""


def configure_supabase(url: str, service_role_key: str) -> None:
    global SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
    SUPABASE_URL = str(url).strip().rstrip("/")
    SUPABASE_SERVICE_ROLE_KEY = str(service_role_key).strip()


def supabase_enabled() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def _supabase_headers(prefer: str | None = None) -> dict[str, str]:
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Content-Type": "application/json",
        "User-Agent": "NOVA-AI-Backend/1.0",
    }
    if not SUPABASE_SERVICE_ROLE_KEY.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _rest(table: str, method: str = "GET", *, params: dict[str, str] | None = None, payload: Any = None, prefer: str | None = None) -> requests.Response:
    response = requests.request(
        method,
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=_supabase_headers(prefer),
        params=params,
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return response


def normalize_username(username: str) -> str:
    return username.strip().lower()


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    normalized = normalize_username(username)
    clean_password = str(password).strip()
    user = USERS.get(normalized)
    if not user or clean_password != user["password"]:
        return None
    return {"username": normalized, "is_pro": bool(user.get("is_pro", False))}


def is_pro_user(username: str) -> bool:
    user = USERS.get(normalize_username(username))
    return bool(user and user.get("is_pro", False))


def user_data_dir(username: str) -> Path:
    normalized = normalize_username(username)
    if normalized not in USERS:
        raise ValueError("Tanımsız kullanıcı.")
    path = DATA_ROOT / normalized
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_user_list(username: str, file_name: str) -> list[dict[str, Any]]:
    path = user_data_dir(username) / file_name
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def save_user_list(username: str, file_name: str, rows: list[dict[str, Any]]) -> None:
    path = user_data_dir(username) / file_name
    path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_open_positions(username: str) -> list[dict[str, Any]]:
    return load_user_list(username, "open_positions.json")


def save_open_positions(username: str, positions: list[dict[str, Any]]) -> None:
    save_user_list(username, "open_positions.json", positions)


def load_closed_trades(username: str) -> list[dict[str, Any]]:
    return load_user_list(username, "closed_trades.json")


def save_closed_trades(username: str, trades: list[dict[str, Any]]) -> None:
    save_user_list(username, "closed_trades.json", trades)


def load_ai_watchlist(username: str) -> list[dict[str, Any]]:
    """Return the private Pro watchlist belonging to one user."""
    return load_user_list(username, "ai_watchlist.json")


def save_ai_watchlist(username: str, watchlist: list[dict[str, Any]]) -> None:
    save_user_list(username, "ai_watchlist.json", watchlist)


def load_simulation(username: str) -> dict[str, Any]:
    if supabase_enabled():
        normalized = normalize_username(username)
        try:
            accounts = _rest("simulation_accounts", params={"username": f"eq.{normalized}", "select": "*"}).json()
            if not accounts:
                return {}
            account = accounts[0]
            week_key = str(account["week_key"])
            positions = _rest("simulation_positions", params={"username": f"eq.{normalized}", "week_key": f"eq.{week_key}", "select": "*"}).json()
            trades = _rest("simulation_trades", params={"username": f"eq.{normalized}", "week_key": f"eq.{week_key}", "select": "*", "order": "executed_at.asc"}).json()
            archives = _rest("simulation_weekly_summaries", params={"username": f"eq.{normalized}", "select": "*", "order": "closed_at.asc"}).json()
            return {
                "week": week_key,
                "starting_cash": float(account["starting_cash"]),
                "cash": float(account["cash"]),
                "positions": [{"symbol": p["symbol"], "quantity": p["quantity"], "avg_price": float(p["avg_price"]), "stop_price": float(p["stop_price"]), "target_price": float(p["target_price"]), "last_price": float(p["last_price"] or p["avg_price"]), "bought_at": p["opened_at"]} for p in positions],
                "trades": [{"side": t["side"], "symbol": t["symbol"], "quantity": t["quantity"], "price": float(t["price"]), "total": float(t["total"]), "pnl": float(t["realized_pnl"] or 0), "reason": t["reason"], "time": t["executed_at"]} for t in trades],
                "archives": [{"week": a["week_key"], "ending_value": float(a["ending_value"]), "pnl": float(a["pnl"]), "pnl_pct": float(a["pnl_pct"]), "trade_count": a["trade_count"], "closed_at": a["closed_at"]} for a in archives],
            }
        except (requests.RequestException, KeyError, TypeError, ValueError):
            pass
    path = user_data_dir(username) / "simulation.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_simulation(username: str, simulation: dict[str, Any]) -> None:
    if supabase_enabled() and simulation.get("week"):
        normalized = normalize_username(username)
        week_key = str(simulation["week"])
        try:
            _rest("simulation_accounts", "POST", payload={"username": normalized, "week_key": week_key, "starting_cash": simulation.get("starting_cash", 10000), "cash": simulation.get("cash", 10000)}, prefer="resolution=merge-duplicates")
            for table in ("simulation_positions", "simulation_trades"):
                _rest(table, "DELETE", params={"username": f"eq.{normalized}", "week_key": f"eq.{week_key}"})
            positions = [{"username": normalized, "week_key": week_key, "symbol": p["symbol"], "quantity": p["quantity"], "avg_price": p["avg_price"], "stop_price": p["stop_price"], "target_price": p["target_price"], "last_price": p.get("last_price"), "opened_at": p.get("bought_at")} for p in simulation.get("positions", [])]
            if positions:
                _rest("simulation_positions", "POST", payload=positions)
            trades = [{"username": normalized, "week_key": week_key, "side": t["side"], "symbol": t["symbol"], "quantity": t["quantity"], "price": t["price"], "total": t["total"], "realized_pnl": t.get("pnl"), "reason": t.get("reason"), "executed_at": t.get("time")} for t in simulation.get("trades", [])]
            if trades:
                _rest("simulation_trades", "POST", payload=trades)
            for archive in simulation.get("archives", []):
                _rest("simulation_weekly_summaries", "POST", payload={"username": normalized, "week_key": archive["week"], "ending_value": archive["ending_value"], "pnl": archive["pnl"], "pnl_pct": archive["pnl_pct"], "trade_count": archive.get("trade_count", 0), "closed_at": archive.get("closed_at")}, prefer="resolution=merge-duplicates")
            return
        except (requests.RequestException, KeyError, TypeError, ValueError):
            pass
    path = user_data_dir(username) / "simulation.json"
    path.write_text(
        json.dumps(simulation, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
