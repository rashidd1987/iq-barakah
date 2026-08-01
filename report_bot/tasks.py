"""Persistent owner tasks with an append-only decision journal."""

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path
import secrets
from typing import Literal


TaskStatus = Literal["open", "done", "canceled"]


@dataclass(frozen=True)
class OwnerTask:
    id: str
    project_key: str
    title: str
    due_date: str
    success_criterion: str
    responsible: str
    status: TaskStatus
    created_at: str
    created_by: int
    completed_at: str | None = None
    completed_by: int | None = None
    completion_evidence: str | None = None
    canceled_at: str | None = None
    canceled_by: int | None = None
    cancel_reason: str | None = None
    rescheduled_count: int = 0


@dataclass(frozen=True)
class TaskEvent:
    event: str
    task_id: str
    occurred_at: str
    actor_id: int
    details: str | None = None


def parse_task_details(value: str) -> tuple[str, date, str]:
    parts = [part.strip() for part in value.split("|")]
    if len(parts) != 3:
        raise ValueError(
            "Формат: задача | ГГГГ-ММ-ДД | критерий готовности"
        )
    title, due_raw, criterion = parts
    if not 3 <= len(title) <= 300:
        raise ValueError("Описание задачи должно содержать от 3 до 300 символов")
    if not 3 <= len(criterion) <= 500:
        raise ValueError("Критерий готовности должен содержать от 3 до 500 символов")
    try:
        due_date = date.fromisoformat(due_raw)
    except ValueError:
        raise ValueError("Срок укажите в формате ГГГГ-ММ-ДД") from None
    return title, due_date, criterion


class TaskStore:
    def __init__(self, data_dir: str) -> None:
        self._path = Path(data_dir) / "owner_tasks.json"
        self._tasks: dict[str, OwnerTask] = {}
        self._events: list[TaskEvent] = []
        self._load()

    def create(
        self,
        *,
        project_key: str,
        title: str,
        due_date: date,
        success_criterion: str,
        created_by: int,
        responsible: str = "Владелец",
        now: datetime | None = None,
    ) -> OwnerTask:
        current = now or datetime.now(timezone.utc)
        task = OwnerTask(
            id=secrets.token_urlsafe(6),
            project_key=project_key,
            title=title.strip(),
            due_date=due_date.isoformat(),
            success_criterion=success_criterion.strip(),
            responsible=responsible.strip() or "Владелец",
            status="open",
            created_at=current.isoformat(),
            created_by=created_by,
        )
        if not 3 <= len(task.title) <= 300:
            raise ValueError("Описание задачи должно содержать от 3 до 300 символов")
        if not 3 <= len(task.success_criterion) <= 500:
            raise ValueError("Критерий готовности должен содержать от 3 до 500 символов")
        self._tasks[task.id] = task
        self._events.append(
            TaskEvent("created", task.id, current.isoformat(), created_by)
        )
        try:
            self._save()
        except OSError:
            self._tasks.pop(task.id, None)
            self._events.pop()
            raise
        return task

    def get(self, task_id: str) -> OwnerTask | None:
        return self._tasks.get(task_id)

    def find_open(self, project_key: str, title: str) -> OwnerTask | None:
        normalized = title.strip().casefold()
        return next(
            (
                task
                for task in self._tasks.values()
                if task.status == "open"
                and task.project_key == project_key
                and task.title.casefold() == normalized
            ),
            None,
        )

    def open(self) -> tuple[OwnerTask, ...]:
        return tuple(
            sorted(
                (task for task in self._tasks.values() if task.status == "open"),
                key=lambda task: (task.due_date, task.created_at),
            )
        )

    def due(self, on_date: date) -> tuple[OwnerTask, ...]:
        return tuple(
            task for task in self.open() if date.fromisoformat(task.due_date) <= on_date
        )

    def complete(
        self,
        task_id: str,
        *,
        completed_by: int,
        evidence: str | None = None,
        now: datetime | None = None,
    ) -> OwnerTask | None:
        task = self._tasks.get(task_id)
        if task is None or task.status != "open":
            return task
        if evidence is not None and not 3 <= len(evidence.strip()) <= 500:
            raise ValueError(
                "Подтверждение результата должно содержать от 3 до 500 символов"
            )
        current = now or datetime.now(timezone.utc)
        completed = OwnerTask(
            **{
                **asdict(task),
                "status": "done",
                "completed_at": current.isoformat(),
                "completed_by": completed_by,
                "completion_evidence": evidence.strip() if evidence else None,
            }
        )
        self._tasks[task_id] = completed
        self._events.append(
            TaskEvent("completed", task_id, current.isoformat(), completed_by)
        )
        try:
            self._save()
        except OSError:
            self._tasks[task_id] = task
            self._events.pop()
            raise
        return completed

    def reschedule(
        self,
        task_id: str,
        *,
        due_date: date,
        reason: str,
        actor_id: int,
        now: datetime | None = None,
    ) -> OwnerTask | None:
        task = self._tasks.get(task_id)
        if task is None or task.status != "open":
            return task
        reason = reason.strip()
        if not 3 <= len(reason) <= 500:
            raise ValueError("Причина переноса должна содержать от 3 до 500 символов")
        current = now or datetime.now(timezone.utc)
        previous_due = task.due_date
        updated = OwnerTask(
            **{
                **asdict(task),
                "due_date": due_date.isoformat(),
                "rescheduled_count": task.rescheduled_count + 1,
            }
        )
        self._tasks[task_id] = updated
        self._events.append(
            TaskEvent(
                "rescheduled",
                task_id,
                current.isoformat(),
                actor_id,
                f"{previous_due} -> {due_date.isoformat()}: {reason}",
            )
        )
        try:
            self._save()
        except OSError:
            self._tasks[task_id] = task
            self._events.pop()
            raise
        return updated

    def cancel(
        self,
        task_id: str,
        *,
        reason: str,
        canceled_by: int,
        now: datetime | None = None,
    ) -> OwnerTask | None:
        task = self._tasks.get(task_id)
        if task is None or task.status != "open":
            return task
        reason = reason.strip()
        if not 3 <= len(reason) <= 500:
            raise ValueError("Причина отмены должна содержать от 3 до 500 символов")
        current = now or datetime.now(timezone.utc)
        canceled = OwnerTask(
            **{
                **asdict(task),
                "status": "canceled",
                "canceled_at": current.isoformat(),
                "canceled_by": canceled_by,
                "cancel_reason": reason,
            }
        )
        self._tasks[task_id] = canceled
        self._events.append(
            TaskEvent("canceled", task_id, current.isoformat(), canceled_by, reason)
        )
        try:
            self._save()
        except OSError:
            self._tasks[task_id] = task
            self._events.pop()
            raise
        return canceled

    def events(self) -> tuple[TaskEvent, ...]:
        return tuple(self._events)

    def _load(self) -> None:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            for item in payload.get("tasks", []):
                item.setdefault("completion_evidence", None)
                item.setdefault("canceled_at", None)
                item.setdefault("canceled_by", None)
                item.setdefault("cancel_reason", None)
                item.setdefault("rescheduled_count", 0)
                task = OwnerTask(**item)
                self._tasks[task.id] = task
            events = []
            for item in payload.get("events", []):
                item.setdefault("details", None)
                events.append(TaskEvent(**item))
            self._events = events
        except FileNotFoundError:
            return
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "tasks": [asdict(task) for task in self._tasks.values()],
                    "events": [asdict(event) for event in self._events],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self._path)
