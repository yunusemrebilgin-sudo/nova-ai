from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping
from pathlib import Path
import tempfile
from typing import Any

import requests


USERS: dict[str, dict[str, Any]] = {}
KNOWN_USERNAMES = {"demo", *(f"kullanici{index}" for index in range(1, 11))}

DATA_ROOT = Path("data/user_data")
SUPABASE_URL = ""
SUPABASE_SERVICE_ROLE_KEY = ""


class PersistenceError(RuntimeError):
    """Raised when live user data cannot be read from or written to Supabase."""


def configure_users(payload: Any) -> None:
    """Load credentials at runtime; passwords must never be committed to source."""
    global USERS
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {}
    configured = {}
    if isinstance(payload, Mapping):
        for username, value in payload.items():
            if not isinstance(value, Mapping) or not str(value.get("password", "")):
                continue
            normalized = normalize_username(str(username))
            if not normalized:
                continue
            configured[normalized] = {
                "password": str(value["password"]),
                "is_pro": bool(value.get("is_pro", False)),
            }
    USERS = configured


def users_configured() -> bool:
    return bool(USERS)


INCEPTION_COMPAT_KEY = "_nova_inception_kind"


def _decode_inception_compat(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    watchlist, decoded = [], {"inception_active": [], "inception_history": [], "inception_metadata": []}
    kind_to_field = {"active": "inception_active", "history": "inception_history", "metadata": "inception_metadata"}
    for row in rows:
        field = kind_to_field.get(str(row.get(INCEPTION_COMPAT_KEY, "")))
        value = row.get("data")
        if field and isinstance(value, dict):
            decoded[field].append(dict(value))
        else:
            watchlist.append(dict(row))
    return watchlist, decoded


def _encode_inception_compat(snapshot: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in snapshot["ai_watchlist"] if INCEPTION_COMPAT_KEY not in row]
    for field, kind in (("inception_active", "active"), ("inception_history", "history"), ("inception_metadata", "metadata")):
        rows.extend({INCEPTION_COMPAT_KEY: kind, "data": dict(value)} for value in snapshot[field])
    return rows


EMPTY_PORTFOLIO_DATA = {
    "open_positions": [],
    "closed_trades": [],
    "ai_watchlist": [],
    "inception_active": [],
    "inception_history": [],
    "inception_metadata": [],
}


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


def _require_known_username(username: str) -> str:
    normalized = normalize_username(username)
    if not normalized or (normalized not in KNOWN_USERNAMES and normalized not in USERS):
        raise ValueError("Tanımsız kullanıcı.")
    return normalized


def user_data_dir(username: str) -> Path:
    normalized = _require_known_username(username)
    path = DATA_ROOT / normalized
    path.mkdir(parents=True, exist_ok=True)
    return path


def _validate_list_payload(value: Any, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise PersistenceError(f"{field_name} verisi geçerli bir liste değil.")
    return [dict(item) for item in value]


def _json_safe(value: Any) -> Any:
    """Convert analytics values to strict JSON before sending them to PostgREST."""
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item") and callable(value.item):
        try:
            return _json_safe(value.item())
        except (TypeError, ValueError):
            pass
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.replace(temporary_path, path)
    except (OSError, TypeError, ValueError) as exc:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise PersistenceError("Kullanıcı verisi atomik olarak kaydedilemedi.") from exc


def load_user_list(username: str, file_name: str) -> list[dict[str, Any]]:
    path = user_data_dir(username) / file_name
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise PersistenceError(f"{file_name} okunamadı; mevcut veri korunuyor.") from exc
    return _validate_list_payload(data, file_name)


def save_user_list(username: str, file_name: str, rows: list[dict[str, Any]]) -> None:
    path = user_data_dir(username) / file_name
    _atomic_write_json(path, _validate_list_payload(rows, file_name))


def load_user_portfolio_data(username: str) -> dict[str, list[dict[str, Any]]]:
    normalized = _require_known_username(username)
    if supabase_enabled():
        try:
            storage_ready = True
            try:
                rows = _rest(
                    "user_portfolio_data",
                    params={"username": f"eq.{normalized}", "select": "open_positions,closed_trades,ai_watchlist,inception_active,inception_history,inception_metadata"},
                ).json()
            except requests.HTTPError:
                storage_ready = False
                rows = _rest(
                    "user_portfolio_data",
                    params={"username": f"eq.{normalized}", "select": "open_positions,closed_trades,ai_watchlist"},
                ).json()
            if not rows:
                return {**{key: [] for key in EMPTY_PORTFOLIO_DATA}, "inception_storage_ready": storage_ready}
            row = rows[0]
            raw_watchlist = _validate_list_payload(row.get("ai_watchlist"), "ai_watchlist")
            compat_watchlist, compat_data = _decode_inception_compat(raw_watchlist)
            return {
                "open_positions": _validate_list_payload(row.get("open_positions"), "open_positions"),
                "closed_trades": _validate_list_payload(row.get("closed_trades"), "closed_trades"),
                "ai_watchlist": compat_watchlist,
                "inception_active": _validate_list_payload(row.get("inception_active", compat_data["inception_active"]), "inception_active"),
                "inception_history": _validate_list_payload(row.get("inception_history", compat_data["inception_history"]), "inception_history"),
                "inception_metadata": _validate_list_payload(row.get("inception_metadata", compat_data["inception_metadata"]), "inception_metadata"),
                "inception_storage_ready": storage_ready,
                "inception_storage_mode": "columns" if storage_ready else "compat",
            }
        except (requests.RequestException, KeyError, TypeError, ValueError, PersistenceError) as exc:
            raise PersistenceError("Pozisyon ve takip verileri Supabase'den okunamadı; mevcut kayıtlar korunuyor.") from exc
    return {
        "open_positions": load_user_list(normalized, "open_positions.json"),
        "closed_trades": load_user_list(normalized, "closed_trades.json"),
        "ai_watchlist": load_user_list(normalized, "ai_watchlist.json"),
        "inception_active": load_user_list(normalized, "inception_active.json"),
        "inception_history": load_user_list(normalized, "inception_history.json"),
        "inception_metadata": load_user_list(normalized, "inception_metadata.json"),
        "inception_storage_ready": True,
    }


def save_user_portfolio_data(
    username: str,
    open_positions: list[dict[str, Any]],
    closed_trades: list[dict[str, Any]],
    ai_watchlist: list[dict[str, Any]],
    inception_active: list[dict[str, Any]] | None = None,
    inception_history: list[dict[str, Any]] | None = None,
    inception_metadata: list[dict[str, Any]] | None = None,
) -> None:
    normalized = _require_known_username(username)
    snapshot = _json_safe({
        "open_positions": _validate_list_payload(open_positions, "open_positions"),
        "closed_trades": _validate_list_payload(closed_trades, "closed_trades"),
        "ai_watchlist": _validate_list_payload(ai_watchlist, "ai_watchlist"),
        "inception_active": _validate_list_payload(inception_active or [], "inception_active"),
        "inception_history": _validate_list_payload(inception_history or [], "inception_history"),
        "inception_metadata": _validate_list_payload(inception_metadata or [], "inception_metadata"),
    })
    if supabase_enabled():
        try:
            _rest(
                "user_portfolio_data",
                "POST",
                payload={"username": normalized, **snapshot},
                prefer="resolution=merge-duplicates",
            )
            return
        except requests.HTTPError:
            try:
                _rest(
                    "user_portfolio_data", "POST",
                    payload={"username": normalized, "open_positions": snapshot["open_positions"],
                             "closed_trades": snapshot["closed_trades"], "ai_watchlist": _encode_inception_compat(snapshot)},
                    prefer="resolution=merge-duplicates",
                )
                return
            except requests.RequestException as exc:
                raise PersistenceError("Pozisyon ve takip verileri Supabase'e kaydedilemedi.") from exc
        except requests.RequestException as exc:
            raise PersistenceError("Pozisyon ve takip verileri Supabase'e kaydedilemedi.") from exc
    for key, file_name in (
        ("open_positions", "open_positions.json"),
        ("closed_trades", "closed_trades.json"),
        ("ai_watchlist", "ai_watchlist.json"),
        ("inception_active", "inception_active.json"),
        ("inception_history", "inception_history.json"),
        ("inception_metadata", "inception_metadata.json"),
    ):
        save_user_list(normalized, file_name, snapshot[key])


def load_open_positions(username: str) -> list[dict[str, Any]]:
    return load_user_portfolio_data(username)["open_positions"]


def save_open_positions(username: str, positions: list[dict[str, Any]]) -> None:
    current = load_user_portfolio_data(username)
    save_user_portfolio_data(username, positions, current["closed_trades"], current["ai_watchlist"], current["inception_active"], current["inception_history"], current["inception_metadata"])


def load_closed_trades(username: str) -> list[dict[str, Any]]:
    return load_user_portfolio_data(username)["closed_trades"]


def save_closed_trades(username: str, trades: list[dict[str, Any]]) -> None:
    current = load_user_portfolio_data(username)
    save_user_portfolio_data(username, current["open_positions"], trades, current["ai_watchlist"], current["inception_active"], current["inception_history"], current["inception_metadata"])


def load_ai_watchlist(username: str) -> list[dict[str, Any]]:
    """Return the private Pro watchlist belonging to one user."""
    return load_user_portfolio_data(username)["ai_watchlist"]


def save_ai_watchlist(username: str, watchlist: list[dict[str, Any]]) -> None:
    current = load_user_portfolio_data(username)
    save_user_portfolio_data(username, current["open_positions"], current["closed_trades"], watchlist, current["inception_active"], current["inception_history"], current["inception_metadata"])


def load_simulation(username: str) -> dict[str, Any]:
    normalized = _require_known_username(username)
    if supabase_enabled():
        try:
            _rest("rpc/rollover_simulation_weeks", "POST", payload={})
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
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            raise PersistenceError("Simülasyon verileri Supabase'den okunamadı.") from exc
    path = user_data_dir(username) / "simulation.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_simulation(username: str, simulation: dict[str, Any]) -> None:
    normalized = _require_known_username(username)
    if supabase_enabled() and simulation.get("week"):
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
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            raise PersistenceError("Simülasyon işlemi Supabase'e kaydedilemedi.") from exc
    path = user_data_dir(username) / "simulation.json"
    path.write_text(
        json.dumps(simulation, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
