import asyncio
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from report_bot.approvals import ApprovalStore
from report_bot.ai_gateway import (
    choose_auto_provider,
    choose_judge,
    synthesis_task,
)
from report_bot.config import load_config
from report_bot.council import CouncilContext, council_views, select_project
from report_bot.day_plan import DayPlanStore, build_day_plan
from report_bot.monitor import (
    ProjectState,
    StateStore,
    morning_brief,
    overdue_task_reminder,
    weekly_task_report,
    stabilize_site_status,
    token_expiry_reminder,
    transition_messages,
)
from report_bot.main import (
    BOT_COMMANDS,
    MENU,
    api_provider_keyboard,
    approval_auth_ok,
    council_mode_keyboard,
    council_keyboard,
    extract_task_evidence,
    multi_provider_keyboard,
    plan_suggestion_keyboard,
    pwa_release_keyboard,
    send_automatic_day_plan,
    task_review_keyboard,
)
from report_bot.knowledge import ProjectKnowledgeLibrary
from report_bot.projects import PROJECTS, ProjectRegistry, validate_project
from report_bot.status import SiteStatus, StatusClient, format_datetime, run_icon
from report_bot.tasks import TaskStore, parse_task_details


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

    def test_loads_default_morning_report_hour(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "test-token",
                "OWNER_TELEGRAM_IDS": "42",
            },
            clear=True,
        ):
            config = load_config()
        self.assertEqual(config.morning_report_hour, 9)
        self.assertEqual(config.weekly_report_weekday, 0)
        self.assertEqual(config.weekly_report_hour, 9)

    def test_rejects_invalid_morning_report_hour(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "test-token",
                "OWNER_TELEGRAM_IDS": "42",
                "MORNING_REPORT_HOUR": "24",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "MORNING_REPORT_HOUR"):
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
    def test_start_is_available_in_commands_and_main_keyboard(self) -> None:
        commands = [item.command for item in BOT_COMMANDS]
        labels = [button.text for row in MENU.keyboard for button in row]
        self.assertIn("start", commands)
        self.assertEqual(labels.count("🏠 Старт"), 1)
        self.assertEqual(MENU.keyboard[0][0].text, "🏠 Старт")

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

    def test_day_plan_callback_is_compact(self) -> None:
        callback = plan_suggestion_keyboard("safe-id").inline_keyboard[0][0]
        self.assertEqual(callback.callback_data, "dayplan:add:safe-id")
        self.assertLessEqual(len(callback.callback_data or ""), 64)

    def test_evening_review_has_three_explicit_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            task = TaskStore(directory).create(
                project_key="iqbarakah",
                title="Проверить путь",
                due_date=date(2026, 8, 1),
                success_criterion="Путь проверен",
                created_by=42,
            )
            callbacks = {
                button.callback_data
                for row in task_review_keyboard(task).inline_keyboard
                for button in row
            }
            self.assertEqual(
                callbacks,
                {
                    f"review:done:{task.id}",
                    f"review:postpone:{task.id}",
                    f"review:cancel:{task.id}",
                },
            )
            self.assertTrue(all(len(value or "") <= 64 for value in callbacks))

    def test_completion_evidence_accepts_screenshot_reference(self) -> None:
        message = SimpleNamespace(
            text=None,
            caption="Экран после проверки",
            photo=[SimpleNamespace(file_id="photo")],
            document=None,
            message_id=123,
        )
        self.assertEqual(
            extract_task_evidence(message),
            "Скриншот Telegram, сообщение #123: Экран после проверки",
        )


