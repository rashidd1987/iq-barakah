"""Persistent owner idea inbox with portable exports."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets


@dataclass(frozen=True)
class Idea:
    id: str
    text: str
    project_key: str
    source: str
    created_at: str
    created_by: int


class IdeaStore:
    def __init__(self, data_dir: str) -> None:
        self._path = Path(data_dir) / "ideas.json"
        self._ideas: dict[str, Idea] = {}
        self._load()

    def create(
        self,
        *,
        text: str,
        project_key: str,
        source: str,
        created_by: int,
        now: datetime | None = None,
    ) -> Idea:
        normalized = text.strip()
        if not 3 <= len(normalized) <= 4000:
            raise ValueError("Идея должна содержать от 3 до 4000 символов")
        if source not in {"text", "voice"}:
            raise ValueError("Неизвестный источник идеи")
        current = now or datetime.now(timezone.utc)
        idea = Idea(
            id=secrets.token_urlsafe(6),
            text=normalized,
            project_key=project_key.strip(),
            source=source,
            created_at=current.isoformat(),
            created_by=created_by,
        )
        self._ideas[idea.id] = idea
        try:
            self._save()
        except OSError:
            self._ideas.pop(idea.id, None)
            raise
        return idea

    def all(self) -> tuple[Idea, ...]:
        return tuple(
            sorted(
                self._ideas.values(),
                key=lambda idea: idea.created_at,
                reverse=True,
            )
        )

    def export_markdown(self) -> str:
        lines = [
            "# Mizan Ideas",
            "",
            "Постоянная база идей собственника. Используйте этот файл как контекст для ИИ.",
            "",
        ]
        for idea in reversed(self.all()):
            created = datetime.fromisoformat(idea.created_at).strftime("%d.%m.%Y %H:%M UTC")
            lines.extend(
                [
                    f"## {idea.id} · {created}",
                    "",
                    f"- Проект: {idea.project_key}",
                    f"- Источник: {'голос' if idea.source == 'voice' else 'текст'}",
                    "",
                    idea.text,
                    "",
                ]
            )
        return "\n".join(lines)

    def export_json(self) -> str:
        return json.dumps(
            {"version": 1, "ideas": [asdict(idea) for idea in reversed(self.all())]},
            ensure_ascii=False,
            indent=2,
        )

    def _load(self) -> None:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            for item in payload.get("ideas", []):
                idea = Idea(**item)
                self._ideas[idea.id] = idea
        except FileNotFoundError:
            return
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {"version": 1, "ideas": [asdict(idea) for idea in self._ideas.values()]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self._path)
