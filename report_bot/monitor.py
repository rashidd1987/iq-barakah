import asyncio
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
import html
import json
import logging
from pathlib import Path
from typing import TypedDict
from zoneinfo import ZoneInfo

from aiogram import Bot

from report_bot.approvals import ApprovalStore
from report_bot.projects import ProjectRegistry
from report_bot.status import SiteStatus, StatusClient, all_sites_summary
from report_bot.tasks import TaskStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProjectState:
    site_ok: bool
    status_code: int | None
    workflow_id: int | None
    workflow_status: str | None
    workflow_conclusion: str | None
    failure_streak: int = 0
    success_streak: int = 0
    error_reason: str | None = None


OUTAGE_CONFIRMATIONS = 3
RECOVERY_CONFIRMATIONS = 2


class StableSiteState(TypedDict):
    site_ok: bool
    status_code: int | None
    failure_streak: int
    success_streak: int
    error_reason: str | None


class StateStore:
    def __init__(self, data_dir: str) -> None:
        self.path = Path(data_dir) / "monitor_state.json"

    def load(self) -> dict[str, ProjectState]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return {key: ProjectState(**value) for key, value in raw.items()}
        except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
            return {}

    def save(self, states: dict[str, ProjectState]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {key: asdict(value) for key, value in states.items()},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.path)


class ReportDateStore:
    def __init__(
        self,
        data_dir: str,
        filename: str = "last_evening_report.txt",
    ) -> None:
        self.path = Path(data_dir) / filename

    def load(self):
        try:
            return datetime.fromisoformat(
                self.path.read_text(encoding="utf-8").strip()
            ).date()
        except (FileNotFoundError, OSError, ValueError):
            return None

    def save(self, value) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(value.isoformat(), encoding="utf-8")
        temporary.replace(self.path)


