"""Persistent, owner-maintained project knowledge for AI prompts."""

from dataclasses import dataclass
import json
from pathlib import Path

from report_bot.projects import Project


DEFAULT_BRIEFS = {
    "iqbarakah": (
        "IQ Barakah — образовательная исламская программа и цифровая система "
        "ежедневного развития. Клиенты: Telegram-бот, Mini App, Android и PWA "
        "используют единый backend и прогресс ученика. Основные функции: уроки, "
        "задания, трекер, мухасаба, диагностика, путь обучения и профиль. "
        "Не является банком, МФО или страховой компанией."
    ),
    "mizanlife": (
        "Mizan Life — персональная PWA-система осознанной организации "
        "повседневной жизни. Подтверждённые разделы: Сегодня, задачи, привычки, "
        "намаз, фокус, вечерний обзор и Jarvas. Задачи поддерживают главную и "
        "текущую задачу, завершение, перенос, восстановление незавершённых дел "
        "и участвуют в едином дневном прогрессе Today. Вечерний обзор помогает "
        "подвести итог и закрыть день. Текущий private-beta MVP хранит данные "
        "локально в браузере без облачной синхронизации между устройствами. "
        "Не является страхованием жизни, МФО, банком или финансовым продуктом."
    ),
    "mizanos": (
        "Mizan OS — отдельное веб-приложение экосистемы Mizan. Подробный "
        "продуктовый паспорт ещё не заполнен владельцем. Нельзя делать выводы "
        "о назначении продукта только по названию; при необходимости нужно "
        "задать владельцу уточняющий вопрос."
    ),
}

PROJECT_ALIASES = {
    "iqbarakah": ("iq barakah", "iq-barakah", "айкью барака", "барака"),
    "mizanlife": ("mizan life", "mizan-life", "мизан лайф"),
    "mizanos": ("mizan os", "mizan-os", "мизан ос"),
}


@dataclass(frozen=True)
class ProjectKnowledge:
    project_key: str
    brief: str


class ProjectKnowledgeLibrary:
    def __init__(self, data_dir: str) -> None:
        self._path = Path(data_dir) / "project_knowledge.json"
        self._briefs = dict(DEFAULT_BRIEFS)
        self._active_project = "iqbarakah"
        self._load()

    @property
    def active_project(self) -> str:
        return self._active_project

    def brief(self, project_key: str) -> str:
        return self._briefs.get(
            project_key,
            "Паспорт проекта ещё не заполнен. Не угадывай назначение по названию.",
        )

    def set_brief(self, project_key: str, brief: str) -> None:
        normalized = " ".join(brief.split())
        if not 20 <= len(normalized) <= 2000:
            raise ValueError("Описание должно содержать от 20 до 2000 символов")
        previous = self._briefs.get(project_key)
        self._briefs[project_key] = normalized
        try:
            self._save()
        except OSError:
            if previous is None:
                self._briefs.pop(project_key, None)
            else:
                self._briefs[project_key] = previous
            raise

    def set_active(self, project_key: str, projects: tuple[Project, ...]) -> None:
        if not any(project.key == project_key for project in projects):
            raise ValueError("Проект не найден")
        previous = self._active_project
        self._active_project = project_key
        try:
            self._save()
        except OSError:
            self._active_project = previous
            raise

    def resolve(self, task: str, projects: tuple[Project, ...]) -> Project:
        normalized = task.casefold()
        for project in projects:
            aliases = (
                project.key.casefold(),
                project.title.casefold(),
                project.title.casefold().replace(" ", "-"),
            ) + PROJECT_ALIASES.get(project.key, ())
            if any(alias in normalized for alias in aliases):
                return project
        active = next(
            (
                project
                for project in projects
                if project.key == self._active_project
            ),
            None,
        )
        return active or projects[0]

    def ai_task(self, project: Project, task: str) -> str:
        return (
            "Используй паспорт проекта как источник истины. Не определяй сферу "
            "продукта по одному названию. Если данных недостаточно, прямо укажи "
            "это и задай один уточняющий вопрос. Не отправляй и не запрашивай "
            "секреты или персональные данные.\n\n"
            f"Проект: {project.title}\n"
            f"Паспорт: {self.brief(project.key)}\n\n"
            f"Задача владельца: {task}"
        )

    def _load(self) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            briefs = raw.get("briefs", {})
            if isinstance(briefs, dict):
                for key, brief in briefs.items():
                    if isinstance(key, str) and isinstance(brief, str):
                        normalized = " ".join(brief.split())
                        if 20 <= len(normalized) <= 2000:
                            self._briefs[key] = normalized
            active = raw.get("active_project")
            if isinstance(active, str) and active:
                self._active_project = active
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
                    "active_project": self._active_project,
                    "briefs": self._briefs,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self._path)
