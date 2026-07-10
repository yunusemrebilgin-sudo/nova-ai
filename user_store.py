from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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
