import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app
import user_store


class FakeResponse:
    def __init__(self, payload=None):
        self.payload = payload

    def json(self):
        return copy.deepcopy(self.payload)


class SupabasePortfolioBackend:
    def __init__(self):
        self.rows = {}
        self.calls = []

    def request(self, table, method="GET", *, params=None, payload=None, prefer=None):
        self.calls.append((table, method, copy.deepcopy(params), copy.deepcopy(payload), prefer))
        if table != "user_portfolio_data":
            return FakeResponse([])
        if method == "GET":
            username = str(params["username"]).removeprefix("eq.")
            row = self.rows.get(username)
            return FakeResponse([] if row is None else [row])
        if method == "POST":
            self.rows[payload["username"]] = {
                "open_positions": copy.deepcopy(payload["open_positions"]),
                "closed_trades": copy.deepcopy(payload["closed_trades"]),
                "ai_watchlist": copy.deepcopy(payload["ai_watchlist"]),
            }
            return FakeResponse(None)
        raise AssertionError(f"Unexpected method: {method}")


class UserPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.original_root = user_store.DATA_ROOT
        self.original_url = user_store.SUPABASE_URL
        self.original_key = user_store.SUPABASE_SERVICE_ROLE_KEY

    def tearDown(self):
        user_store.DATA_ROOT = self.original_root
        user_store.configure_supabase(self.original_url, self.original_key)

    def test_credentials_are_runtime_configured_not_hardcoded(self):
        source = Path(user_store.__file__).read_text(encoding="utf-8")
        self.assertNotIn("demo123", source)
        self.assertNotIn("yeb2026-", source)
        user_store.configure_users({"demo": {"password": "runtime-secret", "is_pro": True}})
        self.assertEqual(user_store.authenticate("demo", "runtime-secret")["username"], "demo")

    def test_records_survive_application_restart(self):
        backend = SupabasePortfolioBackend()
        user_store.configure_supabase("https://example.supabase.co", "sb_secret_test")
        with patch("user_store._rest", side_effect=backend.request):
            user_store.save_user_portfolio_data(
                "kullanici1", [{"id": "p1"}], [{"id": "c1"}], [{"symbol": "AEFES.IS"}]
            )
            user_store.configure_supabase("", "")
            user_store.configure_supabase("https://example.supabase.co", "sb_secret_test")
            loaded = user_store.load_user_portfolio_data("kullanici1")
        self.assertEqual(loaded["open_positions"], [{"id": "p1"}])
        self.assertEqual(loaded["ai_watchlist"], [{"symbol": "AEFES.IS"}])

    def test_deploy_like_restart_does_not_depend_on_local_files(self):
        backend = SupabasePortfolioBackend()
        backend.rows["kullanici1"] = {
            "open_positions": [{"id": "remote"}], "closed_trades": [], "ai_watchlist": []
        }
        with tempfile.TemporaryDirectory() as first_root, tempfile.TemporaryDirectory() as second_root:
            user_store.configure_supabase("https://example.supabase.co", "sb_secret_test")
            with patch("user_store._rest", side_effect=backend.request):
                user_store.DATA_ROOT = Path(first_root)
                first = user_store.load_user_portfolio_data("kullanici1")
                user_store.DATA_ROOT = Path(second_root)
                second = user_store.load_user_portfolio_data("kullanici1")
        self.assertEqual(first, second)
        self.assertEqual(second["open_positions"], [{"id": "remote"}])

    def test_empty_initial_load_does_not_write_over_existing_data(self):
        backend = SupabasePortfolioBackend()
        backend.rows["kullanici1"] = {
            "open_positions": [{"id": "keep"}], "closed_trades": [], "ai_watchlist": []
        }
        user_store.configure_supabase("https://example.supabase.co", "sb_secret_test")
        with patch("user_store._rest", side_effect=backend.request):
            loaded = user_store.load_user_portfolio_data("kullanici1")
        self.assertEqual(loaded["open_positions"], [{"id": "keep"}])
        self.assertFalse(any(call[1] == "POST" for call in backend.calls))

    def test_corrupt_local_data_raises_without_deleting_file(self):
        user_store.configure_supabase("", "")
        with tempfile.TemporaryDirectory() as root:
            user_store.DATA_ROOT = Path(root)
            path = user_store.user_data_dir("kullanici1") / "open_positions.json"
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(user_store.PersistenceError):
                user_store.load_user_portfolio_data("kullanici1")
            self.assertEqual(path.read_text(encoding="utf-8"), "{broken")

    def test_add_update_and_delete_snapshot(self):
        backend = SupabasePortfolioBackend()
        user_store.configure_supabase("https://example.supabase.co", "sb_secret_test")
        with patch("user_store._rest", side_effect=backend.request):
            user_store.save_user_portfolio_data("kullanici1", [{"id": "p1", "quantity": 1}], [], [])
            user_store.save_user_portfolio_data(
                "kullanici1", [{"id": "p1", "quantity": 2}], [], [{"symbol": "AKBNK.IS"}]
            )
            user_store.save_user_portfolio_data("kullanici1", [], [{"id": "closed-p1"}], [])
            loaded = user_store.load_user_portfolio_data("kullanici1")
        self.assertEqual(loaded["open_positions"], [])
        self.assertEqual(loaded["closed_trades"], [{"id": "closed-p1"}])
        self.assertEqual(loaded["ai_watchlist"], [])

    def test_local_fallback_write_is_atomic_and_backward_compatible(self):
        user_store.configure_supabase("", "")
        with tempfile.TemporaryDirectory() as root:
            user_store.DATA_ROOT = Path(root)
            position = {"id": "p1", "Hisse": "AEFES.IS", "legacy_field": "preserved"}
            user_store.save_user_portfolio_data("kullanici1", [position], [], [])
            loaded = user_store.load_user_portfolio_data("kullanici1")
            files = list((Path(root) / "kullanici1").iterdir())
        self.assertEqual(loaded["open_positions"], [position])
        self.assertTrue(all(not path.name.endswith(".tmp") for path in files))

    def test_app_load_error_does_not_replace_existing_session_records(self):
        session = AttributeSession({
            "yeb_data_user": "", "yeb_persistent_data_loaded": False,
            "yeb_open_positions": [{"id": "keep"}], "yeb_closed_trades": [],
            "yeb_ai_watchlist": [{"symbol": "KEEP.IS"}],
        })
        fake_st = FakeStreamlit(session)
        with patch.object(app, "st", fake_st), patch.object(app, "current_auth_user", return_value="kullanici1"), patch.object(
            user_store, "load_user_portfolio_data", side_effect=user_store.PersistenceError("read failed")
        ):
            with self.assertRaises(StopSignal):
                app.load_current_user_pro_data()
        self.assertEqual(session["yeb_open_positions"], [{"id": "keep"}])
        self.assertEqual(session["yeb_ai_watchlist"], [{"symbol": "KEEP.IS"}])

    def test_app_does_not_save_before_successful_load(self):
        session = AttributeSession({
            "yeb_persistent_data_loaded": False, "yeb_open_positions": [],
            "yeb_closed_trades": [], "yeb_ai_watchlist": [],
        })
        fake_st = FakeStreamlit(session)
        with patch.object(app, "st", fake_st), patch.object(app, "current_auth_user", return_value="kullanici1"), patch.object(
            user_store, "save_user_portfolio_data"
        ) as save:
            with self.assertRaises(StopSignal):
                app.save_current_user_pro_data()
        save.assert_not_called()


class AttributeSession(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class StopSignal(RuntimeError):
    pass


class FakeStreamlit:
    def __init__(self, session):
        self.session_state = session
        self.secrets = {"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_test"}
        self.errors = []

    def error(self, message):
        self.errors.append(message)

    def stop(self):
        raise StopSignal()


if __name__ == "__main__":
    unittest.main()
