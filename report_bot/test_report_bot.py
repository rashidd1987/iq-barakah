import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from report_bot.approvals import ApprovalStore
from report_bot.config import load_config
from report_bot.council import CouncilContext, council_views, select_project
from report_bot.monitor import (
    ProjectState,
    StateStore,
    token_expiry_reminder,
    transition_messages,
)
from report_bot.main import (
    BOT_COMMANDS,
    approval_auth_ok,
    council_keyboard,
    pwa_release_keyboard,
)
from report_bot.projects import PROJECTS, ProjectRegistry, validate_project
from report_bot.status import StatusClient, format_datetime, run_icon


class ConfigTests(unittest.TestCase):
    def test_requires_bot_token(self) -> None:
        with patch.dict(
            os.environ,
            {"OWNER_TELEGRAM_IDS": "140700248"},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "TELEGRAM_BOT_TOKEN"):
                load_config()

    def test_requires_numeric_owner_ids(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "test-token",
                "OWNER_TELEGRAM_IDS": "not-a-number",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "numeric"):
                load_config()

    def test_loads_multiple_owner_ids(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "test-token",
                "OWNER_TELEGRAM_IDS": "140700248, 42",
            },
            clear=True,
        ):
            config = load_config()
        self.assertEqual(config.owner_ids, frozenset({140700248, 42}))

    def test_rejects_too_frequent_monitoring(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "test-token",
                "OWNER_TELEGRAM_IDS": "42",
                "MONITOR_INTERVAL_SECONDS": "10",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "at least 60"):
                load_config()

    def test_loads_github_token_expiry(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "test-token",
                "OWNER_TELEGRAM_IDS": "42",
                "GITHUB_TOKEN_EXPIRES_AT": "2026-10-23",
            },
            clear=True,
        ):
            config = load_config()
        self.assertEqual(config.github_token_expires_at, date(2026, 10, 23))

    def test_rejects_invalid_github_token_expiry(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "test-token",
                "OWNER_TELEGRAM_IDS": "42",
                "GITHUB_TOKEN_EXPIRES_AT": "23.10.2026",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "YYYY-MM-DD"):
                load_config()

    def test_loads_optional_ai_provider_secrets_without_requiring_them(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "test-token",
                "OWNER_TELEGRAM_IDS": "42",
                "OPENAI_API_KEY": "openai-secret",
                "XAI_API_KEY": "xai-secret",
                "KIMI_API_KEY": "kimi-secret",
            },
            clear=True,
        ):
            config = load_config()

        self.assertEqual(
            config.ai_provider_secrets.configured_providers(),
            ("openai", "xai", "kimi"),
        )
        self.assertNotIn("openai-secret", repr(config.ai_provider_secrets))


class FormattingTests(unittest.TestCase):
    def test_run_icons(self) -> None:
        self.assertEqual(run_icon("success", "completed"), "✅")
        self.assertEqual(run_icon("failure", "completed"), "❌")
        self.assertEqual(run_icon(None, "in_progress"), "⏳")

    def test_invalid_datetime_is_safe(self) -> None:
        self.assertEqual(format_datetime("invalid"), "нет данных")


class ApprovalAuthTests(unittest.TestCase):
    def test_valid_secret_is_accepted(self) -> None:
        request = SimpleNamespace(headers={"Authorization": "Bearer safe-secret"})
        self.assertTrue(approval_auth_ok(request, "safe-secret"))

    def test_non_ascii_invalid_secret_is_rejected_without_error(self) -> None:
        request = SimpleNamespace(headers={"Authorization": "Bearer неверный"})
        self.assertFalse(approval_auth_ok(request, "safe-secret"))


class ReleaseControlTests(unittest.TestCase):
    def test_pwa_release_confirmation_has_start_and_cancel(self) -> None:
        keyboard = pwa_release_keyboard()
        callbacks = {
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
        }
        self.assertEqual(
            callbacks,
            {"release:pwa:start", "release:pwa:cancel"},
        )