class OwnerCouncilTests(unittest.TestCase):
    def test_council_modes_are_explicit(self) -> None:
        callbacks = {
            button.callback_data
            for row in council_mode_keyboard().inline_keyboard
            for button in row
        }
        self.assertEqual(
            callbacks,
            {
                "councilmode:builtin",
                "councilmode:api",
                "councilmode:subscriptions",
            },
        )

    def test_api_keyboard_only_contains_configured_providers(self) -> None:
        callbacks = {
            button.callback_data
            for row in api_provider_keyboard(("openai", "xai")).inline_keyboard
            for button in row
        }
        self.assertEqual(
            callbacks,
            {
                "aipick:auto",
                "aipick:multi",
                "aipick:all",
                "aipick:openai",
                "aipick:xai",
                "aipick:cancel",
            },
        )

    def test_multi_provider_keyboard_tracks_selection(self) -> None:
        keyboard = multi_provider_keyboard(
            ("openai", "anthropic"), ("anthropic",)
        )
        labels = [
            button.text for row in keyboard.inline_keyboard for button in row
        ]
        self.assertIn("◻️ GPT", labels)
        self.assertIn("✅ Claude", labels)
        self.assertIn("Продолжить (1)", labels)

    def test_auto_provider_uses_task_and_safe_fallback(self) -> None:
        configured = ("openai", "anthropic", "perplexity")
        self.assertEqual(
            choose_auto_provider("Исследуй рынок", configured),
            "perplexity",
        )
        self.assertEqual(
            choose_auto_provider("Проверь архитектуру API", configured),
            "anthropic",
        )
        self.assertEqual(choose_judge(configured), "openai")

    def test_synthesis_prompt_caps_individual_answers(self) -> None:
        prompt = synthesis_task(
            "Выбрать стратегию",
            (("openai", "x" * 3000), ("anthropic", "ответ")),
        )
        self.assertIn("Исходная задача: Выбрать стратегию", prompt)
        self.assertNotIn("x" * 2201, prompt)

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


