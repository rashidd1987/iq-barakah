from dataclasses import dataclass
import json
from pathlib import Path
import re
from urllib.parse import urlparse


@dataclass(frozen=True)
class Project:
    key: str
    title: str
    repo: str | None
    health_url: str


PROJECTS: tuple[Project, ...] = (
    Project(
        key="iqbarakah",
        title="IQ Barakah",
        repo="iq-barakah",
        health_url="https://iq-barakah.ru/",
    ),
    Project(
        key="mizanlife",
        title="Mizan Life",
        repo="mizan-life",
        health_url="https://mizanlife.ru/today",
    ),
    Project(
        key="mizanos",
        title="Mizan OS",
        repo=None,
        health_url="https://app.mizanos.ru/",
    ),
)

PROJECTS_BY_KEY = {project.key: project for project in PROJECTS}

KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")
REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def validate_project(key: str, title: str, health_url: str, repo: str | None) -> Project:
    key = key.strip().lower()
    title = title.strip()
    health_url = health_url.strip()
    repo = repo.strip() if repo else None
    if not KEY_PATTERN.fullmatch(key):
        raise ValueError("Ключ: 2–32 символа, только a-z, 0-9, _ и -")
    if not 2 <= len(title) <= 80:
        raise ValueError("Название должно содержать от 2 до 80 символов")
    parsed = urlparse(health_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username:
        raise ValueError("Адрес должен быть безопасным URL, начинающимся с https://")
    if repo and not REPO_PATTERN.fullmatch(repo):
        raise ValueError("Репозиторий укажите как имя без ссылки или поставьте -")
    return Project(key=key, title=title, repo=repo, health_url=health_url)


class ProjectRegistry:
    def __init__(self, data_dir: str) -> None:
        self._path = Path(data_dir) / "projects.json"
        self._projects = list(PROJECTS)
        self._load()

    def all(self) -> tuple[Project, ...]:
        return tuple(self._projects)

    def by_key(self, key: str) -> Project | None:
        return next((project for project in self._projects if project.key == key), None)

    def add(self, project: Project) -> None:
        if self.by_key(project.key):
            raise ValueError("Проект с таким ключом уже существует")
        self._projects.append(project)
        try:
            self._save()
        except OSError:
            self._projects.remove(project)
            raise

    def _load(self) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            for item in raw:
                project = validate_project(
                    item["key"], item["title"], item["health_url"], item.get("repo")
                )
                if not self.by_key(project.key):
                    self._projects.append(project)
        except FileNotFoundError:
            return
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        custom = [project.__dict__ for project in self._projects if project not in PROJECTS]
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(custom, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(self._path)
