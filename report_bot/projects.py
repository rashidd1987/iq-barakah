from dataclasses import dataclass


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
