"""Deterministic owner council for safe project decision support."""

from dataclasses import dataclass

from report_bot.projects import Project


@dataclass(frozen=True)
class CouncilContext:
    project: Project
    site_ok: bool
    status_code: int | None
    latest_workflow: str | None
    latest_status: str | None


@dataclass(frozen=True)
class CouncilView:
    role: str
    focus: str
    recommendation: str


def select_project(task: str, projects: tuple[Project, ...]) -> Project:
    normalized = task.casefold()
    aliases = {
        "iqbarakah": ("iq barakah", "iq-barakah", "барака", "пва", "pwa"),
        "mizanlife": ("mizan life", "mizan-life", "мизан лайф"),
        "mizanos": ("mizan os", "mizan-os", "мизан ос"),
    }
    for project in projects:
        candidates = (project.key.casefold(), project.title.casefold())
        candidates += aliases.get(project.key, ())
        if any(candidate in normalized for candidate in candidates):
            return project
    return projects[0]


def council_views(task: str, context: CouncilContext) -> tuple[CouncilView, ...]:
    unhealthy = not context.site_ok
    failed = context.latest_status == "failure"
    technical_state = (
        f"сайт отвечает {context.status_code}"
        if context.site_ok
        else "сайт сейчас недоступен"
    )
    workflow_state = (
        f"последний workflow: {context.latest_workflow} — {context.latest_status}"
        if context.latest_workflow
        else "данных о workflow нет"
    )
    return (
        CouncilView(
            "CEO · стратегия",
            "ценность и приоритет",
            (
                "Сначала восстановить доступность, затем возвращаться к развитию."
                if unhealthy
                else "Сформулировать один измеримый результат и выбрать самый короткий путь к нему."
            ),
        ),
        CouncilView(
            "CTO · технологии",
            "надёжность и архитектура",
            f"{technical_state}; {workflow_state}. Начать с read-only проверки и не смешивать исправление с релизом.",
        ),
        CouncilView(
            "CPO · продукт",
            "ценность для ученика",
            "Проверить полный пользовательский путь и убедиться, что изменение решает конкретную проблему ученика.",
        ),
        CouncilView(
            "CMO · маркетинг",
            "рост и коммуникация",
            "До продвижения проверить понятность первого экрана, обещание продукта и точку активации.",
        ),
        CouncilView(
            "CCO · клиентский опыт",
            "поддержка и доверие",
            "Оценить, поймёт ли пользователь следующий шаг без инструкции и куда он обратится при ошибке.",
        ),
        CouncilView(
            "CFO · экономика",
            "стоимость и отдача",
            "Предпочесть малый обратимый эксперимент; заранее определить стоимость, срок и критерий остановки.",
        ),
        CouncilView(
            "CISO · служба безопасности",
            "доступы и угрозы",
            "Не передавать секреты, не расширять токены и не выполнять production-действия без отдельного разрешения.",
        ),
        CouncilView(
            "COO · операции",
            "исполнение и контроль",
            (
                "Сначала локализовать сбой и назначить контрольную проверку восстановления."
                if unhealthy or failed
                else "Разбить работу на проверку, подготовку, разрешение, выпуск и наблюдение после выпуска."
            ),
        ),
        CouncilView(
            "Data/DPO · данные",
            "метрики и приватность",
            "Использовать минимальные данные, определить метрику до изменения и не выводить личные данные в отчёты.",
        ),
        CouncilView(
            "Красная команда · критик",
            "почему план может провалиться",
            "Главный риск — принять красивую идею без доказательства проблемы; сначала ищем опровергающие факты.",
        ),
    )


def executive_recommendation(context: CouncilContext) -> tuple[str, ...]:
    if not context.site_ok:
        return (
            "1. Read-only диагностика доступности и последних ошибок.",
            "2. План восстановления без изменений production.",
            "3. После диагностики — отдельный запрос на конкретное действие.",
        )
    if context.latest_status == "failure":
        return (
            "1. Разобрать последнюю ошибку без изменений.",
            "2. Подготовить минимальное исправление через PR.",
            "3. Выпускать только после зелёного CI и вашего разрешения.",
        )
    return (
        "1. Углублённая read-only проверка проекта.",
        "2. Подготовка конкретного плана с рисками и критериями успеха.",
        "3. Для IQ Barakah — безопасно подготовить PWA-релиз с отдельным production-разрешением.",
    )
