import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime
import json
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import Bot

from report_bot.projects import ProjectRegistry
from report_bot.status import StatusClient, all_sites_summary

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProjectState:
    site_ok: bool
    status_code: int | None
    workflow_id: int | None
    workflow_status: str | None
    workflow_conclusion: str | None


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
    def __init__(self, data_dir: str) -> None:
        self.path = Path(data_dir) / "last_evening_report.txt"

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


async def capture_state(
    client: StatusClient, registry: ProjectRegistry
) -> dict[str, ProjectState]:
    async def capture(project):
        site = await client.site_status(project)
        runs = await client.workflow_runs(project.repo, limit=1) if project.repo else None
        latest = runs[0] if runs else {}
        return project.key, ProjectState(
            site_ok=site.ok,
            status_code=site.status_code,
            workflow_id=latest.get("id"),
            workflow_status=latest.get("status"),
            workflow_conclusion=latest.get("conclusion"),
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
            messages.append(
                f"{'✅ Восстановлен' if after.site_ok else '🚨 Недоступен'}: "
                f"<b>{project.title}</b>"
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


async def monitor_loop(
    bot: Bot,
    owner_ids: frozenset[int],
    client: StatusClient,
    registry: ProjectRegistry,
    data_dir: str,
    interval_seconds: int,
    report_hour: int,
    timezone: str,
) -> None:
    store = StateStore(data_dir)
    report_store = ReportDateStore(data_dir)
    previous = store.load()
    last_report_date = report_store.load()
    zone = ZoneInfo(timezone)
    while True:
        try:
            current = await capture_state(client, registry)
            if previous:
                for message in transition_messages(previous, current, registry):
                    for owner_id in owner_ids:
                        await bot.send_message(owner_id, message)
            previous = current
            store.save(current)

            now = datetime.now(zone)
            if now.hour == report_hour and last_report_date != now.date():
                summary = "🌙 <b>Вечерний отчёт</b>\n\n" + await all_sites_summary(
                    client, registry.all()
                )
                for owner_id in owner_ids:
                    await bot.send_message(owner_id, summary)
                last_report_date = now.date()
                report_store.save(last_report_date)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Monitoring iteration failed")
        await asyncio.sleep(interval_seconds)