class ReminderStore:
    def __init__(self, data_dir: str) -> None:
        self.path = Path(data_dir) / "sent_reminders.json"

    def load(self) -> set[str]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return {str(value) for value in raw}
        except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
            return set()

    def save(self, values: set[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(sorted(values), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)


def token_expiry_reminder(
    today: date,
    expires_at: date | None,
    sent: set[str],
) -> tuple[str, str] | None:
    if expires_at is None:
        return None
    days_left = (expires_at - today).days
    if days_left in {30, 14, 7, 3, 1}:
        key = f"github-token:{expires_at.isoformat()}:{days_left}"
        if key in sent:
            return None
        return (
            key,
            "🔐 <b>Скоро истекает GitHub-токен</b>\n\n"
            f"Осталось дней: <b>{days_left}</b>.\n"
            f"Дата окончания: <b>{expires_at.strftime('%d.%m.%Y')}</b>.\n\n"
            "Обновите <code>GITHUB_READ_TOKEN</code> в Amvera, "
            "чтобы отчёты по приватным проектам не остановились.",
        )
    if days_left == 0:
        key = f"github-token:{expires_at.isoformat()}:today"
        if key in sent:
            return None
        return (
            key,
            "🚨 <b>GitHub-токен истекает сегодня</b>\n\n"
            "Обновите <code>GITHUB_READ_TOKEN</code> в Amvera.",
        )
    if days_left < 0:
        key = f"github-token:{expires_at.isoformat()}:expired"
        if key in sent:
            return None
        return (
            key,
            "🚨 <b>GitHub-токен истёк</b>\n\n"
            f"Дата окончания: <b>{expires_at.strftime('%d.%m.%Y')}</b>.\n"
            "Создайте новый read-only токен и обновите "
            "<code>GITHUB_READ_TOKEN</code> в Amvera.",
        )
    return None


def stabilize_site_status(
    site: SiteStatus,
    previous: ProjectState | None,
) -> StableSiteState:
    if previous is None:
        return {
            "site_ok": site.ok,
            "status_code": site.status_code,
            "failure_streak": 0 if site.ok else 1,
            "success_streak": 1 if site.ok else 0,
            "error_reason": site.error_reason,
        }

    if site.ok:
        success_streak = previous.success_streak + 1
        return {
            "site_ok": previous.site_ok or success_streak >= RECOVERY_CONFIRMATIONS,
            "status_code": site.status_code,
            "failure_streak": 0,
            "success_streak": success_streak,
            "error_reason": None,
        }

    failure_streak = previous.failure_streak + 1
    return {
        "site_ok": (
            previous.site_ok and failure_streak < OUTAGE_CONFIRMATIONS
        ),
        "status_code": site.status_code,
        "failure_streak": failure_streak,
        "success_streak": 0,
        "error_reason": site.error_reason,
    }


async def capture_state(
    client: StatusClient,
    registry: ProjectRegistry,
    previous: dict[str, ProjectState] | None = None,
) -> dict[str, ProjectState]:
    previous = previous or {}

    async def capture(project):
        site = await client.site_status(project)
        runs = await client.workflow_runs(project.repo, limit=1) if project.repo else None
        latest = runs[0] if runs else {}
        stable_site = stabilize_site_status(site, previous.get(project.key))
        return project.key, ProjectState(
            workflow_id=latest.get("id"),
            workflow_status=latest.get("status"),
            workflow_conclusion=latest.get("conclusion"),
            **stable_site,
        )

    return dict(await asyncio.gather(*(capture(project) for project in registry.all())))


def transition_messages(
    previous: dict[str, ProjectState],
    current: dict[str, ProjectState],
    registry: ProjectRegistry,
) -> list[str]:
    messages: list[str] = []
    for project in registry.all():
        before, after = previous.get(project.key), current.get(project.key)
        if before is None or after is None:
            continue
        if before.site_ok != after.site_ok:
            if after.site_ok:
                messages.append(f"✅ Восстановлен: <b>{project.title}</b>")
            else:
                reason = after.error_reason or (
                    f"HTTP {after.status_code}"
                    if after.status_code is not None
                    else "причина не определена"
                )
                messages.append(
                    f"🚨 Недоступен: <b>{project.title}</b>\n"
                    f"Причина: {reason} "
                    f"({after.failure_streak} проверки подряд)"
                )
        workflow_changed = (
            after.workflow_id is not None
            and (
                before.workflow_id != after.workflow_id
                or before.workflow_status != after.workflow_status
                or before.workflow_conclusion != after.workflow_conclusion
            )
        )
        if workflow_changed and after.workflow_status == "completed":
            icon = "✅" if after.workflow_conclusion == "success" else "❌"
            messages.append(
                f"{icon} Сборка <b>{project.title}</b>: "
                f"{after.workflow_conclusion or 'завершена'}"
            )
    return messages


def morning_brief(
    states: dict[str, ProjectState],
    registry: ProjectRegistry,
    task_store: TaskStore,
    approval_store: ApprovalStore,
    today: date,
) -> str:
    projects = registry.all()
    down = [
        project
        for project in projects
        if (state := states.get(project.key)) is not None and not state.site_ok
    ]
    failed = [
        project
        for project in projects
        if (state := states.get(project.key)) is not None
        and state.workflow_status == "completed"
        and state.workflow_conclusion == "failure"
    ]
    open_tasks = task_store.open()
    overdue = [task for task in open_tasks if date.fromisoformat(task.due_date) < today]
    due_today = [task for task in open_tasks if task.due_date == today.isoformat()]
    pending = approval_store.pending()

    lines = [
        "☀️ <b>Утренний бриф собственника</b>",
        f"📅 {today.strftime('%d.%m.%Y')}",
        "",
        "<b>Проекты</b>",
    ]
    for project in projects:
        state = states.get(project.key)
        if state is None:
            lines.append(f"⚪️ {html.escape(project.title)}: нет данных")
            continue
        icon = "✅" if state.site_ok else "🚨"
        status = (
            f"HTTP {state.status_code}"
            if state.status_code is not None
            else state.error_reason or "нет ответа"
        )
        lines.append(f"{icon} {html.escape(project.title)}: {html.escape(status)}")

    lines.extend(
        [
            "",
            "<b>Поручения и решения</b>",
            f"📌 Открыто: <b>{len(open_tasks)}</b>",
            f"⏰ Просрочено: <b>{len(overdue)}</b>",
            f"📅 На сегодня: <b>{len(due_today)}</b>",
            f"🔐 Ждут решения: <b>{len(pending)}</b>",
        ]
    )

    priorities: list[str] = []
    if down:
        priorities.append(
            "Восстановить: "
            + ", ".join(html.escape(project.title) for project in down)
        )
    if failed:
        priorities.append(
            "Разобрать ошибку сборки: "
            + ", ".join(html.escape(project.title) for project in failed)
        )
    if pending:
        priorities.append(f"Принять решение по {len(pending)} запросам")
    if overdue:
        priorities.append(f"Закрыть {len(overdue)} просроченных поручений")
    if due_today:
        priorities.append(
            "Выполнить сегодня: "
            + "; ".join(html.escape(task.title) for task in due_today[:2])
        )
    if not priorities:
        priorities.append(
            "Критических отклонений нет — выберите один главный результат дня"
        )

    lines.extend(["", "<b>Приоритеты</b>"])
    lines.extend(
        f"{index}. {priority}" for index, priority in enumerate(priorities[:3], 1)
    )
    lines.append(
        "\nКоманды: /today — срочные, /tasks — все, /newtask — новое."
    )
    return "\n".join(lines)


def weekly_task_report(
    task_store: TaskStore,
    registry: ProjectRegistry,
    today: date,
) -> str:
    """Build a factual seven-day owner report from the append-only task journal."""
    period_start = today - timedelta(days=6)
    events = [
        event
        for event in task_store.events()
        if period_start <= datetime.fromisoformat(event.occurred_at).date() <= today
    ]
    counts = {
        event_name: sum(event.event == event_name for event in events)
        for event_name in ("created", "completed", "rescheduled", "canceled")
    }
    open_tasks = task_store.open()
    overdue = [task for task in open_tasks if task.due_date < today.isoformat()]
    project_pressure: dict[str, int] = {}
    for task in overdue:
        project_pressure[task.project_key] = project_pressure.get(task.project_key, 0) + 1
    for event in events:
        if event.event != "rescheduled":
            continue
        task = task_store.get(event.task_id)
        if task:
            project_pressure[task.project_key] = project_pressure.get(task.project_key, 0) + 1

    lines = [
        "📊 <b>Недельный отчёт собственника</b>",
        f"📅 {period_start.strftime('%d.%m')}–{today.strftime('%d.%m.%Y')}",
        "",
        "<b>Движение поручений</b>",
        f"➕ Создано: <b>{counts['created']}</b>",
        f"✅ Выполнено: <b>{counts['completed']}</b>",
        f"➡️ Перенесено: <b>{counts['rescheduled']}</b>",
        f"⛔ Отменено: <b>{counts['canceled']}</b>",
        f"📌 Открыто сейчас: <b>{len(open_tasks)}</b>",
        f"⏰ Просрочено сейчас: <b>{len(overdue)}</b>",
        "",
        "<b>Зоны внимания</b>",
    ]
    if project_pressure:
        ranked = sorted(project_pressure.items(), key=lambda item: (-item[1], item[0]))
        for project_key, pressure in ranked[:3]:
            project = registry.by_key(project_key)
            title = project.title if project else project_key
            lines.append(f"• {html.escape(title)}: <b>{pressure}</b> сигналов")
    else:
        lines.append("✅ Просрочек и переносов за период нет")

    if overdue:
        lines.extend(["", "<b>Следующее действие</b>"])
        for task in overdue[:3]:
            project = registry.by_key(task.project_key)
            title = project.title if project else task.project_key
            lines.append(
                f"• {html.escape(title)} — {html.escape(task.title)} "
                f"(срок {date.fromisoformat(task.due_date).strftime('%d.%m')})"
            )
        lines.append("\nОткройте /evening, чтобы закрыть, перенести или отменить.")
    elif counts["created"] == counts["completed"] == 0:
        lines.append("\nЗа неделю поручений не было. Зафиксируйте следующий результат: /newtask")
    else:
        lines.append("\n✅ Просроченных поручений нет. Сформируйте следующий фокус: /plan")
    return "\n".join(lines)


async def monitor_loop(
    bot: Bot,
    owner_ids: frozenset[int],
    client: StatusClient,
    registry: ProjectRegistry,
    data_dir: str,
    interval_seconds: int,
    morning_hour: int,
    report_hour: int,
    weekly_weekday: int,
    weekly_hour: int,
    timezone: str,
    github_token_expires_at: date | None,
    task_store: TaskStore,
    approval_store: ApprovalStore,
) -> None:
    store = StateStore(data_dir)
    report_store = ReportDateStore(data_dir)
    morning_store = ReportDateStore(data_dir, "last_morning_report.txt")
    weekly_store = ReportDateStore(data_dir, "last_weekly_report.txt")
    previous = store.load()
    last_report_date = report_store.load()
    last_morning_date = morning_store.load()
    last_weekly_date = weekly_store.load()
    reminder_store = ReminderStore(data_dir)
    sent_reminders = reminder_store.load()
    zone = ZoneInfo(timezone)
    while True:
        try:
            current = await capture_state(client, registry, previous)
            if previous:
                for message in transition_messages(previous, current, registry):
                    for owner_id in owner_ids:
                        await bot.send_message(owner_id, message)
            previous = current
            store.save(current)

            now = datetime.now(zone)
            reminder = token_expiry_reminder(
                now.date(), github_token_expires_at, sent_reminders
            )
            if reminder:
                reminder_key, reminder_message = reminder
                for owner_id in owner_ids:
                    await bot.send_message(owner_id, reminder_message)
                sent_reminders.add(reminder_key)
                reminder_store.save(sent_reminders)

            if now.hour == morning_hour and last_morning_date != now.date():
                summary = morning_brief(
                    current,
                    registry,
                    task_store,
                    approval_store,
                    now.date(),
                )
                for owner_id in owner_ids:
                    await bot.send_message(owner_id, summary)
                last_morning_date = now.date()
                morning_store.save(last_morning_date)

            if now.hour == report_hour and last_report_date != now.date():
                summary = "🌙 <b>Вечерний отчёт</b>\n\n" + await all_sites_summary(
                    client, registry.all()
                )
                due_count = len(task_store.due(now.date()))
                summary += (
                    "\n\n<b>Контроль поручений</b>\n"
                    f"Требуют итога: <b>{due_count}</b>\n"
                    "Откройте /evening, чтобы выполнить, перенести или отменить."
                )
                for owner_id in owner_ids:
                    await bot.send_message(owner_id, summary)
                last_report_date = now.date()
                report_store.save(last_report_date)

            if (
                now.weekday() == weekly_weekday
                and now.hour == weekly_hour
                and last_weekly_date != now.date()
            ):
                summary = weekly_task_report(task_store, registry, now.date())
                for owner_id in owner_ids:
                    await bot.send_message(owner_id, summary)
                last_weekly_date = now.date()
                weekly_store.save(last_weekly_date)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Monitoring iteration failed")
        await asyncio.sleep(interval_seconds)
