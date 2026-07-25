import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp

from report_bot.projects import PROJECTS, Project


@dataclass(frozen=True)
class SiteStatus:
    ok: bool
    status_code: int | None
    latency_ms: int | None


class StatusClient:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        github_owner: str,
        github_token: str,
    ) -> None:
        self._session = session
        self._github_owner = github_owner
        self._github_headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "mizan-project-reports",
        }
        if github_token:
            self._github_headers["Authorization"] = f"Bearer {github_token}"

    async def site_status(self, project: Project) -> SiteStatus:
        loop = asyncio.get_running_loop()
        started_at = loop.time()
        try:
            async with self._session.get(
                project.health_url,
                allow_redirects=True,
            ) as response:
                latency_ms = round((loop.time() - started_at) * 1000)
                return SiteStatus(
                    ok=200 <= response.status < 400 or response.status in {401, 403},
                    status_code=response.status,
                    latency_ms=latency_ms,
                )
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return SiteStatus(ok=False, status_code=None, latency_ms=None)

    async def repo(self, name: str) -> dict[str, Any] | None:
        payload = await self._github_get(f"/repos/{self._github_owner}/{name}")
        return payload if isinstance(payload, dict) else None

    async def workflow_runs(
        self,
        name: str,
        *,
        status: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]] | None:
        query = f"?per_page={limit}"
        if status:
            query += f"&status={status}"
        payload = await self._github_get(
            f"/repos/{self._github_owner}/{name}/actions/runs{query}"
        )
        if not isinstance(payload, dict):
            return None
        runs = payload.get("workflow_runs")
        return runs if isinstance(runs, list) else None

    async def _github_get(self, path: str) -> Any | None:
        try:
            async with self._session.get(
                f"https://api.github.com{path}",
                headers=self._github_headers,
            ) as response:
                if response.status in {401, 403, 404}:
                    return None
                response.raise_for_status()
                return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            return None


def format_datetime(value: str | None) -> str:
    if not value:
        return "нет данных"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "нет данных"
    return parsed.astimezone().strftime("%d.%m.%Y %H:%M")


def run_icon(conclusion: str | None, status: str | None = None) -> str:
    if status and status != "completed":
        return "⏳"
    return {
        "success": "✅",
        "failure": "❌",
        "cancelled": "⚪️",
        "skipped": "⚪️",
    }.get(conclusion or "", "⚠️")


async def project_summary(client: StatusClient, project: Project) -> str:
    site, repo, runs = await asyncio.gather(
        client.site_status(project),
        client.repo(project.repo) if project.repo else asyncio.sleep(0, result=None),
        (
            client.workflow_runs(project.repo, limit=1)
            if project.repo
            else asyncio.sleep(0, result=None)
        ),
    )

    site_line = (
        f"✅ Сайт отвечает: {site.status_code}, {site.latency_ms} мс"
        if site.ok
        else "❌ Сайт не отвечает"
    )
    lines = [f"<b>{project.title}</b>", site_line]

    if project.repo and repo is None:
        lines.append("⚠️ GitHub: доступ не подключён")
    elif repo:
        lines.append(f"📦 GitHub обновлён: {format_datetime(repo.get('pushed_at'))}")

    if runs:
        latest = runs[0]
        lines.append(
            f"{run_icon(latest.get('conclusion'), latest.get('status'))} "
            f"{latest.get('name') or 'Workflow'} — "
            f"{latest.get('conclusion') or latest.get('status') or 'unknown'}"
        )

    lines.append(f'🔗 <a href="{project.health_url}">Открыть проект</a>')
    return "\n".join(lines)


async def all_sites_summary(
    client: StatusClient, projects: tuple[Project, ...] = PROJECTS
) -> str:
    statuses = await asyncio.gather(
        *(client.site_status(project) for project in projects)
    )
    lines = ["<b>Состояние проектов</b>"]
    for project, status in zip(projects, statuses, strict=True):
        if status.ok:
            lines.append(
                f"✅ {project.title}: {status.status_code}, {status.latency_ms} мс"
            )
        else:
            lines.append(f"❌ {project.title}: недоступен")
    return "\n".join(lines)
