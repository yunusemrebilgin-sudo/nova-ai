import copy
import json
from pathlib import Path
import tempfile
import unittest
from types import MappingProxyType
from unittest.mock import MagicMock, patch

import app
import user_store


class FakeResponse:
    def __init__(self, payload=None):
        self.payload = payload

    def json(self):
        return copy.deepcopy(self.payload)


class SessionState(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


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
            username = payload["username"]
            row = self.rows.setdefault(username, {})
            row.update({key: copy.deepcopy(value) for key, value in payload.items() if key != "username"})
            return FakeResponse(None)
        raise AssertionError(f"Unexpected method: {method}")


class UserPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.original_root = user_store.DATA_ROOT
        self.original_url = user_store.SUPABASE_URL
        self.original_key = user_store.SUPABASE_SERVICE_ROLE_KEY
        self.original_users = copy.deepcopy(user_store.USERS)
        user_store.configure_users({
            "kullanici1": {"password": "existing-secret", "is_pro": True},
            "user1": {"password": "new-user-secret", "is_pro": True},
        })

    def tearDown(self):
        user_store.DATA_ROOT = self.original_root
        user_store.configure_supabase(self.original_url, self.original_key)
        user_store.USERS = self.original_users

    def test_credentials_are_runtime_configured_not_hardcoded(self):
        source = Path(user_store.__file__).read_text(encoding="utf-8")
        self.assertNotIn("demo123", source)
        self.assertNotIn("yeb2026-", source)
        user_store.configure_users({"demo": {"password": "runtime-secret", "is_pro": True}})
        self.assertEqual(user_store.authenticate("demo", "runtime-secret")["username"], "demo")

    def test_streamlit_mapping_secrets_are_accepted(self):
        users = MappingProxyType({"kullanici1": MappingProxyType({"password": "runtime-secret", "is_pro": True})})
        user_store.configure_users(users)
        self.assertIsNotNone(user_store.authenticate("kullanici1", "runtime-secret"))

    def test_blank_secret_username_is_not_configured(self):
        user_store.configure_users({"  ": {"password": "runtime-secret", "is_pro": True}})
        self.assertNotIn("", user_store.USERS)

    def test_new_configured_pro_user_without_supabase_row_gets_empty_snapshot(self):
        backend = SupabasePortfolioBackend()
        user_store.configure_supabase("https://example.supabase.co", "sb_secret_test")
        with patch("user_store._rest", side_effect=backend.request):
            loaded = user_store.load_user_portfolio_data("user1")

        self.assertTrue(user_store.authenticate("user1", "new-user-secret")["is_pro"])
        for key in user_store.EMPTY_PORTFOLIO_DATA:
            self.assertEqual(loaded[key], [])
        self.assertFalse(any(call[1] == "POST" for call in backend.calls))

    def test_empty_and_unconfigured_usernames_remain_rejected(self):
        for username in ("", "   ", "not-in-secrets"):
            with self.subTest(username=username):
                with self.assertRaises(ValueError):
                    user_store.load_user_portfolio_data(username)
                with self.assertRaises(ValueError):
                    user_store.load_simulation(username)

    def test_unauthenticated_session_cannot_supply_persistence_username(self):
        state = self.logout_state(is_authenticated=False, auth_user="user1")
        with (
            patch.object(app.st, "session_state", state),
            patch.object(user_store, "load_user_portfolio_data") as load_data,
        ):
            self.assertEqual(app.current_auth_user(), "")
            app.load_current_user_pro_data()

        load_data.assert_not_called()

    def test_new_user_can_save_after_first_load_and_read_snapshot_again(self):
        backend = SupabasePortfolioBackend()
        user_store.configure_supabase("https://example.supabase.co", "sb_secret_test")
        with patch("user_store._rest", side_effect=backend.request):
            initial = user_store.load_user_portfolio_data("user1")
            user_store.save_user_portfolio_data(
                "user1", [{"id": "user1-position"}], [], [], [], [], []
            )
            reloaded = user_store.load_user_portfolio_data("user1")

        self.assertEqual(initial["open_positions"], [])
        self.assertEqual(reloaded["open_positions"], [{"id": "user1-position"}])
        post = next(call for call in backend.calls if call[1] == "POST")
        self.assertEqual(post[4], "resolution=merge-duplicates")

    def test_new_and_existing_user_snapshots_remain_isolated(self):
        backend = SupabasePortfolioBackend()
        backend.rows["kullanici1"] = {
            "open_positions": [{"id": "existing-position"}],
            "closed_trades": [],
            "ai_watchlist": [],
            "schema_version": 2,
        }
        user_store.configure_supabase("https://example.supabase.co", "sb_secret_test")
        with patch("user_store._rest", side_effect=backend.request):
            existing_before = user_store.load_user_portfolio_data("kullanici1")
            user_store.save_user_portfolio_data(
                "user1", [{"id": "new-user-position"}], [], [], [], [], []
            )
            existing_after = user_store.load_user_portfolio_data("kullanici1")
            new_user = user_store.load_user_portfolio_data("user1")

        self.assertEqual(existing_before["open_positions"], [{"id": "existing-position"}])
        self.assertEqual(existing_after["open_positions"], [{"id": "existing-position"}])
        self.assertEqual(new_user["open_positions"], [{"id": "new-user-position"}])
        self.assertEqual(backend.rows["kullanici1"]["schema_version"], 2)

    def logout_state(self, **overrides):
        state = SessionState(
            is_authenticated=True,
            auth_user="user1",
            yeb_pro_active=True,
            yeb_data_user="user1",
            yeb_persistent_data_loaded=True,
            yeb_pro_module="Trade Journal",
            yeb_open_positions=[{"symbol": "TEST.IS"}],
            yeb_closed_trades=[{"symbol": "OLD.IS"}],
            yeb_ai_watchlist=[{"symbol": "WATCH.IS"}],
            yeb_simulation={"balance": 1000},
            inception_active=[{"symbol": "TEST.IS"}],
            inception_history=[{"symbol": "OLD.IS"}],
            inception_metadata=[{"kind": "update"}],
            login_username="user1",
            login_password="temporary-password",
            inception_storage_ready=True,
            inception_storage_mode="columns",
            inception_visit_id="visit",
            inception_last_attempt_visit="attempt",
            portfolio_ranked_results={"private": True},
            portfolio_results_cache_key="user1-cache",
            selected_page=app.PUBLIC_DASHBOARD_PAGE,
        )
        state.update(overrides)
        return state

    def test_logout_with_cookie_starts_client_delete_without_immediate_rerun(self):
        state = self.logout_state()
        with (
            patch.object(app.st, "session_state", state),
            patch.object(app, "COOKIE_MANAGER") as cookie_manager,
            patch.object(app.st, "rerun") as rerun,
            patch.object(app.st, "stop") as stop,
            patch.object(user_store, "save_user_portfolio_data") as save_data,
        ):
            app.logout_current_user()

        self.assertTrue(state["logout_in_progress"])
        self.assertEqual(state["logout_request_id"], 1)
        self.assertFalse(state["is_authenticated"])
        self.assertEqual(state["auth_user"], "")
        self.assertFalse(state["yeb_pro_active"])
        self.assertEqual(state["yeb_data_user"], "")
        self.assertFalse(state["yeb_persistent_data_loaded"])
        self.assertEqual(state["yeb_pro_module"], app.DEFAULT_PRO_MODULE)
        for key in ("yeb_open_positions", "yeb_closed_trades", "yeb_ai_watchlist", "inception_active", "inception_history", "inception_metadata"):
            self.assertEqual(state[key], [])
        self.assertEqual(state["yeb_simulation"], {})
        for key in ("login_username", "login_password", "inception_storage_ready", "inception_storage_mode", "inception_visit_id", "inception_last_attempt_visit", "portfolio_ranked_results", "portfolio_results_cache_key"):
            self.assertNotIn(key, state)
        self.assertEqual(state["selected_page"], app.SMART_SCANNER_PAGE)
        cookie_manager.delete.assert_called_once_with(app.AUTH_COOKIE_NAME, key="logout_cookie_1_1")
        stop.assert_called_once_with()
        rerun.assert_not_called()
        save_data.assert_not_called()

    def test_logout_without_cached_cookie_still_emits_browser_delete(self):
        state = self.logout_state()
        with (
            patch.object(app.st, "session_state", state),
            patch.object(app, "COOKIE_MANAGER") as cookie_manager,
            patch.object(app.st, "stop") as stop,
        ):
            cookie_manager.delete.side_effect = KeyError(app.AUTH_COOKIE_NAME)
            app.logout_current_user()

        cookie_manager.delete.assert_called_once_with(app.AUTH_COOKIE_NAME, key="logout_cookie_1_1")
        self.assertTrue(state["logout_in_progress"])
        stop.assert_called_once_with()

    def test_logout_component_rerun_finishes_cleanup_and_reruns_app(self):
        state = self.logout_state(
            is_authenticated=False,
            auth_user="",
            logout_in_progress=True,
            logout_request_id=3,
            logout_delete_attempt=1,
        )
        with (
            patch.object(app.st, "session_state", state),
            patch.object(app, "COOKIE_MANAGER") as cookie_manager,
            patch.object(app.st, "rerun") as rerun,
        ):
            cookie_manager.get.return_value = None
            self.assertTrue(app.complete_pending_logout())

        self.assertNotIn("logout_in_progress", state)
        self.assertNotIn("logout_delete_attempt", state)
        self.assertEqual(state["selected_page"], app.SMART_SCANNER_PAGE)
        rerun.assert_called_once_with()

    def test_refresh_cannot_restore_old_cookie_while_logout_is_pending(self):
        state = self.logout_state(
            is_authenticated=False,
            auth_user="",
            logout_in_progress=True,
            logout_request_id=4,
            logout_delete_attempt=1,
        )
        with (
            patch.object(app.st, "session_state", state),
            patch.object(app, "COOKIE_MANAGER") as cookie_manager,
            patch.object(app, "validate_auth_session_token") as validate_token,
            patch.object(app.st, "stop") as stop,
        ):
            cookie_manager.get.return_value = "old-valid-cookie"
            app.restore_persistent_session()
            self.assertTrue(app.complete_pending_logout())

        validate_token.assert_not_called()
        cookie_manager.delete.assert_called_once_with(app.AUTH_COOKIE_NAME, key="logout_cookie_4_2")
        self.assertFalse(state["is_authenticated"])
        self.assertEqual(state["auth_user"], "")
        self.assertTrue(state["logout_in_progress"])
        stop.assert_called_once_with()

    def test_different_user_can_login_after_completed_logout(self):
        user_store.configure_users(
            {
                "user1": {"password": "first-secret", "is_pro": True},
                "kullanici1": {"password": "second-secret", "is_pro": False},
            }
        )
        state = self.logout_state(
            is_authenticated=False,
            auth_user="",
            login_username="kullanici1",
            login_password="second-secret",
        )
        state.pop("logout_in_progress", None)
        form_context = MagicMock()
        with (
            patch.object(app.st, "session_state", state),
            patch.object(app.st, "title"),
            patch.object(app.st, "markdown"),
            patch.object(app.st, "form", return_value=form_context),
            patch.object(app.st, "text_input", side_effect=["kullanici1", "second-secret"]),
            patch.object(app.st, "form_submit_button", return_value=True),
            patch.object(app, "COOKIE_MANAGER") as cookie_manager,
            patch.object(app, "load_current_user_pro_data"),
            patch.object(app.st, "success"),
            patch.object(app.st, "rerun"),
        ):
            self.assertTrue(app.render_login_page())

        self.assertTrue(state["is_authenticated"])
        self.assertEqual(state["auth_user"], "kullanici1")
        self.assertFalse(state["yeb_pro_active"])
        cookie_manager.set.assert_called_once()
        self.assertEqual(cookie_manager.set.call_args.args[0], app.AUTH_COOKIE_NAME)

    def test_inception_compat_storage_preserves_watchlist_and_round_trips(self):
        snapshot = {
            "ai_watchlist": [{"symbol": "LEGACY.IS"}],
            "inception_active": [{"id": "active-1", "symbol": "ASTOR.IS"}],
            "inception_history": [{"id": "history-1"}],
            "inception_metadata": [{"kind": "update"}],
        }
        encoded = user_store._encode_inception_compat(snapshot)
        watchlist, decoded = user_store._decode_inception_compat(encoded)
        self.assertEqual(watchlist, snapshot["ai_watchlist"])
        self.assertEqual(decoded["inception_active"], snapshot["inception_active"])
        self.assertEqual(decoded["inception_history"], snapshot["inception_history"])
        self.assertEqual(decoded["inception_metadata"], snapshot["inception_metadata"])

    def test_supabase_snapshot_is_strict_json_safe(self):
        backend = SupabasePortfolioBackend()
        user_store.configure_supabase("https://example.supabase.co", "sb_secret_test")
        with patch("user_store._rest", side_effect=backend.request):
            user_store.save_user_portfolio_data(
                "kullanici1", [], [], [],
                [{"symbol": "ASTOR.IS", "initial": {"rsi": float("nan")}}], [], [],
            )
        payload = backend.calls[-1][3]
        self.assertIsNone(payload["inception_active"][0]["initial"]["rsi"])
        json.dumps(payload, allow_nan=False)

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

    def test_simulation_failure_does_not_cancel_successful_inception_save(self):
        session = AttributeSession({
            "yeb_persistent_data_loaded": True, "yeb_open_positions": [],
            "yeb_closed_trades": [], "yeb_ai_watchlist": [],
            "inception_active": [{"symbol": "ASTOR.IS"}], "inception_history": [],
            "inception_metadata": [], "yeb_simulation": {"week": "2026-W29"},
        })
        fake_st = FakeStreamlit(session)
        with patch.object(app, "st", fake_st), patch.object(app, "current_auth_user", return_value="kullanici1"), patch.object(
            user_store, "save_user_portfolio_data"
        ) as save_portfolio, patch.object(
            user_store, "save_simulation", side_effect=user_store.PersistenceError("simulation failed")
        ):
            app.save_current_user_pro_data()
        save_portfolio.assert_called_once()
        self.assertEqual(len(fake_st.warnings), 1)
        self.assertEqual(fake_st.errors, [])


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
        self.warnings = []

    def error(self, message):
        self.errors.append(message)

    def warning(self, message):
        self.warnings.append(message)

    def stop(self):
        raise StopSignal()


if __name__ == "__main__":
    unittest.main()