class OwnerCouncilTests(unittest.TestCase):
    def test_council_is_registered_in_bot_commands(self) -> None:
        commands = [item.command for item in BOT_COMMANDS]
        self.assertIn("council", commands)
        self.assertEqual(len(commands), len(set(commands)))

    def test_selects_named_project_and_defaults_safely(self) -> None:
        self.assertEqual(
            select_project("Проверь Mizan Life", PROJECTS).key,
            "mizanlife",
        )
        self.assertEqual(
            select_project("Предложи следующий приоритет", PROJECTS).key,
            "iqbarakah",
        )

    def test_council_contains_business_product_security_and_critic(self) -> None:
        context = CouncilContext(
            project=PROJECTS[0],
            site_ok=True,
            status_code=200,
            latest_workflow="Quality checks",
            latest_status="success",
        )
        roles = {view.role for view in council_views("Улучшить продукт", context)}
        self.assertTrue(
            {
                "CEO · стратегия",
                "CTO · технологии",
                "CPO · продукт",
                "CMO · маркетинг",
                "CCO · клиентский опыт",
                "CFO · экономика",
                "CISO · служба безопасности",
                "COO · операции",
                "Data/DPO · данные",
                "Красная команда · критик",
            }.issubset(roles)
        )

    def test_council_keyboard_exposes_only_whitelisted_actions(self) -> None:
        keyboard = council_keyboard("iqbarakah")
        callbacks = {
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
        }
        self.assertEqual(
            callbacks,
            {
                "council:inspect:iqbarakah",
                "council:pwa:iqbarakah",
                "council:cancel:iqbarakah",
            },
        )
        self.assertFalse(any("shell" in callback for callback in callbacks))


class _FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


class _FakeSession:
    def __init__(self, status: int) -> None:
        self.status = status
        self.last_post: tuple[str, dict[str, object]] | None = None

    def post(self, url: str, **kwargs):
        self.last_post = (url, kwargs)
        return _FakeResponse(self.status)


class WorkflowDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_dispatches_only_declared_workflow_inputs(self) -> None:
        session = _FakeSession(204)
        client = StatusClient(session, "owner", "token")
        result = await client.dispatch_workflow(
            "repo",
            "release-pwa.yml",
            ref="main",
            inputs={"target": "production"},
        )
        self.assertEqual(result, "started")
        assert session.last_post is not None
        url, kwargs = session.last_post
        self.assertEqual(
            url,
            "https://api.github.com/repos/owner/repo/actions/workflows/"
            "release-pwa.yml/dispatches",
        )
        self.assertEqual(
            kwargs["json"],
            {"ref": "main", "inputs": {"target": "production"}},
        )

    async def test_reports_missing_actions_permission(self) -> None:
        client = StatusClient(_FakeSession(403), "owner", "token")
        result = await client.dispatch_workflow(
            "repo",
            "release-pwa.yml",
            ref="main",
            inputs={},
        )
        self.assertEqual(result, "unauthorized")

    async def test_reviews_only_production_pending_deployment(self) -> None:
        session = _FakeSession(200)
        client = StatusClient(session, "owner", "token")
        client._github_get = AsyncMock(
            return_value=[
                {"environment": {"id": 17, "name": "production"}},
                {"environment": {"id": 18, "name": "preview"}},
            ]
        )
        result = await client.review_pending_deployment(
            "repo",
            123,
            approved=True,
        )
        self.assertEqual(result, "reviewed")
        assert session.last_post is not None
        _, kwargs = session.last_post
        self.assertEqual(kwargs["json"]["environment_ids"], [17])
        self.assertEqual(kwargs["json"]["state"], "approved")


class ProjectRegistryTests(unittest.TestCase):
    def test_validates_https_and_persists_custom_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = ProjectRegistry(directory)
            project = validate_project(
                "new_one", "Новый проект", "https://example.com/health", "private-repo"
            )
            registry.add(project)
            reloaded = ProjectRegistry(directory)
            self.assertEqual(reloaded.by_key("new_one"), project)

    def test_rejects_insecure_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "https"):
            validate_project("demo", "Demo", "http://example.com", None)


class MonitorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry_dir = tempfile.TemporaryDirectory()
        self.registry = ProjectRegistry(self.registry_dir.name)
        self.project = self.registry.by_key("iqbarakah")
        assert self.project is not None

    def tearDown(self) -> None:
        self.registry_dir.cleanup()

    def test_no_message_for_identical_state(self) -> None:
        state = ProjectState(True, 200, 10, "completed", "success")
        self.assertEqual(
            transition_messages(
                {self.project.key: state},
                {self.project.key: state},
                self.registry,
            ),
            [],
        )

    def test_reports_outage_and_recovery(self) -> None:
        healthy = ProjectState(True, 200, None, None, None)
        down = ProjectState(False, None, None, None, None)
        outage = transition_messages(
            {self.project.key: healthy},
            {self.project.key: down},
            self.registry,
        )
        recovery = transition_messages(
            {self.project.key: down},
            {self.project.key: healthy},
            self.registry,
        )
        self.assertIn("Недоступен", outage[0])
        self.assertIn("Восстановлен", recovery[0])

    def test_state_store_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(directory)
            states = {
                "demo": ProjectState(True, 401, 12, "completed", "failure")
            }
            store.save(states)
            self.assertEqual(store.load(), states)
            self.assertTrue(Path(directory, "monitor_state.json").exists())

    def test_token_expiry_reminder_is_sent_once_per_milestone(self) -> None:
        expires = date(2026, 10, 23)
        reminder = token_expiry_reminder(date(2026, 10, 16), expires, set())
        self.assertIsNotNone(reminder)
        assert reminder is not None
        key, message = reminder
        self.assertIn("7", message)
        self.assertIsNone(
            token_expiry_reminder(date(2026, 10, 16), expires, {key})
        )

    def test_expired_token_reminder_is_not_repeated(self) -> None:
        expires = date(2026, 10, 23)
        reminder = token_expiry_reminder(date(2026, 10, 24), expires, set())
        self.assertIsNotNone(reminder)
        assert reminder is not None
        key, message = reminder
        self.assertIn("истёк", message)
        self.assertIsNone(
            token_expiry_reminder(date(2026, 11, 1), expires, {key})
        )


