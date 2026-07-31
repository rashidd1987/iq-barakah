"""Deterministic owner day-plan proposals with persistent acceptance state."""

from dataclasses import asdict, dataclass
from datetime import date
import json
from pathlib import Path
import secrets

from report_bot.monitor import ProjectState
from report_bot.projects import Project, ProjectRegistry
from report_bot.tasks import TaskStore


@dataclass(frozen=True)
class DayPlanSuggestion:
    id: str
    plan_date: str
    project_key: str
    title: str
    success_criterion: str
    reason: str
    accepted_task_id: str | None = None


def _routine_suggestion(project: Project, today: date) -> DayPlanSuggestion:
    presets = {
        "iqbarakah": (
            "Проверить путь участника IQ Barakah от входа до текущего урока",
            "Миниапп, PWA и приложение показывают одинаковый шаг и прогресс",
            "Критичных отклонений нет — проверяем основной путь пользователя",
        ),
        "mizanlife": (
            "Проверить главный пользовательский сценарий Mizan Life",
            "Основной сценарий выполняется без блокирующих ошибок",
            "Критичных отклонений нет — подтверждаем качество продукта",
        ),
        "mizanos": (
            "Проверить готовность Mizan OS к следующему релизу",
            "Статус, последняя сборка и один ключевой сценарий проверены",
            "Критичных отклонений нет — готовим следующий управляемый релиз",
        ),
    }
    title, criterion, reason = presets.get(
        project.key,
        (
            f"Проверить основной сценарий проекта {project.title}",
            "Основной пользовательский сценарий проходит без блокирующих ошибок",
            "Критичных отклонений нет — выполняем контроль качества",
        ),
    )
    return DayPlanSuggestion(
        id="",
        plan_date=today.isoformat(),
        project_key=project.key,
        title=title,
        success_criterion=criterion,
        reason=reason,
    )


def build_day_plan(
    states: dict[str, ProjectState],
    registry: ProjectRegistry,
    task_store: TaskStore,
    today: date,
    active_project: str,
    limit: int = 3,
) -> tuple[DayPlanSuggestion, ...]:
    """Return concrete, non-duplicating proposals ordered by operational risk."""
    existing = {
        (task.project_key, task.title.casefold()) for task in task_store.open()
    }
    proposals: list[DayPlanSuggestion] = []

    def add(candidate: DayPlanSuggestion) -> None:
        key = (candidate.project_key, candidate.title.casefold())
        if key not in existing and all(
            (item.project_key, item.title.casefold()) != key for item in proposals
        ):
            proposals.append(candidate)

    projects = registry.all()
    for project in projects:
        state = states.get(project.key)
        if state is not None and not state.site_ok:
            add(
                DayPlanSuggestion(
                    id="",
                    plan_date=today.isoformat(),
                    project_key=project.key,
                    title=f"Восстановить доступность {project.title}",
                    success_criterion=(
                        "Сервис стабильно отвечает допустимым HTTP-статусом "
                        "в трёх последовательных проверках"
                    ),
                    reason="Обнаружена подтверждённая недоступность проекта",
                )
            )
    for project in projects:
        state = states.get(project.key)
        if (
            state is not None
            and state.workflow_status == "completed"
            and state.workflow_conclusion == "failure"
        ):
            add(
                DayPlanSuggestion(
                    id="",
                    plan_date=today.isoformat(),
                    project_key=project.key,
                    title=f"Разобрать последнюю неуспешную сборку {project.title}",
                    success_criterion=(
                        "Причина зафиксирована, исправление проверено или принято "
                        "явное решение отложить"
                    ),
                    reason="Последняя автоматическая сборка завершилась ошибкой",
                )
            )

    ordered = sorted(projects, key=lambda item: item.key != active_project)
    for project in ordered:
        if len(proposals) >= limit:
            break
        add(_routine_suggestion(project, today))
    return tuple(proposals[:limit])


class DayPlanStore:
    def __init__(self, data_dir: str) -> None:
        self._path = Path(data_dir) / "day_plan.json"
        self._items = self._load()

    def replace(
        self, plan_date: date, suggestions: tuple[DayPlanSuggestion, ...]
    ) -> tuple[DayPlanSuggestion, ...]:
        current = {
            (item.project_key, item.title): item
            for item in self._items.values()
            if item.plan_date == plan_date.isoformat()
        }
        updated: dict[str, DayPlanSuggestion] = {}
        for suggestion in suggestions:
            previous = current.get((suggestion.project_key, suggestion.title))
            item = DayPlanSuggestion(
                **{
                    **asdict(suggestion),
                    "id": previous.id if previous else secrets.token_urlsafe(6),
                    "accepted_task_id": (
                        previous.accepted_task_id if previous else None
                    ),
                }
            )
            updated[item.id] = item
        self._items = updated
        self._save()
        return tuple(updated.values())

    def get(self, suggestion_id: str) -> DayPlanSuggestion | None:
        return self._items.get(suggestion_id)

    def mark_accepted(
        self, suggestion_id: str, task_id: str
    ) -> DayPlanSuggestion | None:
        item = self._items.get(suggestion_id)
        if item is None:
            return None
        if item.accepted_task_id:
            return item
        accepted = DayPlanSuggestion(
            **{**asdict(item), "accepted_task_id": task_id}
        )
        self._items[item.id] = accepted
        self._save()
        return accepted

    def _load(self) -> dict[str, DayPlanSuggestion]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return {
                item["id"]: DayPlanSuggestion(**item)
                for item in raw
            }
        except (FileNotFoundError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                [asdict(item) for item in self._items.values()],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self._path)