class ProjectKnowledgeTests(unittest.TestCase):
    def test_mizan_life_brief_prevents_insurance_guess(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            library = ProjectKnowledgeLibrary(directory)
            project = library.resolve("конкуренты для мизан лайф", PROJECTS)
            prompt = library.ai_task(project, "найди конкурентов")

        self.assertEqual(project.key, "mizanlife")
        self.assertIn("не является страхованием жизни", prompt.casefold())
        self.assertIn("Задача владельца: найди конкурентов", prompt)

    def test_persists_custom_brief_and_active_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            library = ProjectKnowledgeLibrary(directory)
            library.set_brief(
                "mizanos",
                "Mizan OS — операционная система управления проектами владельца.",
            )
            library.set_active("mizanos", PROJECTS)

            reloaded = ProjectKnowledgeLibrary(directory)
            self.assertEqual(reloaded.active_project, "mizanos")
            self.assertIn("управления проектами", reloaded.brief("mizanos"))
            self.assertEqual(
                reloaded.resolve("проверь следующий риск", PROJECTS).key,
                "mizanos",
            )

    def test_migrates_placeholder_mizanos_brief(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project_knowledge.json"
            path.write_text(
                json.dumps(
                    {
                        "active_project": "mizanos",
                        "briefs": {
                            "mizanos": (
                                "Mizan OS — отдельное веб-приложение экосистемы "
                                "Mizan. Подробный продуктовый паспорт ещё не "
                                "заполнен владельцем. Нельзя делать выводы о "
                                "назначении продукта только по названию; при "
                                "необходимости нужно задать владельцу уточняющий "
                                "вопрос."
                            )
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            library = ProjectKnowledgeLibrary(directory)

        self.assertIn("CRM служит единым центром", library.brief("mizanos"))
        self.assertIn("Ready for manual launch", library.brief("mizanos"))


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
        down = ProjectState(
            False,
            None,
            None,
            None,
            None,
            failure_streak=3,
            error_reason="тайм-аут ответа",
        )
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
        self.assertIn("тайм-аут ответа", outage[0])
        self.assertIn("3 проверки подряд", outage[0])
        self.assertIn("Восстановлен", recovery[0])

    def test_single_failure_does_not_mark_healthy_project_down(self) -> None:
        healthy = ProjectState(True, 200, None, None, None)
        first = stabilize_site_status(
            SiteStatus(False, None, None, "ошибка DNS"),
            healthy,
        )
        after_first = ProjectState(
            workflow_id=None,
            workflow_status=None,
            workflow_conclusion=None,
            **first,
        )
        second = stabilize_site_status(
            SiteStatus(False, None, None, "ошибка DNS"),
            after_first,
        )
        self.assertTrue(first["site_ok"])
        self.assertTrue(second["site_ok"])

    def test_three_failures_mark_project_down_and_two_successes_restore_it(self) -> None:
        state = ProjectState(True, 200, None, None, None)
        for expected_ok in (True, True, False):
            values = stabilize_site_status(
                SiteStatus(False, None, None, "тайм-аут ответа"),
                state,
            )
            self.assertEqual(values["site_ok"], expected_ok)
            state = ProjectState(
                workflow_id=None,
                workflow_status=None,
                workflow_conclusion=None,
                **values,
            )

        for expected_ok in (False, True):
            values = stabilize_site_status(
                SiteStatus(True, 401, 120),
                state,
            )
            self.assertEqual(values["site_ok"], expected_ok)
            state = ProjectState(
                workflow_id=None,
                workflow_status=None,
                workflow_conclusion=None,
                **values,
            )

    def test_state_store_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(directory)
            states = {
                "demo": ProjectState(True, 401, 12, "completed", "failure")
            }
            store.save(states)
            self.assertEqual(store.load(), states)
            self.assertTrue(Path(directory, "monitor_state.json").exists())

    def test_state_store_loads_state_written_before_stability_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "monitor_state.json").write_text(
                json.dumps(
                    {
                        "mizanos": {
                            "site_ok": True,
                            "status_code": 401,
                            "workflow_id": None,
                            "workflow_status": None,
                            "workflow_conclusion": None,
                        }
                    }
                ),
                encoding="utf-8",
            )
            state = StateStore(directory).load()["mizanos"]
            self.assertEqual(state.failure_streak, 0)
            self.assertEqual(state.success_streak, 0)
            self.assertIsNone(state.error_reason)

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


class TaskStoreTests(unittest.TestCase):
    def test_parses_compact_task_details(self) -> None:
        title, due_date, criterion = parse_task_details(
            "Проверить оплату | 2026-08-02 | Тестовая оплата проходит"
        )
        self.assertEqual(title, "Проверить оплату")
        self.assertEqual(due_date, date(2026, 8, 2))
        self.assertEqual(criterion, "Тестовая оплата проходит")

    def test_rejects_invalid_task_details(self) -> None:
        with self.assertRaisesRegex(ValueError, "Формат"):
            parse_task_details("Только название")
        with self.assertRaisesRegex(ValueError, "ГГГГ-ММ-ДД"):
            parse_task_details("Проверить оплату | завтра | Оплата проходит")

    def test_task_lifecycle_and_journal_persist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(directory)
            created_at = datetime(2026, 7, 31, 8, 0, tzinfo=timezone.utc)
            task = store.create(
                project_key="iqbarakah",
                title="Проверить оплату",
                due_date=date(2026, 8, 1),
                success_criterion="Тестовая оплата проходит",
                created_by=42,
                now=created_at,
            )
            completed = store.complete(
                task.id,
                completed_by=42,
                now=created_at + timedelta(hours=1),
            )
            assert completed is not None
            self.assertEqual(completed.status, "done")
            self.assertEqual(
                [event.event for event in store.events()],
                ["created", "completed"],
            )

            reloaded = TaskStore(directory)
            persisted = reloaded.get(task.id)
            assert persisted is not None
            self.assertEqual(persisted.status, "done")
            self.assertEqual(persisted.completed_by, 42)
            self.assertEqual(len(reloaded.events()), 2)

    def test_complete_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(directory)
            task = store.create(
                project_key="mizanlife",
                title="Проверить главную",
                due_date=date(2026, 8, 1),
                success_criterion="Страница открывается",
                created_by=42,
            )
            first = store.complete(task.id, completed_by=42)
            repeated = store.complete(task.id, completed_by=99)
            assert first is not None and repeated is not None
            self.assertEqual(first.completed_at, repeated.completed_at)
            self.assertEqual(repeated.completed_by, 42)
            self.assertEqual(len(store.events()), 2)

    def test_due_includes_overdue_and_today_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(directory)
            for title, due_date in (
                ("Просроченная задача", date(2026, 7, 30)),
                ("Задача на сегодня", date(2026, 7, 31)),
                ("Будущая задача", date(2026, 8, 1)),
            ):
                store.create(
                    project_key="mizanos",
                    title=title,
                    due_date=due_date,
                    success_criterion="Результат проверен",
                    created_by=42,
                )
            self.assertEqual(
                [task.title for task in store.due(date(2026, 7, 31))],
                ["Просроченная задача", "Задача на сегодня"],
            )

    def test_completion_evidence_persists_and_repeated_completion_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(directory)
            task = store.create(
                project_key="iqbarakah",
                title="Проверить синхронизацию",
                due_date=date(2026, 8, 1),
                success_criterion="Прогресс совпадает",
                created_by=42,
            )
            completed = store.complete(
                task.id,
                completed_by=42,
                evidence="Миниапп и PWA показывают шаг 6",
            )
            repeated = store.complete(
                task.id,
                completed_by=99,
                evidence="Другое подтверждение",
            )
            assert completed is not None and repeated is not None
            self.assertEqual(
                repeated.completion_evidence,
                "Миниапп и PWA показывают шаг 6",
            )
            persisted = TaskStore(directory).get(task.id)
            assert persisted is not None
            self.assertEqual(persisted.completion_evidence, completed.completion_evidence)

    def test_reschedule_requires_reason_and_updates_due_date(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(directory)
            task = store.create(
                project_key="mizanlife",
                title="Проверить сценарий",
                due_date=date(2026, 8, 1),
                success_criterion="Сценарий работает",
                created_by=42,
            )
            with self.assertRaisesRegex(ValueError, "Причина переноса"):
                store.reschedule(
                    task.id,
                    due_date=date(2026, 8, 3),
                    reason="x",
                    actor_id=42,
                )
            updated = store.reschedule(
                task.id,
                due_date=date(2026, 8, 3),
                reason="Нужен доступ к тестовому аккаунту",
                actor_id=42,
            )
            assert updated is not None
            self.assertEqual(updated.due_date, "2026-08-03")
            self.assertEqual(updated.rescheduled_count, 1)
            self.assertEqual(store.events()[-1].event, "rescheduled")
            self.assertNotIn(updated, store.due(date(2026, 8, 1)))

    def test_cancel_is_idempotent_and_removes_task_from_open_lists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(directory)
            task = store.create(
                project_key="mizanos",
                title="Старое поручение",
                due_date=date(2026, 8, 1),
                success_criterion="Проверено",
                created_by=42,
            )
            canceled = store.cancel(
                task.id,
                reason="Задача больше не относится к релизу",
                canceled_by=42,
            )
            repeated = store.cancel(
                task.id,
                reason="Повторная причина",
                canceled_by=99,
            )
            assert canceled is not None and repeated is not None
            self.assertEqual(repeated.status, "canceled")
            self.assertEqual(repeated.cancel_reason, canceled.cancel_reason)
            unchanged = store.complete(task.id, completed_by=99)
            assert unchanged is not None
            self.assertEqual(unchanged.status, "canceled")
            self.assertEqual(len(store.events()), 2)
            self.assertEqual(store.open(), ())
            self.assertEqual(store.due(date(2026, 8, 1)), ())

    def test_old_task_file_loads_with_backward_compatible_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "owner_tasks.json"
            path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "id": "old-task",
                                "project_key": "iqbarakah",
                                "title": "Старое поручение",
                                "due_date": "2026-08-01",
                                "success_criterion": "Проверено",
                                "responsible": "Владелец",
                                "status": "open",
                                "created_at": "2026-07-31T10:00:00+00:00",
                                "created_by": 42,
                                "completed_at": None,
                                "completed_by": None,
                            }
                        ],
                        "events": [
                            {
                                "event": "created",
                                "task_id": "old-task",
                                "occurred_at": "2026-07-31T10:00:00+00:00",
                                "actor_id": 42,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            loaded = TaskStore(directory).get("old-task")
            assert loaded is not None
            self.assertIsNone(loaded.completion_evidence)
            self.assertEqual(loaded.rescheduled_count, 0)


class MorningBriefTests(unittest.TestCase):
    def test_prioritizes_outage_decisions_and_overdue_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = ProjectRegistry(directory)
            task_store = TaskStore(directory)
            approval_store = ApprovalStore(directory)
            task_store.create(
                project_key="iqbarakah",
                title="Проверить <оплату>",
                due_date=date(2026, 7, 30),
                success_criterion="Оплата проходит",
                created_by=42,
            )
            approval_store.create(
                idempotency_key="morning:test:1",
                project="IQ Barakah",
                action="Release",
                description="Deploy",
                risk="Users",
            )
            states = {
                project.key: ProjectState(
                    site_ok=project.key != "mizanlife",
                    status_code=200 if project.key != "mizanlife" else 503,
                    workflow_id=1,
                    workflow_status="completed",
                    workflow_conclusion="success",
                )
                for project in registry.all()
            }

            result = morning_brief(
                states,
                registry,
                task_store,
                approval_store,
                date(2026, 7, 31),
            )

            self.assertIn("Утренний бриф собственника", result)
            self.assertIn("🚨 Mizan Life: HTTP 503", result)
            self.assertIn("Просрочено: <b>1</b>", result)
            self.assertIn("Ждут решения: <b>1</b>", result)
            self.assertIn("1. Восстановить: Mizan Life", result)
            self.assertNotIn("<оплату>", result)

    def test_reports_clear_day_without_false_alarm(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = ProjectRegistry(directory)
            states = {
                project.key: ProjectState(
                    site_ok=True,
                    status_code=200,
                    workflow_id=None,
                    workflow_status=None,
                    workflow_conclusion=None,
                )
                for project in registry.all()
            }
            result = morning_brief(
                states,
                registry,
                TaskStore(directory),
                ApprovalStore(directory),
                date(2026, 7, 31),
            )
            self.assertIn("Критических отклонений нет", result)


class OverdueTaskReminderTests(unittest.TestCase):
    def test_reminds_once_on_milestones_and_escapes_task_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(directory)
            registry = ProjectRegistry(directory)
            task = store.create(
                project_key="iqbarakah",
                title="Проверить <релиз>",
                due_date=date(2026, 7, 31),
                success_criterion="CI зелёный",
                created_by=42,
            )

            result = overdue_task_reminder(
                date(2026, 8, 1), store, registry, set()
            )

            assert result is not None
            keys, message = result
            self.assertEqual(len(keys), 1)
            self.assertIn(task.id, keys[0])
            self.assertIn("<b>1</b> дн.", message)
            self.assertIn("&lt;релиз&gt;", message)
            self.assertIsNone(
                overdue_task_reminder(date(2026, 8, 1), store, registry, set(keys))
            )

    def test_skips_non_milestone_and_completed_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(directory)
            registry = ProjectRegistry(directory)
            task = store.create(
                project_key="iqbarakah",
                title="Проверить релиз",
                due_date=date(2026, 7, 30),
                success_criterion="CI зелёный",
                created_by=42,
            )
            self.assertIsNone(
                overdue_task_reminder(date(2026, 8, 1), store, registry, set())
            )
            store.complete(task.id, completed_by=42, evidence="CI зелёный")
            self.assertIsNone(
                overdue_task_reminder(date(2026, 8, 2), store, registry, set())
            )


class WeeklyTaskReportTests(unittest.TestCase):
    def test_reports_real_events_and_project_pressure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(directory)
            registry = ProjectRegistry(directory)
            created = datetime(2026, 7, 27, 10, tzinfo=timezone.utc)
            done = store.create(
                project_key="iqbarakah",
                title="Проверить релиз",
                due_date=date(2026, 7, 28),
                success_criterion="Проверка зелёная",
                created_by=42,
                now=created,
            )
            store.complete(
                done.id,
                completed_by=42,
                evidence="CI прошёл успешно",
                now=created + timedelta(days=1),
            )
            overdue = store.create(
                project_key="mizanlife",
                title="Проверить сценарий",
                due_date=date(2026, 7, 29),
                success_criterion="Сценарий работает",
                created_by=42,
                now=created,
            )
            store.reschedule(
                overdue.id,
                due_date=date(2026, 7, 30),
                reason="Нужен повторный тест",
                actor_id=42,
                now=created + timedelta(days=2),
            )

            result = weekly_task_report(store, registry, date(2026, 8, 1))

            self.assertIn("Создано: <b>2</b>", result)
            self.assertIn("Выполнено: <b>1</b>", result)
            self.assertIn("Перенесено: <b>1</b>", result)
            self.assertIn("Просрочено сейчас: <b>1</b>", result)
            self.assertIn("Mizan Life: <b>2</b> сигналов", result)

    def test_does_not_invent_percentage_for_empty_week(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = weekly_task_report(
                TaskStore(directory), ProjectRegistry(directory), date(2026, 8, 1)
            )
            self.assertIn("За неделю поручений не было", result)
            self.assertNotIn("%", result)


class DayPlanTests(unittest.TestCase):
    def test_automatic_plan_only_sends_suggestions_until_owner_accepts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = ProjectRegistry(directory)
            task_store = TaskStore(directory)
            plan_store = DayPlanStore(directory)
            states = {
                project.key: ProjectState(
                    site_ok=True,
                    status_code=200,
                    workflow_id=None,
                    workflow_status=None,
                    workflow_conclusion=None,
                )
                for project in registry.all()
            }
            bot = SimpleNamespace(send_message=AsyncMock())

            asyncio.run(
                send_automatic_day_plan(
                    bot,
                    frozenset({42}),
                    states,
                    registry,
                    task_store,
                    plan_store,
                    "iqbarakah",
                    date(2026, 8, 1),
                )
            )

            self.assertEqual(task_store.open(), ())
            self.assertEqual(bot.send_message.await_count, 4)
            heading = bot.send_message.await_args_list[0].args[1]
            self.assertIn("Без нажатия ничего не создаётся", heading)
            for call in bot.send_message.await_args_list[1:]:
                self.assertIsNotNone(call.kwargs["reply_markup"])

    def test_operational_failures_are_proposed_before_routine_checks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = ProjectRegistry(directory)
            states = {
                project.key: ProjectState(
                    site_ok=project.key != "mizanlife",
                    status_code=503 if project.key == "mizanlife" else 200,
                    workflow_id=1,
                    workflow_status="completed",
                    workflow_conclusion=(
                        "failure" if project.key == "iqbarakah" else "success"
                    ),
                )
                for project in registry.all()
            }
            result = build_day_plan(
                states,
                registry,
                TaskStore(directory),
                date(2026, 7, 31),
                "iqbarakah",
            )
            self.assertEqual(len(result), 3)
            self.assertEqual(result[0].project_key, "mizanlife")
            self.assertIn("Восстановить доступность", result[0].title)
            self.assertEqual(result[1].project_key, "iqbarakah")
            self.assertIn("неуспешную сборку", result[1].title)

    def test_existing_open_task_is_not_proposed_twice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = ProjectRegistry(directory)
            task_store = TaskStore(directory)
            title = "Проверить путь участника IQ Barakah от входа до текущего урока"
            task_store.create(
                project_key="iqbarakah",
                title=title,
                due_date=date(2026, 7, 31),
                success_criterion="Проверено",
                created_by=42,
            )
            states = {
                project.key: ProjectState(
                    site_ok=True,
                    status_code=200,
                    workflow_id=None,
                    workflow_status=None,
                    workflow_conclusion=None,
                )
                for project in registry.all()
            }
            result = build_day_plan(
                states,
                registry,
                task_store,
                date(2026, 7, 31),
                "iqbarakah",
            )
            self.assertNotIn(title, [item.title for item in result])

    def test_plan_store_reuses_id_and_preserves_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = ProjectRegistry(directory)
            states = {
                project.key: ProjectState(
                    site_ok=True,
                    status_code=200,
                    workflow_id=None,
                    workflow_status=None,
                    workflow_conclusion=None,
                )
                for project in registry.all()
            }
            suggestions = build_day_plan(
                states,
                registry,
                TaskStore(directory),
                date(2026, 7, 31),
                "iqbarakah",
            )
            store = DayPlanStore(directory)
            first = store.replace(date(2026, 7, 31), suggestions)
            accepted = store.mark_accepted(first[0].id, "task-1")
            assert accepted is not None
            repeated = store.replace(date(2026, 7, 31), suggestions)
            self.assertEqual(repeated[0].id, first[0].id)
            self.assertEqual(repeated[0].accepted_task_id, "task-1")
            reloaded = DayPlanStore(directory).get(first[0].id)
            assert reloaded is not None
            self.assertEqual(reloaded.accepted_task_id, "task-1")

    def test_find_open_uses_case_insensitive_exact_title(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(directory)
            task = store.create(
                project_key="mizanos",
                title="Проверить релиз",
                due_date=date(2026, 7, 31),
                success_criterion="Релиз проверен",
                created_by=42,
            )
            self.assertEqual(
                store.find_open("mizanos", "  проверить РЕЛИЗ  "), task
            )


if __name__ == "__main__":
    unittest.main()