class ApprovalStoreTests(unittest.TestCase):
    def test_idempotent_request_returns_same_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ApprovalStore(directory)
            first, first_created = store.create(
                idempotency_key="release:iqbarakah:42",
                project="IQ Barakah",
                action="Production deploy",
                description="Deploy tested release",
                risk="Container restart",
            )
            second, second_created = store.create(
                idempotency_key="release:iqbarakah:42",
                project="IQ Barakah",
                action="Changed text is ignored",
                description="Changed text is ignored",
                risk="Changed text is ignored",
            )
            self.assertTrue(first_created)
            self.assertFalse(second_created)
            self.assertEqual(first.id, second.id)

    def test_owner_can_approve_only_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ApprovalStore(directory)
            approval, _ = store.create(
                idempotency_key="release:mizanlife:43",
                project="Mizan Life",
                action="Production deploy",
                description="Deploy tested release",
                risk="Container restart",
            )
            decided = store.decide(approval.id, approved=True, owner_id=42)
            repeated = store.decide(approval.id, approved=False, owner_id=99)
            assert decided is not None and repeated is not None
            self.assertEqual(decided.status, "approved")
            self.assertEqual(repeated.status, "approved")
            self.assertEqual(repeated.decided_by, 42)

    def test_expired_request_cannot_be_approved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ApprovalStore(directory)
            created_at = datetime(2026, 7, 25, tzinfo=timezone.utc)
            approval, _ = store.create(
                idempotency_key="release:mizanos:44",
                project="Mizan OS",
                action="Production deploy",
                description="Deploy tested release",
                risk="Container restart",
                ttl_minutes=5,
                now=created_at,
            )
            decided = store.decide(
                approval.id,
                approved=True,
                owner_id=42,
                now=created_at + timedelta(minutes=6),
            )
            assert decided is not None
            self.assertEqual(decided.status, "expired")
            self.assertIsNone(decided.decided_by)

    def test_approval_persists_across_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ApprovalStore(directory)
            approval, _ = store.create(
                idempotency_key="release:iqbarakah:45",
                project="IQ Barakah",
                action="Production deploy",
                description="Deploy tested release",
                risk="Container restart",
            )
            reloaded = ApprovalStore(directory)
            self.assertEqual(reloaded.get(approval.id), approval)

    def test_notification_is_marked_only_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ApprovalStore(directory)
            approval, _ = store.create(
                idempotency_key="release:iqbarakah:46",
                project="IQ Barakah",
                action="Production deploy",
                description="Deploy tested release",
                risk="Container restart",
            )
            notified = store.mark_notified(approval.id)
            repeated = store.mark_notified(approval.id)
            assert notified is not None and repeated is not None
            self.assertIsNotNone(notified.notified_at)
            self.assertEqual(repeated.notified_at, notified.notified_at)

    def test_github_context_messages_and_decision_source_persist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ApprovalStore(directory)
            approval, _ = store.create(
                idempotency_key="release:iqbarakah:47",
                project="IQ Barakah",
                action="Production deploy",
                description="Deploy tested release",
                risk="Container restart",
                github_repository="iq-barakah",
                github_run_id=123,
            )
            store.add_telegram_message(
                approval.id,
                chat_id=42,
                message_id=99,
            )
            decided = store.decide(
                approval.id,
                approved=True,
                owner_id=None,
                source="github",
            )
            assert decided is not None
            reloaded = ApprovalStore(directory).get(approval.id)
            assert reloaded is not None
            self.assertEqual(reloaded.telegram_messages, ((42, 99),))
            self.assertEqual(reloaded.github_repository, "iq-barakah")
            self.assertEqual(reloaded.github_run_id, 123)
            self.assertEqual(reloaded.decision_source, "github")


if __name__ == "__main__":
    unittest.main()
