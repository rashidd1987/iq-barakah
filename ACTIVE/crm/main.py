from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, Response, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from sqlalchemy import Select, and_, desc, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import aliased

from bot_v2.config import _load_database_url
from bot_v2.db.models import (
    DiagResult,
    MuhasabaLog,
    Participant,
    Payment,
    TaskCompletion,
    TrackerRecord,
    User,
    WeekAck,
    WheelRecord,
)


BASE_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.dirname(BASE_DIR)
SESSION_COOKIE = "iqb_crm_session"
CRM_TASKS_FILE = os.path.join(BASE_DIR, "storage", "team_tasks.json")
CRM_USERS_FILE = os.path.join(BASE_DIR, "storage", "crm_users.json")
BUSINESS_OS_FILE = os.path.join(BASE_DIR, "storage", "business_os.json")
CRM_ACTIVITY_FILE = os.path.join(BASE_DIR, "storage", "crm_activity.json")

load_dotenv(os.path.join(PROJECT_DIR, ".env"))

app = FastAPI(title="IQ Barakah CRM", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

engine: AsyncEngine | None = None
session_factory: async_sessionmaker[AsyncSession] | None = None

LEVEL_SEGMENTS = {
    "I": ("А", "I"),
    "II": ("Б", "II"),
    "III": ("В", "Г", "III"),
}

TARIFF_VIEWS = {
    "vakt": ("ВАКТ", "Первый фундамент · 6 недель"),
    "s_half": ("IQ Barakah · 4 недели", "Половина сезона · тест системы"),
    "s1_full": ("IQ Barakah · Сезон 1", "Основание · КТО ты есть · 8 недель"),
    "s2_full": ("IQ Barakah · Сезон 2", "Строительство · КАК ты живёшь · 8 недель"),
    "s3_season": ("IQ Barakah · Сезон 3", "Наследие · ЗАЧЕМ ты живёшь · 8 недель"),
    "s3_full": ("IQ Barakah · 3 сезона", "Вся программа · 24 недели"),
    "jamaat": ("Джамаат · месяц", "Сообщество и куратор · 50 000 ₽/мес"),
    "jamaat_full": ("Джамаат · программа", "Полный путь в группе · 270 000 ₽"),
    "leader": ("Лидер Уммы · месяц", "1 на 1 с основателем · 250 000 ₽/мес"),
    "leader_6m": ("Лидер Уммы · 6 месяцев", "Премиальное сопровождение · 1 350 000 ₽"),
}

TARIFF_OPTIONS = tuple(TARIFF_VIEWS.keys())
TARIFF_AMOUNTS = {
    "vakt": 1500,
    "s_half": 5000,
    "s1_full": 10000,
    "s2_full": 10000,
    "s3_season": 10000,
    "s3_full": 27000,
    "jamaat": 50000,
    "jamaat_full": 270000,
    "leader": 250000,
    "leader_6m": 1350000,
}
TARIFF_CHARITY = {
    "vakt": 300,
    "s_half": 1000,
    "s1_full": 2000,
    "s2_full": 2000,
    "s3_season": 2000,
    "s3_full": 5400,
    "jamaat": 10000,
    "jamaat_full": 54000,
    "leader": 0,
    "leader_6m": 0,
}
TEAM_MEMBERS = ("Рашид", "Куратор", "Маркетолог", "Продажи", "Методолог")
TASK_STATUSES = ("todo", "doing", "done")
TASK_PRIORITIES = ("high", "normal", "low")
CRM_ROLES = {
    "owner": "Владелец",
    "admin": "Админ",
    "curator": "Куратор",
    "sales": "Продажи",
    "marketing": "Маркетинг",
}
CRM_ROLE_ACCESS = {
    "owner": "полный доступ, доступы, задачи, финансы, рефералки",
    "admin": "задачи, ученики, финансы, маркетинг",
    "curator": "ученики, обучение, задачи",
    "sales": "оплаты, ученики, задачи, рефералки",
    "marketing": "маркетинг, воронка, рефералки",
}
DESIGN_THEMES = {
    "executive": {
        "name": "Executive",
        "desc": "кабинет собственника: деньги, риски, действия",
    },
    "analytics": {
        "name": "Analytics",
        "desc": "BI-вид: графики, воронка, маркетинг",
    },
    "premium": {
        "name": "Premium",
        "desc": "бренд IQ Barakah: зелёный, золото, мягкий премиум",
    },
}


@dataclass(frozen=True)
class StudentRow:
    user: User
    participant: Participant | None
    last_diag: DiagResult | None
    last_activity: datetime | None

    @property
    def status(self) -> str:
        if self.participant and self.participant.graduated_at:
            return "graduated"
        if self.participant and self.participant.is_active:
            return "active"
        return "inactive"


@dataclass(frozen=True)
class BarakahMetrics:
    tasks_done: int
    tasks_total: int
    quran_pages: int
    good_deeds: int
    namaz_on_time: int
    azkar_days: int
    muhasaba_days: int
    streak_days: int

    @property
    def task_pct(self) -> int:
        if not self.tasks_total:
            return 0
        return round(self.tasks_done / self.tasks_total * 100)

    @property
    def score(self) -> int:
        task_score = min(self.task_pct, 100) * 0.32
        quran_score = min(self.quran_pages / 35 * 100, 100) * 0.18
        deeds_score = min(self.good_deeds / 21 * 100, 100) * 0.14
        namaz_score = min(self.namaz_on_time / 35 * 100, 100) * 0.18
        rhythm_score = min((self.azkar_days + self.muhasaba_days + self.streak_days) / 21 * 100, 100) * 0.18
        return round(task_score + quran_score + deeds_score + namaz_score + rhythm_score)


async def get_db() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global engine, session_factory
    if session_factory:
        return session_factory

    try:
        database_url = _load_database_url()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return session_factory


@app.on_event("shutdown")
async def shutdown() -> None:
    if engine:
        await engine.dispose()


async def require_admin(request: Request) -> None:
    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_PASSWORD is not configured",
        )
    if not current_crm_user(request):
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})


async def require_owner(request: Request) -> dict[str, Any]:
    user = current_crm_user(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    if user.get("role") not in {"owner", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
    return user


def fmt_dt(value: datetime | None) -> str:
    if not value:
        return "-"
    return value.astimezone().strftime("%d.%m.%Y %H:%M")


def status_label(value: str) -> str:
    return {
        "active": "Активен",
        "graduated": "Завершил",
        "inactive": "Неактивен",
    }.get(value, value)


def payment_status_label(value: str) -> str:
    return {
        "paid": "Оплачен",
        "pending": "Ожидает",
        "failed": "Ошибка",
        "refunded": "Возврат",
    }.get(value, value)


def task_status_label(value: str) -> str:
    return {
        "todo": "Нужно сделать",
        "doing": "В работе",
        "done": "Готово",
    }.get(value, value)


def task_priority_label(value: str) -> str:
    return {
        "high": "Высокий",
        "normal": "Обычный",
        "low": "Низкий",
    }.get(value, value)


def role_label(value: str) -> str:
    return CRM_ROLES.get(value, value)


def gender_label(value: bool | None) -> str:
    if value is True:
        return "Женщины"
    if value is False:
        return "Мужчины"
    return "Не указан"


def level_label(value: str | None) -> str:
    return {
        "А": "I",
        "I": "I",
        "Б": "II",
        "II": "II",
        "В": "III",
        "Г": "III",
        "III": "III",
    }.get(value or "", value or "-")


def level_filter_values(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return LEVEL_SEGMENTS.get(level_label(value), (value,))


def tariff_name(value: str | None) -> str:
    if not value:
        return "-"
    return TARIFF_VIEWS.get(value, (value, ""))[0]


def tariff_desc(value: str | None) -> str:
    if not value:
        return "-"
    return TARIFF_VIEWS.get(value, ("", "Описание тарифа не найдено"))[1]


def tariff_catalog() -> list[dict[str, Any]]:
    groups = {
        "vakt": "Вход",
        "s_half": "Сезоны",
        "s1_full": "Сезоны",
        "s2_full": "Сезоны",
        "s3_season": "Сезоны",
        "s3_full": "Сезоны",
        "jamaat": "Джамаат",
        "jamaat_full": "Джамаат",
        "leader": "Премиум",
        "leader_6m": "Премиум",
    }
    return [
        {
            "id": tariff_id,
            "group": groups.get(tariff_id, "Другое"),
            "name": tariff_name(tariff_id),
            "desc": tariff_desc(tariff_id),
            "amount": TARIFF_AMOUNTS[tariff_id],
            "charity": TARIFF_CHARITY.get(tariff_id, 0),
        }
        for tariff_id in TARIFF_OPTIONS
    ]


def money(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{value:,}".replace(",", " ") + " ₽"


def progress_width(value: int | None) -> int:
    if value is None:
        return 0
    return max(0, min(int(value), 100))


def short_json(value: Any, limit: int = 220) -> str:
    if value is None:
        return "-"
    if isinstance(value, datetime):
        text = fmt_dt(value)
    elif isinstance(value, date):
        text = value.strftime("%d.%m.%Y")
    elif isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "..."


def records_label(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "запись"
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return "записи"
    return "записей"


def days_since(value: datetime | None) -> int | None:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - value.astimezone(timezone.utc)).days)


def session_token(password: str) -> str:
    secret = os.environ.get("CRM_SESSION_SECRET", "iqb-crm")
    return hashlib.sha256(f"{secret}:{password}".encode("utf-8")).hexdigest()


def password_hash(password: str) -> str:
    secret = os.environ.get("CRM_SESSION_SECRET", "iqb-crm")
    return hashlib.sha256(f"{secret}:crm-user:{password}".encode("utf-8")).hexdigest()


def user_session_token(username: str, stored_hash: str) -> str:
    secret = os.environ.get("CRM_SESSION_SECRET", "iqb-crm")
    return hashlib.sha256(f"{secret}:session:{username}:{stored_hash}".encode("utf-8")).hexdigest()


def slugify_code(value: str) -> str:
    cleaned = "".join(ch.lower() for ch in value.strip() if ch.isalnum())
    return cleaned or uuid.uuid4().hex[:8]


def design_theme(value: str | None) -> str:
    return value if value in DESIGN_THEMES else "premium"


templates.env.filters["dt"] = fmt_dt
templates.env.filters["status_label"] = status_label
templates.env.filters["payment_status_label"] = payment_status_label
templates.env.filters["task_status_label"] = task_status_label
templates.env.filters["task_priority_label"] = task_priority_label
templates.env.filters["role_label"] = role_label
templates.env.filters["gender_label"] = gender_label
templates.env.filters["level_label"] = level_label
templates.env.filters["tariff_name"] = tariff_name
templates.env.filters["tariff_desc"] = tariff_desc
templates.env.filters["money"] = money
templates.env.filters["progress_width"] = progress_width
templates.env.filters["short_json"] = short_json
templates.env.filters["records_label"] = records_label


@app.exception_handler(HTTPException)
async def crm_http_exception_handler(request: Request, exc: HTTPException) -> Response:
    if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE and str(exc.detail).startswith("DATABASE_URL"):
        return templates.TemplateResponse(
            "db_setup.html",
            {"request": request, "message": exc.detail},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return await http_exception_handler(request, exc)


@app.exception_handler(SQLAlchemyError)
async def crm_db_exception_handler(request: Request, exc: SQLAlchemyError) -> Response:
    return render_db_error(request, str(exc.__cause__ or exc))


@app.exception_handler(OSError)
async def crm_os_exception_handler(request: Request, exc: OSError) -> Response:
    return render_db_error(request, str(exc))


def render_db_error(request: Request, message: str) -> Response:
    return templates.TemplateResponse(
        "db_error.html",
        {
            "request": request,
            "message": message,
        },
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def record(**kwargs: Any) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


def admin_user() -> dict[str, Any] | None:
    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        return None
    return {
        "id": "owner",
        "username": "admin",
        "display_name": "Рашид",
        "role": "owner",
        "password_hash": password_hash(password),
        "referral_code": "rashid",
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def load_crm_users() -> list[dict[str, Any]]:
    if not os.path.exists(CRM_USERS_FILE):
        return []
    try:
        with open(CRM_USERS_FILE, encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def save_crm_users(users: list[dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(CRM_USERS_FILE), exist_ok=True)
    with open(CRM_USERS_FILE, "w", encoding="utf-8") as file:
        json.dump(users, file, ensure_ascii=False, indent=2)


def team_accounts() -> list[dict[str, Any]]:
    users = load_crm_users()
    owner = admin_user()
    return ([owner] if owner else []) + users


def current_crm_user(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get(SESSION_COOKIE, "")
    owner = admin_user()
    if owner and (
        hmac.compare_digest(token, session_token(os.environ.get("ADMIN_PASSWORD", "")))
        or hmac.compare_digest(token, user_session_token(owner["username"], owner["password_hash"]))
    ):
        return owner
    for user in load_crm_users():
        if user.get("active") is False:
            continue
        if hmac.compare_digest(token, user_session_token(str(user.get("username", "")), str(user.get("password_hash", "")))):
            return user
    return None


def authenticate_crm_user(username: str, password: str) -> dict[str, Any] | None:
    normalized = username.strip().lower()
    owner = admin_user()
    if owner and password == os.environ.get("ADMIN_PASSWORD") and normalized in {"", "admin", owner["username"]}:
        return owner
    hashed = password_hash(password)
    for user in load_crm_users():
        if user.get("active") is False:
            continue
        if normalized == str(user.get("username", "")).lower() and hmac.compare_digest(hashed, str(user.get("password_hash", ""))):
            return user
    return None


def create_crm_user(*, username: str, display_name: str, role: str, password: str) -> None:
    users = load_crm_users()
    normalized = slugify_code(username)
    existing_codes = {str(user.get("referral_code", "")) for user in users}
    existing_codes.add("rashid")
    referral_code = normalized
    if referral_code in existing_codes:
        referral_code = f"{normalized}{len(users) + 1}"
    user = {
        "id": uuid.uuid4().hex,
        "username": normalized,
        "display_name": display_name.strip() or normalized,
        "role": role if role in CRM_ROLES else "curator",
        "password_hash": password_hash(password),
        "referral_code": referral_code,
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    users = [item for item in users if str(item.get("username", "")).lower() != normalized]
    users.insert(0, user)
    save_crm_users(users)


def update_crm_user(user_id: str, *, active: bool | None = None) -> None:
    users = load_crm_users()
    for user in users:
        if user.get("id") == user_id and active is not None:
            user["active"] = active
            user["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_crm_users(users)


def seed_business_os() -> dict[str, list[dict[str, Any]]]:
    today = date.today().isoformat()
    return {
        "clients": [
            {"id": uuid.uuid4().hex, "first_name": "Амина", "last_name": "Садыкова", "company": "IQ Barakah", "phone": "+7 999 111-22-33", "email": "amina@example.com", "messenger": "Telegram", "source": "Telegram", "segment": "Премиум", "status": "active", "manager": "Куратор", "next_contact_at": today, "total_amount": 27000, "purchases_count": 2, "comments": "Готова к следующему уровню", "tags": "сезон, активная", "created_at": datetime.now(timezone.utc).isoformat()},
            {"id": uuid.uuid4().hex, "first_name": "Юсуф", "last_name": "Магомедов", "company": "", "phone": "+7 999 333-66-77", "email": "yusuf@example.com", "messenger": "Telegram", "source": "Рекомендации", "segment": "Риск", "status": "warm", "manager": "Продажи", "next_contact_at": today, "total_amount": 1500, "purchases_count": 1, "comments": "Нужно дожать оплату", "tags": "pending", "created_at": datetime.now(timezone.utc).isoformat()},
        ],
        "leads": [
            {"id": uuid.uuid4().hex, "client": "Юсуф Магомедов", "source": "Рекомендации", "campaign": "ref-kurator", "manager": "Продажи", "status": "new", "priority": "high", "need": "Войти в сезон", "planned_amount": 10000, "next_step": "Созвон и объяснение маршрута", "next_contact_at": today, "comments": "", "lost_reason": "", "created_at": datetime.now(timezone.utc).isoformat()},
        ],
        "deals": [
            {"id": uuid.uuid4().hex, "title": "Сезон 1 для Юсуфа", "client": "Юсуф Магомедов", "amount": 10000, "cost": 2000, "margin": 8000, "manager": "Продажи", "stage": "Связаться", "probability": 45, "expected_close_at": today, "next_step": "Написать сегодня", "comments": "", "lost_reason": "", "created_at": datetime.now(timezone.utc).isoformat()},
            {"id": uuid.uuid4().hex, "title": "Джамаат для Амины", "client": "Амина Садыкова", "amount": 50000, "cost": 10000, "margin": 40000, "manager": "Рашид", "stage": "Переговоры", "probability": 70, "expected_close_at": today, "next_step": "Показать ценность сопровождения", "comments": "", "lost_reason": "", "created_at": datetime.now(timezone.utc).isoformat()},
        ],
        "cashflow": [
            {"id": uuid.uuid4().hex, "date": today, "type": "income", "amount": 27000, "account": "Т-Банк", "category": "Продажи", "subcategory": "3 сезона", "counterparty": "Амина Садыкова", "project": "IQ Barakah", "branch": "Онлайн", "direction": "Обучение", "budget_item": "Выручка", "comment": "Оплата программы", "responsible": "Рашид", "approval_status": "approved", "author": "admin", "created_at": datetime.now(timezone.utc).isoformat()},
            {"id": uuid.uuid4().hex, "date": today, "type": "expense", "amount": 12000, "account": "Т-Банк", "category": "Маркетинг", "subcategory": "Реклама", "counterparty": "VK Ads", "project": "Лиды", "branch": "Онлайн", "direction": "Маркетинг", "budget_item": "Реклама", "comment": "Тест канала", "responsible": "Маркетолог", "approval_status": "pending", "author": "admin", "created_at": datetime.now(timezone.utc).isoformat()},
        ],
        "calendar": [
            {"id": uuid.uuid4().hex, "due_date": today, "amount": 12000, "counterparty": "VK Ads", "category": "Маркетинг", "project": "Лиды", "branch": "Онлайн", "priority": "high", "required": "yes", "responsible": "Маркетолог", "status": "planned", "comment": "Оплатить после проверки заявки", "created_at": datetime.now(timezone.utc).isoformat()},
        ],
        "projects": [
            {"id": uuid.uuid4().hex, "title": "CRM MVP", "goal": "Единый кабинет собственника", "budget": 0, "actual_expenses": 0, "manager": "Рашид", "progress": 62, "status": "active", "deadline": today, "risk": "Не перенести данные в PostgreSQL"},
        ],
        "knowledge": [
            {"id": uuid.uuid4().hex, "title": "Регламент обработки лида", "category": "Продажи", "tags": "лид, звонок, оплата", "content": "Ответить в течение 15 минут, зафиксировать потребность, поставить следующий контакт.", "access_role": "sales", "owner": "Рашид", "status": "active", "created_at": datetime.now(timezone.utc).isoformat()},
        ],
    }


def load_business_os() -> dict[str, list[dict[str, Any]]]:
    if not os.path.exists(BUSINESS_OS_FILE):
        data = seed_business_os()
        save_business_os(data)
        return data
    try:
        with open(BUSINESS_OS_FILE, encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        data = seed_business_os()
    for key, value in seed_business_os().items():
        data.setdefault(key, [] if isinstance(value, list) else value)
    return data


def save_business_os(data: dict[str, list[dict[str, Any]]]) -> None:
    os.makedirs(os.path.dirname(BUSINESS_OS_FILE), exist_ok=True)
    with open(BUSINESS_OS_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def load_activity_log() -> list[dict[str, Any]]:
    if not os.path.exists(CRM_ACTIVITY_FILE):
        return []
    try:
        with open(CRM_ACTIVITY_FILE, encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def save_activity_log(items: list[dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(CRM_ACTIVITY_FILE), exist_ok=True)
    with open(CRM_ACTIVITY_FILE, "w", encoding="utf-8") as file:
        json.dump(items[:300], file, ensure_ascii=False, indent=2)


def actor_name(request: Request | None) -> str:
    user = current_crm_user(request) if request else None
    if not user:
        return "CRM"
    return str(user.get("display_name") or user.get("username") or "CRM")


def log_activity(request: Request | None, *, action: str, entity: str, title: str, href: str = "", details: str = "") -> None:
    items = load_activity_log()
    items.insert(
        0,
        {
            "id": uuid.uuid4().hex,
            "actor": actor_name(request),
            "action": action,
            "entity": entity,
            "title": title,
            "href": href,
            "details": details,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    save_activity_log(items)


def create_business_record(section: str, payload: dict[str, Any]) -> None:
    data = load_business_os()
    payload["id"] = uuid.uuid4().hex
    payload["created_at"] = datetime.now(timezone.utc).isoformat()
    data.setdefault(section, []).insert(0, payload)
    save_business_os(data)


def update_business_record(section: str, record_id: str, updates: dict[str, Any]) -> None:
    data = load_business_os()
    for item in data.get(section, []):
        if item.get("id") == record_id:
            item.update(updates)
            item["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_business_os(data)


def delete_business_record(section: str, record_id: str) -> None:
    data = load_business_os()
    data[section] = [item for item in data.get(section, []) if item.get("id") != record_id]
    save_business_os(data)


def get_business_record(section: str, record_id: str) -> dict[str, Any] | None:
    for item in load_business_os().get(section, []):
        if item.get("id") == record_id:
            return item
    return None


def mizan_signature(secret: str, raw_body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def verify_mizan_signature(secret: str, raw_body: bytes, signature: str) -> bool:
    if not secret or not signature:
        return False
    return hmac.compare_digest(mizan_signature(secret, raw_body), signature)


def paid_date(value: str | None) -> str:
    if not value:
        return date.today().isoformat()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return date.today().isoformat()


def split_client_name(value: str | None) -> tuple[str, str]:
    cleaned = (value or "Клиент IQ Barakah").strip() or "Клиент IQ Barakah"
    parts = cleaned.split(maxsplit=1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def upsert_mizan_payment_in_business_os(payload: dict[str, Any]) -> dict[str, Any]:
    payment_id = str(payload.get("payment_id") or "").strip()
    if not payment_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="payment_id is required")
    amount = int(payload.get("amount") or 0)
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="amount must be positive")

    data = load_business_os()
    now = datetime.now(timezone.utc).isoformat()
    customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else {}
    tg_user_id = str(payload.get("telegram_user_id") or customer.get("telegram_user_id") or "").strip()
    product = str(payload.get("product_name") or payload.get("product") or payload.get("tariff_id") or "IQ Barakah").strip()
    tariff_id = str(payload.get("tariff_id") or "").strip()
    customer_name = str(
        payload.get("customer_name")
        or customer.get("name")
        or customer.get("telegram_username")
        or payload.get("telegram_username")
        or ""
    )
    first_name, last_name = split_client_name(customer_name)
    full_name = f"{first_name} {last_name}".strip()

    duplicate = any(str(item.get("mizan_payment_id") or item.get("payment_id") or "") == payment_id for item in data.get("cashflow", []))

    client = None
    for item in data.get("clients", []):
        existing_tg_id = str(item.get("telegram_user_id") or item.get("mizan_telegram_user_id") or "")
        if (tg_user_id and existing_tg_id == tg_user_id) or str(item.get("mizan_last_payment_id") or "") == payment_id:
            client = item
            break
    if not client:
        client = {
            "id": uuid.uuid4().hex,
            "first_name": first_name,
            "last_name": last_name,
            "company": "",
            "phone": "",
            "email": "",
            "messenger": "Telegram",
            "source": "Mizan OS / YooKassa",
            "segment": "Клиент",
            "status": "active",
            "manager": "Рашид",
            "next_contact_at": "",
            "total_amount": 0,
            "purchases_count": 0,
            "comments": f"Автоматически создан из оплаты Mizan OS: {product}",
            "tags": "mizan-os, paid",
            "telegram_user_id": tg_user_id,
            "telegram_username": str(payload.get("telegram_username") or customer.get("telegram_username") or "").strip(),
            "mizan_last_payment_id": payment_id,
            "created_at": now,
        }
        data.setdefault("clients", []).insert(0, client)

    if not duplicate:
        client["status"] = "active"
        client["segment"] = client.get("segment") or "Клиент"
        client["total_amount"] = int(client.get("total_amount") or 0) + amount
        client["purchases_count"] = int(client.get("purchases_count") or 0) + 1
        client["mizan_last_payment_id"] = payment_id
        client["updated_at"] = now

        data.setdefault("cashflow", []).insert(0, {
            "id": uuid.uuid4().hex,
            "date": paid_date(str(payload.get("paid_at") or "")),
            "type": "income",
            "amount": amount,
            "account": "YooKassa",
            "category": "Продажи",
            "subcategory": product,
            "counterparty": full_name,
            "project": "IQ Barakah",
            "branch": "Онлайн",
            "direction": "Обучение",
            "budget_item": "Выручка",
            "comment": f"Оплата из Mizan OS: {product}",
            "responsible": "Рашид",
            "approval_status": "approved",
            "author": "mizan-os",
            "mizan_payment_id": payment_id,
            "tariff_id": tariff_id,
            "telegram_user_id": tg_user_id,
            "created_at": now,
        })
        data.setdefault("deals", []).insert(0, {
            "id": uuid.uuid4().hex,
            "title": product,
            "client": full_name,
            "amount": amount,
            "cost": 0,
            "margin": amount,
            "manager": "Рашид",
            "stage": "Успешно закрыто",
            "probability": 100,
            "expected_close_at": paid_date(str(payload.get("paid_at") or "")),
            "next_step": "Передать клиента в сопровождение",
            "comments": f"Создано автоматически из Mizan OS, payment_id={payment_id}",
            "lost_reason": "",
            "mizan_payment_id": payment_id,
            "telegram_user_id": tg_user_id,
            "created_at": now,
        })
        data.setdefault("leads", []).insert(0, {
            "id": uuid.uuid4().hex,
            "client": full_name,
            "source": "Mizan OS / YooKassa",
            "campaign": product,
            "manager": "Рашид",
            "status": "paid",
            "priority": "high",
            "need": "Оплатил программу",
            "planned_amount": amount,
            "next_step": "Начать сопровождение клиента",
            "next_contact_at": "",
            "comments": f"payment_id={payment_id}",
            "lost_reason": "",
            "mizan_payment_id": payment_id,
            "telegram_user_id": tg_user_id,
            "created_at": now,
        })
        save_business_os(data)
        log_activity(None, action="принял", entity="оплату", title=f"{full_name} · {amount} ₽", href="/?view=crm", details=product)

    return {
        "duplicate": duplicate,
        "client_id": client.get("id"),
        "client": full_name,
        "payment_id": payment_id,
    }


def client_full_name(client: dict[str, Any]) -> str:
    return f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()


def business_client_relations(data: dict[str, list[dict[str, Any]]], client: dict[str, Any]) -> dict[str, Any]:
    name = client_full_name(client)
    normalized = name.lower()
    deals = [item for item in data.get("deals", []) if str(item.get("client", "")).lower() == normalized]
    leads = [item for item in data.get("leads", []) if str(item.get("client", "")).lower() == normalized]
    cashflow = [item for item in data.get("cashflow", []) if str(item.get("counterparty", "")).lower() == normalized]
    calendar = [item for item in data.get("calendar", []) if str(item.get("counterparty", "")).lower() == normalized]
    paid_total = sum(int(item.get("amount") or 0) for item in cashflow if item.get("type") == "income")
    planned_total = sum(int(item.get("amount") or 0) for item in calendar if item.get("status") != "paid")
    return {
        "name": name,
        "deals": deals,
        "leads": leads,
        "cashflow": cashflow,
        "calendar": calendar,
        "paid_total": paid_total,
        "planned_total": planned_total,
        "pipeline": sum(int(item.get("amount") or 0) for item in deals if item.get("stage") not in {"Успешно закрыто", "Отказ"}),
    }


def load_team_tasks() -> list[dict[str, Any]]:
    if not os.path.exists(CRM_TASKS_FILE):
        return []
    try:
        with open(CRM_TASKS_FILE, encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def save_team_tasks(tasks: list[dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(CRM_TASKS_FILE), exist_ok=True)
    with open(CRM_TASKS_FILE, "w", encoding="utf-8") as file:
        json.dump(tasks, file, ensure_ascii=False, indent=2)


def seed_team_tasks(students: list[StudentRow], payments: list[Any]) -> list[dict[str, Any]]:
    tasks = load_team_tasks()
    if tasks:
        return tasks
    seeded = []
    for item in curator_tasks(students, payments, limit=6):
        seeded.append(
            {
                "id": uuid.uuid4().hex,
                "title": item["title"],
                "student_id": item["student"].user.id,
                "student_name": item["student"].user.name,
                "assignee": "Куратор",
                "priority": item["priority"],
                "status": "todo",
                "due_date": "Сегодня" if item["priority"] == "high" else "На неделе",
                "notes": ", ".join(item["risk"]["reasons"]),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    save_team_tasks(seeded)
    return seeded


def create_team_task(
    *,
    title: str,
    assignee: str,
    priority: str,
    due_date: str,
    student_id: int | None,
    notes: str,
    students: list[StudentRow],
) -> None:
    student = next((item for item in students if student_id and item.user.id == student_id), None)
    tasks = load_team_tasks()
    assignees = {str(user.get("display_name")) for user in team_accounts()}
    assignees.update(TEAM_MEMBERS)
    tasks.insert(
        0,
        {
            "id": uuid.uuid4().hex,
            "title": title.strip(),
            "student_id": student_id,
            "student_name": student.user.name if student else "",
            "assignee": assignee if assignee in assignees else TEAM_MEMBERS[0],
            "priority": priority if priority in TASK_PRIORITIES else "normal",
            "status": "todo",
            "due_date": due_date.strip() or "Сегодня",
            "notes": notes.strip(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    save_team_tasks(tasks)


def update_team_task(task_id: str, *, status_value: str | None = None) -> None:
    tasks = load_team_tasks()
    for task in tasks:
        if task.get("id") == task_id and status_value in TASK_STATUSES:
            task["status"] = status_value
            task["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_team_tasks(tasks)


def get_team_task(task_id: str) -> dict[str, Any] | None:
    for task in load_team_tasks():
        if task.get("id") == task_id:
            return task
    return None


def update_team_task_fields(task_id: str, updates: dict[str, Any]) -> None:
    tasks = load_team_tasks()
    for task in tasks:
        if task.get("id") == task_id:
            task.update(updates)
            task["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_team_tasks(tasks)


def delete_team_task(task_id: str) -> None:
    tasks = [task for task in load_team_tasks() if task.get("id") != task_id]
    save_team_tasks(tasks)


def task_columns(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "status": status_key,
            "label": task_status_label(status_key),
            "tasks": [task for task in tasks if task.get("status") == status_key],
        }
        for status_key in TASK_STATUSES
    ]


def task_metrics(tasks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(tasks),
        "todo": len([task for task in tasks if task.get("status") == "todo"]),
        "doing": len([task for task in tasks if task.get("status") == "doing"]),
        "done": len([task for task in tasks if task.get("status") == "done"]),
        "high": len([task for task in tasks if task.get("priority") == "high" and task.get("status") != "done"]),
    }


def referral_url(code: str) -> str:
    base_url = os.environ.get("CRM_REFERRAL_BASE_URL", "https://iq-barakah.ru/index.html")
    query = urlencode({"ref": code, "utm_source": "referral", "utm_campaign": code})
    return f"{base_url}?{query}"


def student_referral_code(student: StudentRow) -> str | None:
    code = getattr(student.user, "referral_code", None) or getattr(student.user, "ref_code", None) or getattr(student.user, "ref", None)
    return str(code) if code else None


def referral_rows(users: list[dict[str, Any]], students: list[StudentRow], payments: list[Any]) -> list[dict[str, Any]]:
    payment_by_user: dict[int, int] = {}
    for payment in payments:
        if getattr(payment, "status", "") != "paid":
            continue
        payment_by_user[getattr(payment, "user_id", 0)] = payment_by_user.get(getattr(payment, "user_id", 0), 0) + int(getattr(payment, "amount", 0) or 0)

    rows = []
    for user in users:
        code = str(user.get("referral_code") or slugify_code(str(user.get("username", ""))))
        referred = [student for student in students if student_referral_code(student) == code]
        revenue = sum(payment_by_user.get(student.user.id, 0) for student in referred)
        rows.append(
            {
                "user": user,
                "code": code,
                "url": referral_url(code),
                "students": referred,
                "count": len(referred),
                "paid_count": len([student for student in referred if payment_by_user.get(student.user.id, 0) > 0]),
                "revenue": revenue,
            }
        )
    return sorted(rows, key=lambda item: (item["revenue"], item["count"]), reverse=True)


def referral_students(students: list[StudentRow], users: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    by_code = {str(user.get("referral_code")): user for user in users}
    rows = []
    for student in students:
        code = student_referral_code(student)
        if not code:
            continue
        owner = by_code.get(code)
        rows.append({"student": student, "code": code, "owner": owner})
    return rows[:limit]


def demo_students(
    *,
    q: str | None = None,
    level: str | None = None,
    gender: str | None = None,
    tariff: str | None = None,
    payment_status: str | None = None,
    activity: str | None = None,
    ref: str | None = None,
    week: int | None = None,
    limit: int | None = None,
) -> list[StudentRow]:
    students = [
        StudentRow(
            user=record(
                id=140700248,
                name="Амина Садыкова",
                username="amina_iqb",
                email="amina@example.com",
                phone="+7 999 111-22-33",
                is_female=True,
                age="29",
                occupation="entrepreneur",
                source="telegram",
                referral_code=None,
                created_at=datetime(2026, 5, 3, 10, 15, tzinfo=timezone.utc),
                updated_at=datetime(2026, 5, 23, 7, 40, tzinfo=timezone.utc),
            ),
            participant=record(
                level="А",
                week=3,
                vakt_level="Б",
                activated_at=datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
                graduated_at=None,
                is_active=True,
            ),
            last_diag=record(level_key="Б", pct=74, created_at=datetime(2026, 5, 22, 18, 10, tzinfo=timezone.utc)),
            last_activity=datetime(2026, 5, 23, 7, 40, tzinfo=timezone.utc),
        ),
        StudentRow(
            user=record(
                id=782441903,
                name="Мадина Хасанова",
                username="madina_time",
                email="madina@example.com",
                phone="+7 999 222-44-55",
                is_female=True,
                age="34",
                occupation="employee",
                source="social",
                referral_code=None,
                created_at=datetime(2026, 4, 28, 12, 20, tzinfo=timezone.utc),
                updated_at=datetime(2026, 5, 22, 20, 25, tzinfo=timezone.utc),
            ),
            participant=record(
                level="В",
                week=6,
                vakt_level="В",
                activated_at=datetime(2026, 4, 29, 8, 30, tzinfo=timezone.utc),
                graduated_at=None,
                is_active=True,
            ),
            last_diag=record(level_key="В", pct=88, created_at=datetime(2026, 5, 20, 16, 35, tzinfo=timezone.utc)),
            last_activity=datetime(2026, 5, 22, 20, 25, tzinfo=timezone.utc),
        ),
        StudentRow(
            user=record(
                id=516908331,
                name="Юсуф Магомедов",
                username="yusuf_track",
                email="yusuf@example.com",
                phone="+7 999 333-66-77",
                is_female=False,
                age="22",
                occupation="student",
                source="maps",
                referral_code=None,
                created_at=datetime(2026, 5, 1, 15, 5, tzinfo=timezone.utc),
                updated_at=datetime(2026, 5, 18, 12, 10, tzinfo=timezone.utc),
            ),
            participant=record(
                level="Б",
                week=2,
                vakt_level="А",
                activated_at=datetime(2026, 5, 2, 11, 10, tzinfo=timezone.utc),
                graduated_at=None,
                is_active=False,
            ),
            last_diag=record(level_key="А", pct=51, created_at=datetime(2026, 5, 17, 13, 45, tzinfo=timezone.utc)),
            last_activity=datetime(2026, 5, 18, 12, 10, tzinfo=timezone.utc),
        ),
        StudentRow(
            user=record(
                id=990184227,
                name="Лейла Абдуллаева",
                username="leyla_done",
                email="leyla@example.com",
                phone=None,
                is_female=True,
                age="31",
                occupation="freelance",
                source="internet",
                referral_code=None,
                created_at=datetime(2026, 4, 6, 14, 0, tzinfo=timezone.utc),
                updated_at=datetime(2026, 5, 19, 17, 20, tzinfo=timezone.utc),
            ),
            participant=record(
                level="Г",
                week=8,
                vakt_level="В",
                activated_at=datetime(2026, 4, 7, 10, 0, tzinfo=timezone.utc),
                graduated_at=datetime(2026, 5, 19, 17, 20, tzinfo=timezone.utc),
                is_active=False,
            ),
            last_diag=record(level_key="В", pct=93, created_at=datetime(2026, 5, 19, 16, 55, tzinfo=timezone.utc)),
            last_activity=datetime(2026, 5, 19, 17, 20, tzinfo=timezone.utc),
        ),
    ]

    first_names_f = [
        "Зайнаб",
        "Фатима",
        "Хадиджа",
        "Айша",
        "Мариям",
        "Райхана",
        "Самира",
        "Асия",
        "Динара",
        "Нура",
    ]
    first_names_m = [
        "Али",
        "Омар",
        "Юсуф",
        "Ибрагим",
        "Муса",
        "Халид",
        "Самир",
        "Амир",
        "Исмаил",
        "Тимур",
    ]
    last_names = [
        "Ахмадова",
        "Каримова",
        "Нуриева",
        "Саидова",
        "Хасанова",
        "Магомедов",
        "Абдуллаев",
        "Рахимов",
        "Садыков",
        "Юсупов",
    ]
    levels = ["А", "Б", "В", "Г"]
    occupations = ["entrepreneur", "employee", "student", "freelance", "manager"]
    sources = ["telegram", "social", "maps", "internet", "referral"]
    referral_codes = ["rashid", "kurator", "sales", "marketing"]

    for idx in range(5, 101):
        is_female = idx % 5 != 0
        name_pool = first_names_f if is_female else first_names_m
        first_name = name_pool[idx % len(name_pool)]
        last_name = last_names[(idx * 3) % len(last_names)]
        if is_female and not last_name.endswith("а"):
            last_name = f"{last_name}а"
        level_value = levels[idx % len(levels)]
        source_value = sources[idx % len(sources)]
        created_day = (idx % 24) + 1
        active = idx % 7 != 0
        graduated = idx % 13 == 0
        students.append(
            StudentRow(
                user=record(
                    id=770000000 + idx,
                    name=f"{first_name} {last_name}",
                    username=f"iqb_{idx:03d}",
                    email=f"student{idx:03d}@example.com",
                    phone=f"+7 999 {idx:03d}-{(idx * 7) % 100:02d}-{(idx * 11) % 100:02d}",
                    is_female=is_female,
                    age=str(18 + idx % 30),
                    occupation=occupations[idx % len(occupations)],
                    source=source_value,
                    referral_code=referral_codes[idx % len(referral_codes)] if source_value == "referral" else None,
                    created_at=datetime(2026, 5, created_day, 9 + idx % 8, 10, tzinfo=timezone.utc),
                    updated_at=datetime(2026, 5, min(created_day + 3, 28), 10 + idx % 9, 25, tzinfo=timezone.utc),
                ),
                participant=record(
                    level=level_value,
                    week=(idx % 8) + 1,
                    vakt_level=levels[(idx + 1) % 3],
                    activated_at=datetime(2026, 5, created_day, 10, 0, tzinfo=timezone.utc),
                    graduated_at=datetime(2026, 5, min(created_day + 7, 28), 18, 0, tzinfo=timezone.utc) if graduated else None,
                    is_active=active and not graduated,
                ),
                last_diag=record(
                    level_key=levels[(idx + 2) % 3],
                    pct=35 + (idx * 7) % 61,
                    created_at=datetime(2026, 5, min(created_day + 2, 28), 17, 30, tzinfo=timezone.utc),
                ),
                last_activity=datetime(2026, 5, min(created_day + 4, 28), 19, idx % 60, tzinfo=timezone.utc),
            )
        )

    if q:
        needle = q.strip().lower()
        students = [
            item
            for item in students
            if needle in str(item.user.id).lower()
            or needle in (item.user.name or "").lower()
            or needle in (item.user.username or "").lower()
            or needle in (item.user.email or "").lower()
            or needle in (item.user.phone or "").lower()
            or needle in (student_referral_code(item) or "").lower()
        ]
    if ref:
        students = [item for item in students if student_referral_code(item) == ref]
    if level:
        values = level_filter_values(level)
        students = [item for item in students if item.participant and item.participant.level in values]
    if gender == "female":
        students = [item for item in students if item.user.is_female is True]
    elif gender == "male":
        students = [item for item in students if item.user.is_female is False]
    elif gender == "unknown":
        students = [item for item in students if item.user.is_female is None]
    if tariff:
        students = [
            item
            for item in students
            if any(payment.tariff_id == tariff for payment in demo_payments(item.user.id))
        ]
    if payment_status:
        students = [
            item
            for item in students
            if any(payment.status == payment_status for payment in demo_payments(item.user.id))
        ]
    if week:
        students = [item for item in students if item.participant and item.participant.week == week]
    if activity:
        students = [item for item in students if item.status == activity]
    return students[:limit] if limit else students


def demo_payments(user_id: int | None = None) -> list[SimpleNamespace]:
    payments = [
        record(id=11, user_id=140700248, tariff_id="s1_full", amount=9900, status="paid", created_at=datetime(2026, 5, 5, 9, 4, tzinfo=timezone.utc), paid_at=datetime(2026, 5, 5, 9, 6, tzinfo=timezone.utc)),
        record(id=12, user_id=782441903, tariff_id="leader", amount=24900, status="paid", created_at=datetime(2026, 4, 29, 8, 42, tzinfo=timezone.utc), paid_at=datetime(2026, 4, 29, 8, 45, tzinfo=timezone.utc)),
        record(id=13, user_id=516908331, tariff_id="vakt", amount=3900, status="pending", created_at=datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc), paid_at=None),
    ]
    statuses = ["paid", "paid", "paid", "pending", "paid", "failed", "paid", "refunded"]
    tariffs = list(TARIFF_OPTIONS)
    for idx in range(5, 101):
        if idx % 11 == 0:
            continue
        tariff_id = tariffs[idx % len(tariffs)]
        status_value = statuses[idx % len(statuses)]
        created_day = (idx % 24) + 1
        payments.append(
            record(
                id=1000 + idx,
                user_id=770000000 + idx,
                tariff_id=tariff_id,
                amount=TARIFF_AMOUNTS[tariff_id],
                status=status_value,
                created_at=datetime(2026, 5, created_day, 12 + idx % 7, idx % 60, tzinfo=timezone.utc),
                paid_at=datetime(2026, 5, created_day, 13 + idx % 6, idx % 60, tzinfo=timezone.utc)
                if status_value == "paid"
                else None,
            )
        )
    return [item for item in payments if user_id is None or item.user_id == user_id]


def demo_barakah_metrics(user_id: int) -> BarakahMetrics:
    seed = user_id % 97
    tasks_total = 21
    return BarakahMetrics(
        tasks_done=5 + seed % 17,
        tasks_total=tasks_total,
        quran_pages=seed % 42,
        good_deeds=seed % 28,
        namaz_on_time=12 + seed % 24,
        azkar_days=seed % 8,
        muhasaba_days=(seed * 2) % 8,
        streak_days=seed % 10,
    )


def barakah_summary(students: list[StudentRow]) -> dict[str, int]:
    if not students:
        return {
            "avg_score": 0,
            "tasks_done": 0,
            "tasks_total": 0,
            "quran_pages": 0,
            "good_deeds": 0,
            "namaz_on_time": 0,
            "azkar_days": 0,
            "muhasaba_days": 0,
            "strong_students": 0,
            "risk_students": 0,
        }
    metrics = [demo_barakah_metrics(item.user.id) for item in students]
    return {
        "avg_score": round(sum(item.score for item in metrics) / len(metrics)),
        "tasks_done": sum(item.tasks_done for item in metrics),
        "tasks_total": sum(item.tasks_total for item in metrics),
        "quran_pages": sum(item.quran_pages for item in metrics),
        "good_deeds": sum(item.good_deeds for item in metrics),
        "namaz_on_time": sum(item.namaz_on_time for item in metrics),
        "azkar_days": sum(item.azkar_days for item in metrics),
        "muhasaba_days": sum(item.muhasaba_days for item in metrics),
        "strong_students": len([item for item in metrics if item.score >= 75]),
        "risk_students": len([item for item in metrics if item.score < 40]),
    }


def program_weeks(level: str | None) -> int:
    return {"I": 6, "II": 8, "III": 24}.get(level_label(level), 8)


def learning_snapshot(
    user: Any,
    participant: Any | None,
    diagnostics: list[Any],
    payments: list[Any],
    trackers: list[Any],
    muhasaba: list[Any],
    barakah: BarakahMetrics,
) -> dict[str, Any]:
    week = int(getattr(participant, "week", 0) or 0)
    weeks_total = program_weeks(getattr(participant, "level", None) if participant else None)
    paid_payments = [item for item in payments if getattr(item, "status", "") == "paid"]
    latest_payment = payments[0] if payments else None
    latest_diag = diagnostics[0] if diagnostics else None
    latest_tracker = trackers[0] if trackers else None
    latest_muhasaba = muhasaba[0] if muhasaba else None

    activity_candidates = [
        getattr(user, "updated_at", None),
        getattr(latest_diag, "created_at", None),
        getattr(latest_tracker, "updated_at", None),
        getattr(latest_muhasaba, "created_at", None),
    ]
    last_activity = max([item for item in activity_candidates if item], default=None)

    return {
        "level": level_label(getattr(participant, "level", None) if participant else None),
        "week": week,
        "weeks_total": weeks_total,
        "week_pct": progress_width(round(week / weeks_total * 100)) if weeks_total else 0,
        "tasks_pct": barakah.task_pct,
        "paid_total": sum(getattr(item, "amount", 0) for item in paid_payments),
        "paid_count": len(paid_payments),
        "latest_payment": latest_payment,
        "latest_diag": latest_diag,
        "latest_tracker": latest_tracker,
        "latest_muhasaba": latest_muhasaba,
        "last_activity": last_activity,
    }


def dashboard_learning_rows(students: list[StudentRow], limit: int = 10) -> list[dict[str, Any]]:
    rows = []
    for item in students:
        metrics = demo_barakah_metrics(item.user.id)
        week = int(getattr(item.participant, "week", 0) or 0)
        weeks_total = program_weeks(getattr(item.participant, "level", None) if item.participant else None)
        rows.append(
            {
                "student": item,
                "barakah": metrics,
                "week_pct": progress_width(round(week / weeks_total * 100)) if weeks_total else 0,
                "risk": metrics.score < 40 or item.status == "inactive",
            }
        )
    return sorted(rows, key=lambda row: (not row["risk"], row["barakah"].score))[:limit]


def user_payments(payments: list[Any], user_id: int) -> list[Any]:
    return [item for item in payments if getattr(item, "user_id", None) == user_id]


def student_stage(student: StudentRow, payments: list[Any]) -> str:
    paid = any(item.status == "paid" for item in user_payments(payments, student.user.id))
    pending = any(item.status == "pending" for item in user_payments(payments, student.user.id))
    if student.status == "graduated":
        return "Завершил"
    if student.participant and student.participant.is_active and paid:
        return "Учится"
    if student.participant and student.participant.is_active:
        return "Активирован"
    if paid:
        return "Оплатил"
    if pending:
        return "Ожидает оплату"
    if student.last_diag:
        return "Диагностика"
    return "Лид"


def risk_profile(student: StudentRow, payments: list[Any], metrics: BarakahMetrics | None = None) -> dict[str, Any]:
    metrics = metrics or demo_barakah_metrics(student.user.id)
    risk = 0
    reasons = []
    inactive_days = days_since(student.last_activity)
    if student.status == "inactive":
        risk += 28
        reasons.append("неактивен")
    if inactive_days is not None and inactive_days >= 5:
        risk += min(28, inactive_days * 3)
        reasons.append(f"нет активности {inactive_days} дн.")
    if metrics.score < 40:
        risk += 24
        reasons.append("низкий индекс")
    if metrics.task_pct < 45:
        risk += 16
        reasons.append("мало заданий")
    if any(item.status == "pending" for item in user_payments(payments, student.user.id)):
        risk += 12
        reasons.append("ожидает оплату")
    if student.status == "graduated":
        risk = max(0, risk - 45)
    risk = progress_width(risk)
    if risk >= 70:
        label = "Высокий"
        action = "Связаться сегодня и вернуть в ритм"
    elif risk >= 40:
        label = "Средний"
        action = "Написать мягкое напоминание"
    else:
        label = "Низкий"
        action = "Поддержать и похвалить прогресс"
    return {
        "score": risk,
        "label": label,
        "reasons": reasons or ["ритм держится"],
        "action": action,
        "inactive_days": inactive_days,
    }


def next_best_action(student: StudentRow, payments: list[Any], metrics: BarakahMetrics | None = None) -> str:
    risk = risk_profile(student, payments, metrics)
    paid = any(item.status == "paid" for item in user_payments(payments, student.user.id))
    pending = any(item.status == "pending" for item in user_payments(payments, student.user.id))
    if pending:
        return "Уточнить оплату и убрать трение"
    if risk["score"] >= 70:
        return "Личное сообщение: один короткий шаг до вечера"
    if student.status == "graduated":
        return "Предложить следующий уровень или Джамаат"
    if not paid and student.last_diag:
        return "Объяснить маршрут после диагностики"
    if metrics and metrics.score >= 75:
        return "Похвалить и закрепить сильный ритм"
    return "Проверить неделю и дать точечную поддержку"


def curator_tasks(students: list[StudentRow], payments: list[Any], limit: int = 12) -> list[dict[str, Any]]:
    tasks = []
    for student in students:
        metrics = demo_barakah_metrics(student.user.id)
        risk = risk_profile(student, payments, metrics)
        if risk["score"] >= 40 or student.status == "inactive" or any(item.status == "pending" for item in user_payments(payments, student.user.id)):
            tasks.append(
                {
                    "student": student,
                    "title": next_best_action(student, payments, metrics),
                    "risk": risk,
                    "priority": "high" if risk["score"] >= 70 else "normal",
                    "due": "Сегодня" if risk["score"] >= 70 else "На неделе",
                }
            )
    return sorted(tasks, key=lambda item: item["risk"]["score"], reverse=True)[:limit]


def lifecycle_funnel(students: list[StudentRow], payments: list[Any]) -> list[dict[str, Any]]:
    order = ["Лид", "Диагностика", "Ожидает оплату", "Оплатил", "Активирован", "Учится", "Завершил"]
    total = max(len(students), 1)
    rows = []
    for stage in order:
        stage_students = [item for item in students if student_stage(item, payments) == stage]
        ids = {item.user.id for item in stage_students}
        rows.append(
            {
                "stage": stage,
                "count": len(stage_students),
                "pct": round(len(stage_students) / total * 100),
                "amount": paid_total_for_users(payments, ids),
            }
        )
    return rows


def funnel_dropoffs(funnel: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for current, next_item in zip(funnel, funnel[1:]):
        current_count = current["count"]
        next_count = next_item["count"]
        lost = max(current_count - next_count, 0)
        rows.append(
            {
                "from": current["stage"],
                "to": next_item["stage"],
                "lost": lost,
                "drop_pct": round(lost / max(current_count, 1) * 100),
            }
        )
    return sorted(rows, key=lambda item: item["drop_pct"], reverse=True)


def payment_analytics(payments: list[Any], students: list[StudentRow]) -> dict[str, Any]:
    paid = [item for item in payments if item.status == "paid"]
    pending = [item for item in payments if item.status == "pending"]
    paid_total = sum(item.amount for item in paid)
    repeat_buyers = len({item.user_id for item in paid if len([p for p in paid if p.user_id == item.user_id]) > 1})
    buyers = len({item.user_id for item in paid})
    return {
        "paid_total": paid_total,
        "pending_total": sum(item.amount for item in pending),
        "avg_check": round(paid_total / len(paid)) if paid else 0,
        "buyers": buyers,
        "repeat_buyers": repeat_buyers,
        "conversion": round(buyers / max(len(students), 1) * 100),
    }


def source_label(value: str | None) -> str:
    return {
        "telegram": "Telegram",
        "social": "Соцсети",
        "maps": "Карты",
        "internet": "Сайт/поиск",
        "referral": "Рекомендации",
    }.get(value or "unknown", value or "Не указан")


def source_analytics(students: list[StudentRow], payments: list[Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[StudentRow]] = {}
    for student in students:
        grouped.setdefault(source_label(getattr(student.user, "source", None)), []).append(student)
    rows = []
    paid = [item for item in payments if item.status == "paid"]
    total_revenue = max(sum(item.amount for item in paid), 1)
    for label, items in grouped.items():
        ids = {item.user.id for item in items}
        buyers = len({item.user_id for item in paid if item.user_id in ids})
        paid_total = paid_total_for_users(payments, ids)
        active = len([item for item in items if item.status == "active"])
        graduated = len([item for item in items if item.status == "graduated"])
        rows.append(
            {
                "source": label,
                "students": len(items),
                "buyers": buyers,
                "conversion": round(buyers / max(len(items), 1) * 100),
                "active_pct": round(active / max(len(items), 1) * 100),
                "graduated_pct": round(graduated / max(len(items), 1) * 100),
                "revenue": paid_total,
                "revenue_pct": progress_width(round(paid_total / total_revenue * 100)),
                "avg_revenue": round(paid_total / max(len(items), 1)),
                "rating": round((buyers / max(len(items), 1) * 45) + (active / max(len(items), 1) * 25) + (paid_total / total_revenue * 30)),
            }
        )
    return sorted(rows, key=lambda item: (item["rating"], item["revenue"]), reverse=True)


def revenue_chart(payments: list[Any]) -> list[dict[str, Any]]:
    buckets: dict[str, int] = {}
    for payment in payments:
        if payment.status != "paid":
            continue
        created_at = getattr(payment, "created_at", None)
        label = created_at.strftime("%d.%m") if isinstance(created_at, datetime) else "Без даты"
        buckets[label] = buckets.get(label, 0) + getattr(payment, "amount", 0)
    max_value = max(buckets.values(), default=1)
    return [
        {"label": label, "value": value, "pct": progress_width(round(value / max_value * 100))}
        for label, value in sorted(buckets.items())[-14:]
    ]


def revenue_line_chart(payments: list[Any]) -> dict[str, Any]:
    rows = revenue_chart(payments)
    width = 640
    height = 220
    pad_x = 24
    pad_y = 18
    max_value = max([item["value"] for item in rows], default=1)
    usable_w = width - pad_x * 2
    usable_h = height - pad_y * 2
    points = []
    for index, item in enumerate(rows):
        x = pad_x + (usable_w * index / max(len(rows) - 1, 1))
        y = pad_y + usable_h - (usable_h * item["value"] / max_value)
        points.append((round(x, 1), round(y, 1)))
    points_text = " ".join(f"{x},{y}" for x, y in points)
    area_text = f"{pad_x},{height - pad_y} {points_text} {width - pad_x},{height - pad_y}" if points else ""
    return {
        "rows": rows,
        "points": points_text,
        "area": area_text,
        "total": sum(item["value"] for item in rows),
        "max": max_value,
        "first_label": rows[0]["label"] if rows else "-",
        "last_label": rows[-1]["label"] if rows else "-",
    }


def donut_segments(items: list[dict[str, Any]], value_key: str) -> list[dict[str, Any]]:
    total = max(sum(int(item.get(value_key, 0)) for item in items), 1)
    offset = 0
    rows = []
    colors = ["#1a3d08", "#c9a84c", "#2a5c10", "#7a8e6a", "#e8c97a"]
    for index, item in enumerate(items[:5]):
        value = int(item.get(value_key, 0))
        pct = round(value / total * 100)
        rows.append(
            {
                "label": item.get("source") or item.get("stage") or "-",
                "value": value,
                "pct": pct,
                "offset": offset,
                "color": colors[index % len(colors)],
            }
        )
        offset += pct
    return rows


def bi_dashboard(students: list[StudentRow], payments: list[Any], sources: list[dict[str, Any]], funnel: list[dict[str, Any]]) -> dict[str, Any]:
    paid = [item for item in payments if item.status == "paid"]
    paid_total = sum(item.amount for item in paid)
    buyers = len({item.user_id for item in paid})
    return {
        "source_donut": donut_segments(sources, "students"),
        "revenue_donut": donut_segments(sources, "revenue"),
        "funnel_donut": donut_segments(funnel, "count"),
        "avg_revenue": round(paid_total / max(len(students), 1)),
        "buyer_pct": round(buyers / max(len(students), 1) * 100),
        "active_pct": round(len([item for item in students if item.status == "active"]) / max(len(students), 1) * 100),
    }


def dashboard_recommendations(sources: list[dict[str, Any]], dropoffs: list[dict[str, Any]]) -> dict[str, Any]:
    best = sources[0] if sources else None
    weakest = dropoffs[0] if dropoffs else None
    return {
        "best_source": best,
        "weakest_dropoff": weakest,
        "marketing_action": f"Усилить {best['source']}: лучший рейтинг {best['rating']}/100" if best else "Недостаточно данных по каналам",
        "funnel_action": f"Чинить переход {weakest['from']} → {weakest['to']}" if weakest else "Воронка стабильна",
    }


def finance_control(payments: list[Any]) -> dict[str, Any]:
    paid = [item for item in payments if getattr(item, "status", "") == "paid"]
    pending = [item for item in payments if getattr(item, "status", "") == "pending"]
    paid_total = sum(int(getattr(item, "amount", 0) or 0) for item in paid)
    pending_total = sum(int(getattr(item, "amount", 0) or 0) for item in pending)
    charity_reserve = sum(TARIFF_CHARITY.get(getattr(item, "tariff_id", ""), 0) for item in paid)
    tax_reserve = round(paid_total * 0.06)
    operating_budget = round(paid_total * 0.28)
    gross_profit = round(paid_total * 0.72)
    obligations = tax_reserve + charity_reserve + operating_budget
    net_profit = max(gross_profit - tax_reserve - charity_reserve, 0)
    available_cash = max(paid_total - obligations, 0)
    return {
        "paid_total": paid_total,
        "pending_total": pending_total,
        "gross_profit": gross_profit,
        "operating_budget": operating_budget,
        "tax_reserve": tax_reserve,
        "charity_reserve": charity_reserve,
        "obligations": obligations,
        "net_profit": net_profit,
        "available_cash": available_cash,
        "cash_gap_risk": obligations > paid_total * 0.62,
        "collection_focus": pending_total,
    }


def task_discipline(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    done = [task for task in tasks if task.get("status") == "done"]
    open_tasks = [task for task in tasks if task.get("status") != "done"]
    critical = [task for task in open_tasks if task.get("priority") == "high"]
    today_due = [task for task in open_tasks if str(task.get("due_date", "")).lower() in {"сегодня", "today"}]
    return {
        "total": len(tasks),
        "open": len(open_tasks),
        "done": len(done),
        "critical": len(critical),
        "today_due": len(today_due),
        "completion_rate": round(len(done) / max(len(tasks), 1) * 100),
    }


def owner_alerts(
    students: list[StudentRow],
    payments: list[Any],
    tasks: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    dropoffs: list[dict[str, Any]],
    finance: dict[str, Any],
) -> list[dict[str, str]]:
    alerts = []
    if finance["pending_total"]:
        alerts.append({"level": "money", "title": "Деньги зависли", "text": f"Ожидает оплаты: {money(finance['pending_total'])}. Нужен контакт продаж."})
    if finance["cash_gap_risk"]:
        alerts.append({"level": "money", "title": "Риск кассового разрыва", "text": "Резервы и обязательства слишком близко к кассе."})
    discipline = task_discipline(tasks)
    if discipline["critical"]:
        alerts.append({"level": "tasks", "title": "Критические задачи", "text": f"{discipline['critical']} срочных задач не закрыто."})
    risk_students = len([student for student in students if risk_profile(student, payments)["score"] >= 70])
    if risk_students:
        alerts.append({"level": "clients", "title": "Риск потери учеников", "text": f"{risk_students} учеников требуют личного касания."})
    if dropoffs:
        alerts.append({"level": "sales", "title": "Провал воронки", "text": f"{dropoffs[0]['from']} → {dropoffs[0]['to']}: теряется {dropoffs[0]['drop_pct']}%."})
    if sources:
        alerts.append({"level": "growth", "title": "Куда лить маркетинг", "text": f"Лучший канал: {sources[0]['source']} с рейтингом {sources[0]['rating']}/100."})
    return alerts[:6]


def owner_actions(alerts: list[dict[str, str]], tasks: list[dict[str, Any]]) -> list[str]:
    actions = [alert["text"] for alert in alerts[:3]]
    if not actions:
        actions.append("Проверить финансы, задачи и учеников без срочных отклонений.")
    if any(task.get("status") != "done" for task in tasks):
        actions.append("Закрыть или переназначить открытые задачи команды.")
    actions.append("Проверить план оплат и следующий контакт по тёплым лидам.")
    return actions[:4]


def employee_kpis(accounts: list[dict[str, Any]], tasks: list[dict[str, Any]], referrals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    referrals_by_name = {item["user"].get("display_name"): item for item in referrals}
    rows = []
    for account in accounts:
        name = str(account.get("display_name", ""))
        user_tasks = [task for task in tasks if task.get("assignee") == name]
        done = len([task for task in user_tasks if task.get("status") == "done"])
        open_count = len([task for task in user_tasks if task.get("status") != "done"])
        referral = referrals_by_name.get(name, {})
        rows.append(
            {
                "name": name,
                "role": account.get("role", ""),
                "tasks": len(user_tasks),
                "done": done,
                "open": open_count,
                "completion": round(done / max(len(user_tasks), 1) * 100),
                "referrals": referral.get("count", 0),
                "revenue": referral.get("revenue", 0),
            }
        )
    return rows


def ai_owner_briefing(finance: dict[str, Any], discipline: dict[str, Any], alerts: list[dict[str, str]], sources: list[dict[str, Any]]) -> dict[str, Any]:
    best_source = sources[0]["source"] if sources else "нет данных"
    return {
        "title": "Доброе утро. Главное по бизнесу",
        "items": [
            f"Касса: {money(finance['paid_total'])}, доступно после резервов: {money(finance['available_cash'])}.",
            f"Чистая управленческая прибыль: {money(finance['net_profit'])}.",
            f"Ожидает оплаты: {money(finance['pending_total'])}.",
            f"Задачи: {discipline['open']} открыто, {discipline['critical']} критичных.",
            f"Лучший канал роста: {best_source}.",
        ],
        "risk": alerts[0]["title"] if alerts else "Критических отклонений нет",
    }


def business_os_summary(data: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    deals = data.get("deals", [])
    cashflow = data.get("cashflow", [])
    calendar = data.get("calendar", [])
    income = sum(int(item.get("amount", 0) or 0) for item in cashflow if item.get("type") == "income")
    expense = sum(int(item.get("amount", 0) or 0) for item in cashflow if item.get("type") == "expense")
    open_deals = [item for item in deals if item.get("stage") not in {"Успешно закрыто", "Отказ"}]
    planned_payments = [item for item in calendar if item.get("status") != "paid"]
    return {
        "clients": len(data.get("clients", [])),
        "leads": len(data.get("leads", [])),
        "deals": len(deals),
        "open_deals": len(open_deals),
        "pipeline": sum(int(item.get("amount", 0) or 0) for item in open_deals),
        "cash_in": income,
        "cash_out": expense,
        "cash_balance": income - expense,
        "planned_payments": sum(int(item.get("amount", 0) or 0) for item in planned_payments),
        "projects": len(data.get("projects", [])),
        "knowledge": len(data.get("knowledge", [])),
    }


def deal_columns(deals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stages = ["Новый лид", "Связаться", "Контакт установлен", "Выявлена потребность", "Предложение", "Переговоры", "Ожидается решение", "Оплата", "Успешно закрыто", "Отказ"]
    return [
        {
            "stage": stage,
            "deals": [deal for deal in deals if deal.get("stage") == stage],
            "amount": sum(int(deal.get("amount", 0) or 0) for deal in deals if deal.get("stage") == stage),
        }
        for stage in stages
    ]


def operating_blueprint() -> dict[str, Any]:
    return {
        "tables": [
            {"name": "clients", "purpose": "единая карточка клиента/ученика", "owner": "Куратор", "priority": "MVP"},
            {"name": "deals", "purpose": "воронка, сумма, этап, следующий контакт", "owner": "Продажи", "priority": "MVP"},
            {"name": "payments", "purpose": "оплаты, тариф, статус, ЮKassa webhook", "owner": "Финансы", "priority": "MVP"},
            {"name": "cashflow", "purpose": "ДДС, категории, план-факт", "owner": "CFO", "priority": "Этап 2"},
            {"name": "tasks", "purpose": "ответственные, сроки, приёмка результата", "owner": "COO", "priority": "MVP"},
            {"name": "kpi", "purpose": "показатели сотрудников и дисциплина", "owner": "Собственник", "priority": "Этап 2"},
        ],
        "automations": [
            {"process": "Новая оплата", "trigger": "ЮKassa paid", "action": "активировать ученика и поставить задачу куратору"},
            {"process": "Нет активности", "trigger": "5 дней без трекера", "action": "создать задачу куратору"},
            {"process": "Ожидает оплату", "trigger": "pending больше 24 часов", "action": "уведомить продажи"},
            {"process": "Утренний отчёт", "trigger": "каждый день 09:00", "action": "AI-сводка собственнику в Telegram"},
        ],
        "roadmap": [
            {"stage": "7 дней", "text": "закрепить лиды, оплаты, задачи, доступы и реферальные ссылки"},
            {"stage": "30 дней", "text": "добавить ДДС, план-факт, платёжный календарь и Telegram-уведомления"},
            {"stage": "60 дней", "text": "подключить Mini App, KPI сотрудников, базу знаний и отчёты"},
            {"stage": "90 дней", "text": "AI-ассистент, прогноз кассового разрыва, API и BI-интеграции"},
        ],
        "kanban": [
            {"column": "Backlog", "items": ["ДДС", "База знаний", "Платёжный календарь"]},
            {"column": "Sprint", "items": ["Кабинет собственника", "KPI команды", "Красные зоны"]},
            {"column": "Done", "items": ["Сегменты", "Рефералки", "Задачи команды"]},
        ],
    }


def integration_status() -> list[dict[str, str]]:
    return [
        {"name": "ЮKassa", "status": "Готовить", "next": "создать checkout/session и webhook оплат"},
        {"name": "Telegram бот", "status": "Готовить", "next": "читать тарифы, оплаты, risk score из CRM API"},
        {"name": "Mini App", "status": "Готовить", "next": "показать прогресс, оплату, задания и неделю"},
        {"name": "Сайт", "status": "Готовить", "next": "передавать source/utm и открывать нужный тариф"},
        {"name": "BI/API", "status": "В CRM", "next": "/api/dashboard.json уже отдаёт агрегаты"},
    ]


def integration_payload(
    stats: dict[str, int],
    funnel: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    payments: list[Any],
    students: list[StudentRow],
    tasks: list[dict[str, Any]] | None = None,
    users: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payment_data = payment_analytics(payments, students)
    dropoffs = funnel_dropoffs(funnel)
    recommendations = dashboard_recommendations(sources, dropoffs)
    team_tasks = tasks or []
    accounts = users or team_accounts()
    finance = finance_control(payments)
    discipline = task_discipline(team_tasks)
    alerts = owner_alerts(students, payments, team_tasks, sources, dropoffs, finance)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "payments": payment_data,
        "owner": {
            "finance": finance,
            "discipline": discipline,
            "alerts": alerts,
            "actions": owner_actions(alerts, team_tasks),
            "ai_briefing": ai_owner_briefing(finance, discipline, alerts, sources),
        },
        "funnel": funnel,
        "dropoffs": dropoffs,
        "sources": sources,
        "recommendations": recommendations,
        "tariffs": tariff_catalog(),
        "team": {
            "metrics": task_metrics(team_tasks),
            "columns": task_columns(team_tasks),
        },
        "referrals": [
            {
                "code": item["code"],
                "owner": item["user"].get("display_name"),
                "role": item["user"].get("role"),
                "url": item["url"],
                "count": item["count"],
                "paid_count": item["paid_count"],
                "revenue": item["revenue"],
            }
            for item in referral_rows(accounts, students, payments)
        ],
        "integration_status": integration_status(),
    }


def cohort_analytics(students: list[StudentRow], payments: list[Any]) -> list[dict[str, Any]]:
    cohorts: dict[str, list[StudentRow]] = {}
    for student in students:
        created_at = getattr(student.user, "created_at", None)
        label = created_at.strftime("%m.%Y") if isinstance(created_at, datetime) else "Без даты"
        cohorts.setdefault(label, []).append(student)
    rows = []
    for label, cohort_students in sorted(cohorts.items(), reverse=True):
        ids = {item.user.id for item in cohort_students}
        active = len([item for item in cohort_students if item.status == "active"])
        graduated = len([item for item in cohort_students if item.status == "graduated"])
        rows.append(
            {
                "label": label,
                "count": len(cohort_students),
                "active_pct": round(active / max(len(cohort_students), 1) * 100),
                "graduated_pct": round(graduated / max(len(cohort_students), 1) * 100),
                "amount": paid_total_for_users(payments, ids),
            }
        )
    return rows[:6]


def week_map(participant: Any | None, metrics: BarakahMetrics) -> list[dict[str, Any]]:
    titles = ["Намерение", "Фаджр", "Ритм", "Внимание", "Мухасаба", "Истиqама"]
    current_week = int(getattr(participant, "week", 0) or 0)
    weeks_total = min(program_weeks(getattr(participant, "level", None) if participant else None), 8)
    rows = []
    for week in range(1, weeks_total + 1):
        pct = progress_width(round((metrics.task_pct + min(metrics.score + week * 4, 100)) / 2))
        rows.append(
            {
                "week": week,
                "title": titles[(week - 1) % len(titles)],
                "status": "done" if week < current_week else "current" if week == current_week else "next",
                "pct": 100 if week < current_week else pct if week == current_week else 0,
            }
        )
    return rows


def student_timeline(
    user: Any,
    participant: Any | None,
    diagnostics: list[Any],
    payments: list[Any],
    week_acks: list[Any],
    trackers: list[Any],
    muhasaba: list[Any],
) -> list[dict[str, Any]]:
    events = [
        {"at": getattr(user, "created_at", None), "title": "Регистрация", "text": getattr(user, "source", None) or "Источник не указан"},
        {"at": getattr(participant, "activated_at", None) if participant else None, "title": "Активация", "text": f"Уровень {level_label(getattr(participant, 'level', None))}" if participant else "-"},
    ]
    events += [{"at": item.created_at, "title": "Диагностика", "text": f"{level_label(item.level_key)} · {item.pct}%"} for item in diagnostics[:3]]
    events += [{"at": item.created_at, "title": "Оплата", "text": f"{tariff_name(item.tariff_id)} · {money(item.amount)} · {payment_status_label(item.status)}"} for item in payments[:3]]
    events += [{"at": item.acked_at, "title": "Неделя", "text": f"{level_label(item.level)} · неделя {item.week}"} for item in week_acks[:3]]
    events += [{"at": getattr(item, "updated_at", None), "title": "Трекер", "text": "обновил привычки"} for item in trackers[:2]]
    events += [{"at": item.created_at, "title": "Мухасаба", "text": "вечерний отчёт"} for item in muhasaba[:2]]
    return sorted([item for item in events if item["at"]], key=lambda item: item["at"], reverse=True)[:10]


def message_templates(risk: dict[str, Any]) -> list[dict[str, str]]:
    if risk["score"] >= 70:
        return [
            {"title": "Вернуть мягко", "text": "Ассаляму алейку. Не нужно догонять всё. Давай сегодня только один короткий шаг: отметь намаз и сделай 3 строки мухасабы."},
            {"title": "Без давления", "text": "Ты не выпал из пути. Путь продолжается с ближайшего намаза и одного честного действия."},
        ]
    return [
        {"title": "Похвала", "text": "МашаАллах, вижу движение. Закрепи сегодня ритм: Фаджр-лист, один блок без телефона и вечерняя мухасаба."},
        {"title": "Следующая неделя", "text": "Посмотри, что было самым лёгким на этой неделе, и усили именно это. Баракат растёт через постоянство."},
    ]


def demo_stats(students: list[StudentRow], payments: list[SimpleNamespace]) -> dict[str, int]:
    paid_total = sum(item.amount for item in payments if item.status == "paid")
    return {
        "total_users": len(demo_students()),
        "active_students": len([item for item in demo_students() if item.status == "active"]),
        "graduated_students": len([item for item in demo_students() if item.status == "graduated"]),
        "paid_payments": len([item for item in payments if item.status == "paid"]),
        "paid_total": paid_total,
    }


def segment_item(label: str, value: int, href: str, sub: str | None = None) -> dict[str, Any]:
    return {"label": label, "value": value, "href": href, "sub": sub}


def paid_total_for_users(payments: list[Any], user_ids: set[int]) -> int:
    return sum(item.amount for item in payments if item.status == "paid" and item.user_id in user_ids)


def student_segments(students: list[StudentRow]) -> dict[str, int]:
    return {
        "level_i": len([item for item in students if item.participant and level_label(item.participant.level) == "I"]),
        "level_ii": len([item for item in students if item.participant and level_label(item.participant.level) == "II"]),
        "level_iii": len([item for item in students if item.participant and level_label(item.participant.level) == "III"]),
        "active": len([item for item in students if item.status == "active"]),
        "graduated": len([item for item in students if item.status == "graduated"]),
        "needs_attention": len([item for item in students if item.status == "inactive"]),
    }


def level_segments(students: list[StudentRow], payments: list[Any]) -> list[dict[str, Any]]:
    return [
        segment_item(
            "Уровень I",
            len([item for item in students if item.participant and level_label(item.participant.level) == "I"]),
            "/students?level=I",
            money(paid_total_for_users(payments, {item.user.id for item in students if item.participant and level_label(item.participant.level) == "I"})),
        ),
        segment_item(
            "Уровень II",
            len([item for item in students if item.participant and level_label(item.participant.level) == "II"]),
            "/students?level=II",
            money(paid_total_for_users(payments, {item.user.id for item in students if item.participant and level_label(item.participant.level) == "II"})),
        ),
        segment_item(
            "Уровень III",
            len([item for item in students if item.participant and level_label(item.participant.level) == "III"]),
            "/students?level=III",
            money(paid_total_for_users(payments, {item.user.id for item in students if item.participant and level_label(item.participant.level) == "III"})),
        ),
    ]


def gender_segments(students: list[StudentRow], payments: list[Any] | None = None) -> list[dict[str, Any]]:
    payments = payments or []
    female_ids = {item.user.id for item in students if item.user.is_female is True}
    male_ids = {item.user.id for item in students if item.user.is_female is False}
    unknown_ids = {item.user.id for item in students if item.user.is_female is None}
    return [
        segment_item("Женщины", len(female_ids), "/students?gender=female", money(paid_total_for_users(payments, female_ids))),
        segment_item("Мужчины", len(male_ids), "/students?gender=male", money(paid_total_for_users(payments, male_ids))),
        segment_item("Не указан", len(unknown_ids), "/students?gender=unknown", money(paid_total_for_users(payments, unknown_ids))),
    ]


def payment_segments(payments: list[Any]) -> list[dict[str, Any]]:
    statuses = ("paid", "pending", "failed", "refunded")
    return [
        segment_item(
            payment_status_label(status_key),
            len([item for item in payments if item.status == status_key]),
            f"/students?payment_status={status_key}",
            money(sum(item.amount for item in payments if item.status == status_key and item.status == "paid")),
        )
        for status_key in statuses
    ]


def program_segments(payments: list[Any]) -> list[dict[str, Any]]:
    return [
        segment_item(
            tariff_name(tariff_id),
            len([item for item in payments if item.tariff_id == tariff_id]),
            f"/students?tariff={tariff_id}",
            money(sum(item.amount for item in payments if item.tariff_id == tariff_id and item.status == "paid")),
        )
        for tariff_id in TARIFF_OPTIONS
    ]


def export_query(filters: dict[str, Any]) -> str:
    clean = {key: value for key, value in filters.items() if value not in ("", None)}
    return urlencode(clean)


def demo_student_detail(user_id: int) -> dict[str, Any] | None:
    student = next((item for item in demo_students() if item.user.id == user_id), None)
    if not student:
        return None

    return {
        "user": student.user,
        "participant": student.participant,
        "diagnostics": [
            record(created_at=student.last_diag.created_at, level_key=student.last_diag.level_key, pct=student.last_diag.pct, scores=[2, 3, 2, 1, 3, 2, 2, 3]),
            record(created_at=datetime(2026, 5, 8, 15, 20, tzinfo=timezone.utc), level_key="А", pct=58, scores=[1, 2, 2, 1, 2, 1, 2, 1]),
        ],
        "payments": demo_payments(user_id),
        "week_acks": [
            record(acked_at=datetime(2026, 5, 9, 19, 30, tzinfo=timezone.utc), level=student.participant.level, week=1),
            record(acked_at=datetime(2026, 5, 16, 20, 10, tzinfo=timezone.utc), level=student.participant.level, week=2),
        ],
        "trackers": [
            record(date=date(2026, 5, 23), updated_at=datetime(2026, 5, 23, 7, 40, tzinfo=timezone.utc), habits={"namaz": {"fajr": True, "isha": True}, "daily": {"azkar": True, "reading": True}}),
            record(date=date(2026, 5, 22), updated_at=datetime(2026, 5, 22, 21, 5, tzinfo=timezone.utc), habits={"namaz": {"fajr": True, "isha": False}, "daily": {"azkar": True}}),
        ],
        "wheels": [
            record(created_at=datetime(2026, 5, 22, 18, 25, tzinfo=timezone.utc), scores={"iman": 8, "time": 6, "habits": 7, "family": 8, "health": 6, "finance": 5, "mission": 7, "social": 6}),
        ],
        "muhasaba": [
            record(created_at=datetime(2026, 5, 22, 21, 30, tzinfo=timezone.utc), answers=[{"q": "Что получилось?", "a": "Утренний блок и планирование"}, {"q": "Что улучшить?", "a": "Не откладывать трекер"}]),
        ],
        "barakah": demo_barakah_metrics(user_id),
    }


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> Response:
    if current_crm_user(request):
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(default="admin"), password: str = Form(...)) -> Response:
    user = authenticate_crm_user(username, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Неверный пароль."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        SESSION_COOKIE,
        user_session_token(str(user["username"]), str(user["password_hash"])),
        httponly=True,
        samesite="lax",
        secure=os.environ.get("CRM_COOKIE_SECURE", "0") == "1",
    )
    return response


@app.post("/logout")
async def logout() -> Response:
    response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    view: str = Query(default="overview"),
    theme: str = Query(default="premium"),
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    crm_user = current_crm_user(request)
    demo = False
    try:
        stats = await load_dashboard_stats(db)
        recent_students = await load_students(db, limit=8)
        all_students = await load_students(db)
        recent_payments = list(await db.scalars(select(Payment).order_by(desc(Payment.created_at)).limit(8)))
        all_payments = list(await db.scalars(select(Payment)))
    except (OSError, SQLAlchemyError):
        demo = True
        recent_students = demo_students(limit=8)
        all_students = demo_students()
        recent_payments = demo_payments()[:12]
        all_payments = demo_payments()
        stats = demo_stats(all_students, all_payments)
    segments = student_segments(all_students)
    views = {"owner", "business", "crm", "finance_os", "projects", "knowledge", "overview", "bi", "team", "integrations", "learning", "success", "marketing", "segments", "payments", "cohorts", "students"}
    current_view = view if view in views else "overview"
    barakah = barakah_summary(all_students)
    funnel = lifecycle_funnel(all_students, all_payments)
    sources = source_analytics(all_students, all_payments)
    dropoffs = funnel_dropoffs(funnel)
    tasks = seed_team_tasks(all_students, all_payments)
    accounts = team_accounts()
    referrals = referral_rows(accounts, all_students, all_payments)
    finance = finance_control(all_payments)
    discipline = task_discipline(tasks)
    alerts = owner_alerts(all_students, all_payments, tasks, sources, dropoffs, finance)
    blueprint = operating_blueprint()
    business_os = load_business_os()
    current_theme = design_theme(theme)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "current_user": crm_user,
            "view": current_view,
            "theme": current_theme,
            "design_themes": DESIGN_THEMES,
            "stats": stats,
            "segments": segments,
            "level_segments": level_segments(all_students, all_payments),
            "gender_segments": gender_segments(all_students, all_payments),
            "payment_segments": payment_segments(all_payments),
            "program_segments": program_segments(all_payments),
            "barakah": barakah,
            "learning_rows": dashboard_learning_rows(all_students),
            "funnel": funnel,
            "funnel_dropoffs": dropoffs,
            "risk_rows": [
                {
                    "student": row["student"],
                    "risk": risk_profile(row["student"], all_payments, row["barakah"]),
                    "action": next_best_action(row["student"], all_payments, row["barakah"]),
                }
                for row in dashboard_learning_rows(all_students, limit=12)
            ],
            "curator_tasks": curator_tasks(all_students, all_payments),
            "payment_analytics": payment_analytics(all_payments, all_students),
            "cohorts": cohort_analytics(all_students, all_payments),
            "sources": sources,
            "revenue_chart": revenue_chart(all_payments),
            "revenue_line": revenue_line_chart(all_payments),
            "bi": bi_dashboard(all_students, all_payments, sources, funnel),
            "dashboard_recommendations": dashboard_recommendations(sources, dropoffs),
            "integration_status": integration_status(),
            "task_columns": task_columns(tasks),
            "task_metrics": task_metrics(tasks),
            "team_members": tuple(dict.fromkeys((*TEAM_MEMBERS, *(str(user.get("display_name")) for user in accounts)))),
            "task_priorities": TASK_PRIORITIES,
            "crm_users": accounts,
            "crm_roles": CRM_ROLES,
            "crm_role_access": CRM_ROLE_ACCESS,
            "referrals": referrals,
            "referral_students": referral_students(all_students, accounts),
            "finance_control": finance,
            "task_discipline": discipline,
            "owner_alerts": alerts,
            "owner_actions": owner_actions(alerts, tasks),
            "employee_kpis": employee_kpis(accounts, tasks, referrals),
            "ai_briefing": ai_owner_briefing(finance, discipline, alerts, sources),
            "operating_blueprint": blueprint,
            "business_os": business_os,
            "business_summary": business_os_summary(business_os),
            "deal_columns": deal_columns(business_os.get("deals", [])),
            "activity_log": load_activity_log()[:12],
            "tariff_catalog": tariff_catalog(),
            "students": recent_students,
            "payments": recent_payments,
            "demo": demo,
        },
    )


@app.post("/api/mizan/payment-confirmed")
async def receive_mizan_payment_confirmed(request: Request) -> dict[str, Any]:
    secret = os.environ.get("CRM_MIZAN_WEBHOOK_SECRET") or os.environ.get("MIZAN_PAYMENT_WEBHOOK_SECRET") or ""
    if not secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="CRM Mizan webhook secret is not configured")
    raw_body = await request.body()
    signature = request.headers.get("X-Mizan-Signature", "")
    if not verify_mizan_signature(secret, raw_body, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON") from exc
    result = upsert_mizan_payment_in_business_os(payload)
    return {"ok": True, **result}


@app.get("/api/dashboard.json")
async def dashboard_api(
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    try:
        all_students = await load_students(db)
        all_payments = list(await db.scalars(select(Payment)))
        stats = await load_dashboard_stats(db)
    except (OSError, SQLAlchemyError):
        all_students = demo_students()
        all_payments = demo_payments()
        stats = demo_stats(all_students, all_payments)

    funnel = lifecycle_funnel(all_students, all_payments)
    sources = source_analytics(all_students, all_payments)
    tasks = seed_team_tasks(all_students, all_payments)
    return integration_payload(stats, funnel, sources, all_payments, all_students, tasks, team_accounts())


@app.post("/tasks")
async def create_task(
    request: Request,
    title: str = Form(...),
    assignee: str = Form(default="Куратор"),
    priority: str = Form(default="normal"),
    due_date: str = Form(default="Сегодня"),
    student_id: str = Form(default=""),
    notes: str = Form(default=""),
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if not title.strip():
        return RedirectResponse("/?view=team", status_code=status.HTTP_303_SEE_OTHER)
    try:
        students = await load_students(db)
    except (OSError, SQLAlchemyError):
        students = demo_students()
    linked_student_id = int(student_id) if student_id.strip().isdigit() else None
    create_team_task(
        title=title,
        assignee=assignee,
        priority=priority,
        due_date=due_date,
        student_id=linked_student_id,
        notes=notes,
        students=students,
    )
    log_activity(request, action="создал", entity="задача", title=title.strip(), href="/?view=team", details=f"Ответственный: {assignee}, срок: {due_date}")
    return RedirectResponse("/?view=team", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail(
    request: Request,
    task_id: str,
    _: None = Depends(require_admin),
) -> Response:
    task = get_team_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
    return templates.TemplateResponse(
        "task_detail.html",
        {
            "request": request,
            "task": task,
            "team_members": TEAM_MEMBERS,
            "task_statuses": TASK_STATUSES,
            "task_priorities": TASK_PRIORITIES,
        },
    )


@app.post("/tasks/{task_id}")
async def update_task(
    request: Request,
    task_id: str,
    title: str = Form(...),
    assignee: str = Form(default="Куратор"),
    priority: str = Form(default="normal"),
    status_value: str = Form(default="todo"),
    due_date: str = Form(default="Сегодня"),
    student_id: str = Form(default=""),
    student_name: str = Form(default=""),
    notes: str = Form(default=""),
    result: str = Form(default=""),
    _: None = Depends(require_admin),
) -> Response:
    if not get_team_task(task_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
    linked_student_id = int(student_id) if student_id.strip().isdigit() else None
    update_team_task_fields(
        task_id,
        {
            "title": title.strip(),
            "assignee": assignee.strip() or "Куратор",
            "priority": priority if priority in TASK_PRIORITIES else "normal",
            "status": status_value if status_value in TASK_STATUSES else "todo",
            "due_date": due_date.strip() or "Сегодня",
            "student_id": linked_student_id,
            "student_name": student_name.strip(),
            "notes": notes.strip(),
            "result": result.strip(),
        },
    )
    log_activity(request, action="изменил", entity="задача", title=title.strip(), href=f"/tasks/{task_id}", details=f"Статус: {task_status_label(status_value)}")
    return RedirectResponse(f"/tasks/{task_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/tasks/{task_id}/status")
async def update_task_status(
    request: Request,
    task_id: str,
    status_value: str = Form(...),
    _: None = Depends(require_admin),
) -> Response:
    update_team_task(task_id, status_value=status_value)
    task = get_team_task(task_id)
    log_activity(request, action="сменил статус", entity="задача", title=str(task.get("title", task_id)) if task else task_id, href=f"/tasks/{task_id}", details=task_status_label(status_value))
    return RedirectResponse("/?view=team", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/tasks/{task_id}/delete")
async def delete_task(
    request: Request,
    task_id: str,
    _: None = Depends(require_admin),
) -> Response:
    task = get_team_task(task_id)
    delete_team_task(task_id)
    log_activity(request, action="удалил", entity="задача", title=str(task.get("title", task_id)) if task else task_id, details="Удалено из доски команды")
    return RedirectResponse("/?view=team", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/team/users")
async def create_team_user(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(...),
    role: str = Form(default="curator"),
    password: str = Form(...),
    _: dict[str, Any] = Depends(require_owner),
) -> Response:
    if username.strip() and password.strip():
        create_crm_user(username=username, display_name=display_name, role=role, password=password)
        log_activity(request, action="выдал доступ", entity="сотрудник", title=display_name.strip() or username.strip(), href="/?view=team", details=role_label(role))
    return RedirectResponse("/?view=team", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/team/users/{user_id}/status")
async def update_team_user_status(
    request: Request,
    user_id: str,
    active: str = Form(default="1"),
    _: dict[str, Any] = Depends(require_owner),
) -> Response:
    update_crm_user(user_id, active=active == "1")
    log_activity(request, action="изменил доступ", entity="сотрудник", title=user_id, href="/?view=team", details="Включен" if active == "1" else "Отключен")
    return RedirectResponse("/?view=team", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/business/clients")
async def create_business_client(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(default=""),
    company: str = Form(default=""),
    phone: str = Form(default=""),
    email: str = Form(default=""),
    source: str = Form(default=""),
    segment: str = Form(default=""),
    status_value: str = Form(default="new"),
    manager: str = Form(default=""),
    next_contact_at: str = Form(default=""),
    comments: str = Form(default=""),
    _: None = Depends(require_admin),
) -> Response:
    create_business_record(
        "clients",
        {
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "company": company.strip(),
            "phone": phone.strip(),
            "email": email.strip(),
            "messenger": "Telegram",
            "source": source.strip(),
            "segment": segment.strip(),
            "status": status_value,
            "manager": manager.strip() or "Продажи",
            "next_contact_at": next_contact_at.strip(),
            "total_amount": 0,
            "purchases_count": 0,
            "comments": comments.strip(),
            "tags": "",
        },
    )
    log_activity(request, action="создал", entity="клиент", title=f"{first_name} {last_name}".strip(), href="/?view=crm", details=f"Источник: {source or '-'}")
    return RedirectResponse("/?view=crm", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/business/clients/{client_id}", response_class=HTMLResponse)
async def business_client_detail(
    request: Request,
    client_id: str,
    _: None = Depends(require_admin),
) -> Response:
    data = load_business_os()
    client = next((item for item in data.get("clients", []) if item.get("id") == client_id), None)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клиент не найден")
    return templates.TemplateResponse(
        "business_client_detail.html",
        {
            "request": request,
            "client": client,
            "relations": business_client_relations(data, client),
        },
    )


@app.post("/business/clients/{client_id}")
async def update_business_client(
    request: Request,
    client_id: str,
    first_name: str = Form(...),
    last_name: str = Form(default=""),
    company: str = Form(default=""),
    phone: str = Form(default=""),
    email: str = Form(default=""),
    messenger: str = Form(default="Telegram"),
    source: str = Form(default=""),
    segment: str = Form(default=""),
    status_value: str = Form(default="new"),
    manager: str = Form(default=""),
    next_contact_at: str = Form(default=""),
    total_amount: int = Form(default=0),
    purchases_count: int = Form(default=0),
    comments: str = Form(default=""),
    tags: str = Form(default=""),
    _: None = Depends(require_admin),
) -> Response:
    if not get_business_record("clients", client_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клиент не найден")
    update_business_record(
        "clients",
        client_id,
        {
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "company": company.strip(),
            "phone": phone.strip(),
            "email": email.strip(),
            "messenger": messenger.strip(),
            "source": source.strip(),
            "segment": segment.strip(),
            "status": status_value.strip(),
            "manager": manager.strip() or "Продажи",
            "next_contact_at": next_contact_at.strip(),
            "total_amount": total_amount,
            "purchases_count": purchases_count,
            "comments": comments.strip(),
            "tags": tags.strip(),
        },
    )
    log_activity(request, action="изменил", entity="клиент", title=f"{first_name} {last_name}".strip(), href=f"/business/clients/{client_id}", details=f"Статус: {status_value}")
    return RedirectResponse(f"/business/clients/{client_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/business/clients/{client_id}/delete")
async def delete_business_client(
    request: Request,
    client_id: str,
    _: None = Depends(require_admin),
) -> Response:
    client = get_business_record("clients", client_id)
    delete_business_record("clients", client_id)
    log_activity(request, action="удалил", entity="клиент", title=client_full_name(client) if client else client_id, details="Удалено из CRM")
    return RedirectResponse("/?view=crm", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/business/leads")
async def create_business_lead(
    request: Request,
    client: str = Form(...),
    source: str = Form(default=""),
    campaign: str = Form(default=""),
    manager: str = Form(default=""),
    priority: str = Form(default="normal"),
    need: str = Form(default=""),
    planned_amount: int = Form(default=0),
    next_step: str = Form(default=""),
    next_contact_at: str = Form(default=""),
    _: None = Depends(require_admin),
) -> Response:
    create_business_record(
        "leads",
        {
            "client": client.strip(),
            "source": source.strip(),
            "campaign": campaign.strip(),
            "manager": manager.strip() or "Продажи",
            "status": "new",
            "priority": priority,
            "need": need.strip(),
            "planned_amount": planned_amount,
            "next_step": next_step.strip(),
            "next_contact_at": next_contact_at.strip(),
            "comments": "",
            "lost_reason": "",
        },
    )
    log_activity(request, action="создал", entity="лид", title=client.strip(), href="/?view=crm", details=f"Канал: {source or '-'}, сумма: {money(planned_amount)}")
    return RedirectResponse("/?view=crm", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/business/leads/{lead_id}", response_class=HTMLResponse)
async def business_lead_detail(
    request: Request,
    lead_id: str,
    _: None = Depends(require_admin),
) -> Response:
    lead = get_business_record("leads", lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Лид не найден")
    return templates.TemplateResponse(
        "business_lead_detail.html",
        {
            "request": request,
            "lead": lead,
            "deal_columns": deal_columns(load_business_os().get("deals", [])),
        },
    )


@app.post("/business/leads/{lead_id}")
async def update_business_lead(
    request: Request,
    lead_id: str,
    client: str = Form(...),
    source: str = Form(default=""),
    campaign: str = Form(default=""),
    manager: str = Form(default=""),
    status_value: str = Form(default="new"),
    priority: str = Form(default="normal"),
    need: str = Form(default=""),
    planned_amount: int = Form(default=0),
    next_step: str = Form(default=""),
    next_contact_at: str = Form(default=""),
    comments: str = Form(default=""),
    lost_reason: str = Form(default=""),
    _: None = Depends(require_admin),
) -> Response:
    if not get_business_record("leads", lead_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Лид не найден")
    update_business_record(
        "leads",
        lead_id,
        {
            "client": client.strip(),
            "source": source.strip(),
            "campaign": campaign.strip(),
            "manager": manager.strip() or "Продажи",
            "status": status_value.strip() or "new",
            "priority": priority if priority in TASK_PRIORITIES else "normal",
            "need": need.strip(),
            "planned_amount": planned_amount,
            "next_step": next_step.strip(),
            "next_contact_at": next_contact_at.strip(),
            "comments": comments.strip(),
            "lost_reason": lost_reason.strip(),
        },
    )
    log_activity(request, action="изменил", entity="лид", title=client.strip(), href=f"/business/leads/{lead_id}", details=f"Статус: {status_value}, сумма: {money(planned_amount)}")
    return RedirectResponse(f"/business/leads/{lead_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/business/leads/{lead_id}/delete")
async def delete_business_lead(
    request: Request,
    lead_id: str,
    _: None = Depends(require_admin),
) -> Response:
    lead = get_business_record("leads", lead_id)
    delete_business_record("leads", lead_id)
    log_activity(request, action="удалил", entity="лид", title=str(lead.get("client", lead_id)) if lead else lead_id, details="Удалено из CRM")
    return RedirectResponse("/?view=crm", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/business/deals/{deal_id}", response_class=HTMLResponse)
async def business_deal_detail(
    request: Request,
    deal_id: str,
    _: None = Depends(require_admin),
) -> Response:
    deal = get_business_record("deals", deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сделка не найдена")
    data = load_business_os()
    return templates.TemplateResponse(
        "business_deal_detail.html",
        {
            "request": request,
            "deal": deal,
            "clients": data.get("clients", []),
            "deal_columns": deal_columns(data.get("deals", [])),
        },
    )


@app.post("/business/deals")
async def create_business_deal(
    request: Request,
    title: str = Form(...),
    client: str = Form(...),
    amount: int = Form(default=0),
    cost: int = Form(default=0),
    manager: str = Form(default=""),
    stage: str = Form(default="Новый лид"),
    probability: int = Form(default=30),
    expected_close_at: str = Form(default=""),
    next_step: str = Form(default=""),
    _: None = Depends(require_admin),
) -> Response:
    create_business_record(
        "deals",
        {
            "title": title.strip(),
            "client": client.strip(),
            "amount": amount,
            "cost": cost,
            "margin": max(amount - cost, 0),
            "manager": manager.strip() or "Продажи",
            "stage": stage,
            "probability": probability,
            "expected_close_at": expected_close_at.strip(),
            "next_step": next_step.strip(),
            "comments": "",
            "lost_reason": "",
        },
    )
    log_activity(request, action="создал", entity="сделка", title=title.strip(), href="/?view=crm", details=f"{client.strip()} · {money(amount)}")
    return RedirectResponse("/?view=crm", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/business/deals/{deal_id}")
async def update_business_deal(
    request: Request,
    deal_id: str,
    title: str = Form(...),
    client: str = Form(...),
    amount: int = Form(default=0),
    cost: int = Form(default=0),
    manager: str = Form(default=""),
    stage: str = Form(default="Новый лид"),
    probability: int = Form(default=30),
    expected_close_at: str = Form(default=""),
    next_step: str = Form(default=""),
    comments: str = Form(default=""),
    lost_reason: str = Form(default=""),
    _: None = Depends(require_admin),
) -> Response:
    if not get_business_record("deals", deal_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сделка не найдена")
    update_business_record(
        "deals",
        deal_id,
        {
            "title": title.strip(),
            "client": client.strip(),
            "amount": amount,
            "cost": cost,
            "margin": max(amount - cost, 0),
            "manager": manager.strip() or "Продажи",
            "stage": stage.strip(),
            "probability": max(0, min(probability, 100)),
            "expected_close_at": expected_close_at.strip(),
            "next_step": next_step.strip(),
            "comments": comments.strip(),
            "lost_reason": lost_reason.strip(),
        },
    )
    log_activity(request, action="изменил", entity="сделка", title=title.strip(), href=f"/business/deals/{deal_id}", details=f"{stage} · {money(amount)}")
    return RedirectResponse(f"/business/deals/{deal_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/business/deals/{deal_id}/delete")
async def delete_business_deal(
    request: Request,
    deal_id: str,
    _: None = Depends(require_admin),
) -> Response:
    deal = get_business_record("deals", deal_id)
    delete_business_record("deals", deal_id)
    log_activity(request, action="удалил", entity="сделка", title=str(deal.get("title", deal_id)) if deal else deal_id, details="Удалено из воронки")
    return RedirectResponse("/?view=crm", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/business/deals/{deal_id}/stage")
async def update_business_deal_stage(
    request: Request,
    deal_id: str,
    stage: str = Form(...),
    _: None = Depends(require_admin),
) -> Response:
    update_business_record("deals", deal_id, {"stage": stage})
    deal = get_business_record("deals", deal_id)
    log_activity(request, action="перенёс", entity="сделка", title=str(deal.get("title", deal_id)) if deal else deal_id, href=f"/business/deals/{deal_id}", details=stage)
    return RedirectResponse("/?view=crm", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/business/cashflow")
async def create_cashflow_operation(
    request: Request,
    operation_date: str = Form(...),
    type_value: str = Form(default="income"),
    amount: int = Form(...),
    account: str = Form(default=""),
    category: str = Form(default=""),
    counterparty: str = Form(default=""),
    project: str = Form(default=""),
    responsible: str = Form(default=""),
    comment: str = Form(default=""),
    _: None = Depends(require_admin),
) -> Response:
    create_business_record(
        "cashflow",
        {
            "date": operation_date,
            "type": type_value if type_value in {"income", "expense"} else "expense",
            "amount": amount,
            "account": account.strip(),
            "category": category.strip(),
            "subcategory": "",
            "counterparty": counterparty.strip(),
            "project": project.strip(),
            "branch": "Онлайн",
            "direction": "Общее",
            "budget_item": category.strip(),
            "comment": comment.strip(),
            "responsible": responsible.strip() or "Финансы",
            "approval_status": "approved" if type_value == "income" else "pending",
            "author": "crm",
        },
    )
    log_activity(request, action="создал", entity="ДДС", title=f"{category or 'Операция'} · {money(amount)}", href="/?view=finance_os", details=f"{counterparty or '-'} · {operation_date}")
    return RedirectResponse("/?view=finance_os", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/business/cashflow/{operation_id}", response_class=HTMLResponse)
async def cashflow_detail(
    request: Request,
    operation_id: str,
    _: None = Depends(require_admin),
) -> Response:
    operation = get_business_record("cashflow", operation_id)
    if not operation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Операция не найдена")
    return templates.TemplateResponse(
        "business_cashflow_detail.html",
        {
            "request": request,
            "operation": operation,
        },
    )


@app.post("/business/cashflow/{operation_id}")
async def update_cashflow_operation(
    request: Request,
    operation_id: str,
    operation_date: str = Form(...),
    type_value: str = Form(default="income"),
    amount: int = Form(...),
    account: str = Form(default=""),
    category: str = Form(default=""),
    subcategory: str = Form(default=""),
    counterparty: str = Form(default=""),
    project: str = Form(default=""),
    branch: str = Form(default="Онлайн"),
    direction: str = Form(default="Общее"),
    budget_item: str = Form(default=""),
    responsible: str = Form(default=""),
    approval_status: str = Form(default="pending"),
    comment: str = Form(default=""),
    _: None = Depends(require_admin),
) -> Response:
    if not get_business_record("cashflow", operation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Операция не найдена")
    update_business_record(
        "cashflow",
        operation_id,
        {
            "date": operation_date,
            "type": type_value if type_value in {"income", "expense"} else "expense",
            "amount": amount,
            "account": account.strip(),
            "category": category.strip(),
            "subcategory": subcategory.strip(),
            "counterparty": counterparty.strip(),
            "project": project.strip(),
            "branch": branch.strip(),
            "direction": direction.strip(),
            "budget_item": budget_item.strip() or category.strip(),
            "comment": comment.strip(),
            "responsible": responsible.strip() or "Финансы",
            "approval_status": approval_status.strip() or "pending",
        },
    )
    log_activity(request, action="изменил", entity="ДДС", title=f"{category or 'Операция'} · {money(amount)}", href=f"/business/cashflow/{operation_id}", details=f"{counterparty or '-'} · {approval_status}")
    return RedirectResponse(f"/business/cashflow/{operation_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/business/cashflow/{operation_id}/delete")
async def delete_cashflow_operation(
    request: Request,
    operation_id: str,
    _: None = Depends(require_admin),
) -> Response:
    operation = get_business_record("cashflow", operation_id)
    delete_business_record("cashflow", operation_id)
    log_activity(request, action="удалил", entity="ДДС", title=str(operation.get("category", operation_id)) if operation else operation_id, details="Удалено из финансов")
    return RedirectResponse("/?view=finance_os", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/business/calendar")
async def create_calendar_payment(
    request: Request,
    due_date: str = Form(...),
    amount: int = Form(...),
    counterparty: str = Form(...),
    category: str = Form(default=""),
    priority: str = Form(default="normal"),
    responsible: str = Form(default=""),
    comment: str = Form(default=""),
    _: None = Depends(require_admin),
) -> Response:
    create_business_record(
        "calendar",
        {
            "due_date": due_date,
            "amount": amount,
            "counterparty": counterparty.strip(),
            "category": category.strip(),
            "project": "",
            "branch": "Онлайн",
            "priority": priority,
            "required": "yes",
            "responsible": responsible.strip() or "Финансы",
            "status": "planned",
            "comment": comment.strip(),
        },
    )
    log_activity(request, action="создал", entity="платёж", title=f"{counterparty.strip()} · {money(amount)}", href="/?view=finance_os", details=f"Срок: {due_date}")
    return RedirectResponse("/?view=finance_os", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/business/calendar/{payment_id}/status")
async def update_calendar_payment_status(
    request: Request,
    payment_id: str,
    status_value: str = Form(default="paid"),
    _: None = Depends(require_admin),
) -> Response:
    update_business_record("calendar", payment_id, {"status": status_value})
    payment = get_business_record("calendar", payment_id)
    log_activity(request, action="сменил статус", entity="платёж", title=str(payment.get("counterparty", payment_id)) if payment else payment_id, href="/?view=finance_os", details=status_value)
    return RedirectResponse("/?view=finance_os", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/jarwas", response_class=HTMLResponse)
async def jarwas_stats_page(request: Request, _: None = Depends(require_admin)) -> Response:
    return templates.TemplateResponse("jarwas_stats.html", {"request": request})


@app.get("/students", response_class=HTMLResponse)
async def students_page(
    request: Request,
    q: str | None = Query(default=None),
    level: str | None = Query(default=None),
    gender: str | None = Query(default=None),
    tariff: str | None = Query(default=None),
    payment_status: str | None = Query(default=None),
    activity: str | None = Query(default=None),
    ref: str | None = Query(default=None),
    week: int | None = Query(default=None, ge=1),
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    demo = False
    try:
        students = await load_students(
            db,
            q=q,
            level=level,
            gender=gender,
            tariff=tariff,
            payment_status=payment_status,
            activity=activity,
            week=week,
        )
        if ref:
            students = [item for item in students if student_referral_code(item) == ref]
    except (OSError, SQLAlchemyError):
        demo = True
        students = demo_students(
            q=q,
            level=level,
            gender=gender,
            tariff=tariff,
            payment_status=payment_status,
            activity=activity,
            ref=ref,
            week=week,
        )
    filters = {
        "q": q or "",
        "level": level or "",
        "gender": gender or "",
        "tariff": tariff or "",
        "payment_status": payment_status or "",
        "activity": activity or "",
        "ref": ref or "",
        "week": week or "",
    }

    return templates.TemplateResponse(
        "students.html",
        {
            "request": request,
            "students": students,
            "filters": filters,
            "export_qs": export_query(filters),
            "segments": student_segments(students),
            "gender_segments": gender_segments(students, demo_payments() if demo else []),
            "tariff_options": TARIFF_OPTIONS,
            "demo": demo,
        },
    )


@app.get("/students/export.csv")
async def export_students(
    q: str | None = Query(default=None),
    level: str | None = Query(default=None),
    gender: str | None = Query(default=None),
    tariff: str | None = Query(default=None),
    payment_status: str | None = Query(default=None),
    activity: str | None = Query(default=None),
    ref: str | None = Query(default=None),
    week: int | None = Query(default=None, ge=1),
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    try:
        students = await load_students(
            db,
            q=q,
            level=level,
            gender=gender,
            tariff=tariff,
            payment_status=payment_status,
            activity=activity,
            week=week,
        )
        if ref:
            students = [item for item in students if student_referral_code(item) == ref]
    except (OSError, SQLAlchemyError):
        students = demo_students(
            q=q,
            level=level,
            gender=gender,
            tariff=tariff,
            payment_status=payment_status,
            activity=activity,
            ref=ref,
            week=week,
        )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "telegram_id",
            "name",
            "username",
            "level",
            "gender",
            "week",
            "status",
            "activated_at",
            "last_activity",
            "last_diag_level",
            "last_diag_pct",
            "referral_code",
        ]
    )
    for item in students:
        writer.writerow(
            [
                item.user.id,
                item.user.name,
                item.user.username or "",
                level_label(item.participant.level) if item.participant else "",
                gender_label(item.user.is_female),
                item.participant.week if item.participant else "",
                status_label(item.status),
                fmt_dt(item.participant.activated_at if item.participant else None),
                fmt_dt(item.last_activity),
                level_label(item.last_diag.level_key) if item.last_diag else "",
                item.last_diag.pct if item.last_diag else "",
                student_referral_code(item) or "",
            ]
        )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=iqb_students.csv"},
    )


@app.get("/students/{user_id}", response_class=HTMLResponse)
async def student_detail(
    request: Request,
    user_id: int,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    demo = False
    try:
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

        participant = await db.scalar(select(Participant).where(Participant.user_id == user_id))
        diagnostics = list(
            await db.scalars(
                select(DiagResult).where(DiagResult.user_id == user_id).order_by(desc(DiagResult.created_at))
            )
        )
        payments = list(
            await db.scalars(select(Payment).where(Payment.user_id == user_id).order_by(desc(Payment.created_at)))
        )
        week_acks = list(await db.scalars(select(WeekAck).where(WeekAck.user_id == user_id).order_by(desc(WeekAck.acked_at))))
        trackers = list(
            await db.scalars(
                select(TrackerRecord).where(TrackerRecord.user_id == user_id).order_by(desc(TrackerRecord.date))
            )
        )
        wheels = list(
            await db.scalars(select(WheelRecord).where(WheelRecord.user_id == user_id).order_by(desc(WheelRecord.created_at)))
        )
        muhasaba = list(
            await db.scalars(select(MuhasabaLog).where(MuhasabaLog.user_id == user_id).order_by(desc(MuhasabaLog.created_at)))
        )
        task_count = await db.scalar(select(func.count()).select_from(TaskCompletion).where(TaskCompletion.user_id == user_id))
        tracker_count = await db.scalar(select(func.count()).select_from(TrackerRecord).where(TrackerRecord.user_id == user_id))
        muhasaba_count = await db.scalar(select(func.count()).select_from(MuhasabaLog).where(MuhasabaLog.user_id == user_id))
        barakah = BarakahMetrics(
            tasks_done=task_count or 0,
            tasks_total=max((participant.week if participant else 1) * 3, task_count or 0, 1),
            quran_pages=0,
            good_deeds=0,
            namaz_on_time=0,
            azkar_days=tracker_count or 0,
            muhasaba_days=muhasaba_count or 0,
            streak_days=min(tracker_count or 0, 7),
        )
    except (OSError, SQLAlchemyError):
        demo = True
        detail = demo_student_detail(user_id)
        if not detail:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
        user = detail["user"]
        participant = detail["participant"]
        diagnostics = detail["diagnostics"]
        payments = detail["payments"]
        week_acks = detail["week_acks"]
        trackers = detail["trackers"]
        wheels = detail["wheels"]
        muhasaba = detail["muhasaba"]
        barakah = detail["barakah"]
    learning = learning_snapshot(user, participant, diagnostics, payments, trackers, muhasaba, barakah)
    student_row = StudentRow(user=user, participant=participant, last_diag=diagnostics[0] if diagnostics else None, last_activity=learning["last_activity"])
    risk = risk_profile(student_row, payments, barakah)

    return templates.TemplateResponse(
        "student_detail.html",
        {
            "request": request,
            "user": user,
            "participant": participant,
            "diagnostics": diagnostics,
            "payments": payments,
            "week_acks": week_acks,
            "trackers": trackers,
            "wheels": wheels,
            "muhasaba": muhasaba,
            "barakah": barakah,
            "learning": learning,
            "risk": risk,
            "next_action": next_best_action(student_row, payments, barakah),
            "week_map": week_map(participant, barakah),
            "timeline": student_timeline(user, participant, diagnostics, payments, week_acks, trackers, muhasaba),
            "message_templates": message_templates(risk),
            "demo": demo,
        },
    )


async def load_dashboard_stats(db: AsyncSession) -> dict[str, int]:
    total_users = await db.scalar(select(func.count()).select_from(User))
    active_students = await db.scalar(select(func.count()).select_from(Participant).where(Participant.is_active.is_(True)))
    graduated_students = await db.scalar(
        select(func.count()).select_from(Participant).where(Participant.graduated_at.is_not(None))
    )
    paid_payments = await db.scalar(select(func.count()).select_from(Payment).where(Payment.status == "paid"))
    paid_total = await db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "paid"))
    return {
        "total_users": total_users or 0,
        "active_students": active_students or 0,
        "graduated_students": graduated_students or 0,
        "paid_payments": paid_payments or 0,
        "paid_total": paid_total or 0,
    }


async def load_students(
    db: AsyncSession,
    *,
    q: str | None = None,
    level: str | None = None,
    gender: str | None = None,
    tariff: str | None = None,
    payment_status: str | None = None,
    activity: str | None = None,
    week: int | None = None,
    limit: int | None = None,
) -> list[StudentRow]:
    latest_diag_at = (
        select(DiagResult.user_id, func.max(DiagResult.created_at).label("created_at"))
        .group_by(DiagResult.user_id)
        .subquery()
    )
    latest_tracker_at = (
        select(TrackerRecord.user_id, func.max(TrackerRecord.updated_at).label("last_at"))
        .group_by(TrackerRecord.user_id)
        .subquery()
    )
    latest_wheel_at = (
        select(WheelRecord.user_id, func.max(WheelRecord.created_at).label("last_at"))
        .group_by(WheelRecord.user_id)
        .subquery()
    )
    latest_muhasaba_at = (
        select(MuhasabaLog.user_id, func.max(MuhasabaLog.created_at).label("last_at"))
        .group_by(MuhasabaLog.user_id)
        .subquery()
    )
    latest_week_ack_at = (
        select(WeekAck.user_id, func.max(WeekAck.acked_at).label("last_at"))
        .group_by(WeekAck.user_id)
        .subquery()
    )
    latest_payment_at = (
        select(Payment.user_id, func.max(Payment.created_at).label("last_at"))
        .group_by(Payment.user_id)
        .subquery()
    )
    last_diag = aliased(DiagResult)
    last_activity = func.greatest(
        func.coalesce(User.updated_at, datetime(1970, 1, 1, tzinfo=timezone.utc)),
        func.coalesce(Participant.activated_at, datetime(1970, 1, 1, tzinfo=timezone.utc)),
        func.coalesce(latest_diag_at.c.created_at, datetime(1970, 1, 1, tzinfo=timezone.utc)),
        func.coalesce(latest_tracker_at.c.last_at, datetime(1970, 1, 1, tzinfo=timezone.utc)),
        func.coalesce(latest_wheel_at.c.last_at, datetime(1970, 1, 1, tzinfo=timezone.utc)),
        func.coalesce(latest_muhasaba_at.c.last_at, datetime(1970, 1, 1, tzinfo=timezone.utc)),
        func.coalesce(latest_week_ack_at.c.last_at, datetime(1970, 1, 1, tzinfo=timezone.utc)),
        func.coalesce(latest_payment_at.c.last_at, datetime(1970, 1, 1, tzinfo=timezone.utc)),
    ).label("last_activity")

    stmt: Select[tuple[User, Participant | None, DiagResult | None, datetime | None]] = (
        select(User, Participant, last_diag, last_activity)
        .outerjoin(Participant, Participant.user_id == User.id)
        .outerjoin(latest_diag_at, latest_diag_at.c.user_id == User.id)
        .outerjoin(
            last_diag,
            and_(last_diag.user_id == User.id, last_diag.created_at == latest_diag_at.c.created_at),
        )
        .outerjoin(latest_tracker_at, latest_tracker_at.c.user_id == User.id)
        .outerjoin(latest_wheel_at, latest_wheel_at.c.user_id == User.id)
        .outerjoin(latest_muhasaba_at, latest_muhasaba_at.c.user_id == User.id)
        .outerjoin(latest_week_ack_at, latest_week_ack_at.c.user_id == User.id)
        .outerjoin(latest_payment_at, latest_payment_at.c.user_id == User.id)
    )

    if q:
        needle = f"%{q.strip()}%"
        search_terms = [
            User.name.ilike(needle),
            User.username.ilike(needle),
            User.email.ilike(needle),
            User.phone.ilike(needle),
        ]
        if q.strip().isdigit():
            search_terms.append(User.id == int(q.strip()))
        stmt = stmt.where(or_(*search_terms))
    if level:
        stmt = stmt.where(Participant.level.in_(level_filter_values(level)))
    if gender == "female":
        stmt = stmt.where(User.is_female.is_(True))
    elif gender == "male":
        stmt = stmt.where(User.is_female.is_(False))
    elif gender == "unknown":
        stmt = stmt.where(User.is_female.is_(None))
    if tariff or payment_status:
        payment_match = select(Payment.id).where(Payment.user_id == User.id)
        if tariff:
            payment_match = payment_match.where(Payment.tariff_id == tariff)
        if payment_status:
            payment_match = payment_match.where(Payment.status == payment_status)
        stmt = stmt.where(payment_match.exists())
    if week:
        stmt = stmt.where(Participant.week == week)
    if activity == "active":
        stmt = stmt.where(and_(Participant.is_active.is_(True), Participant.graduated_at.is_(None)))
    elif activity == "graduated":
        stmt = stmt.where(Participant.graduated_at.is_not(None))
    elif activity == "inactive":
        stmt = stmt.where(or_(Participant.id.is_(None), Participant.is_active.is_(False)))

    stmt = stmt.order_by(desc(last_activity), desc(User.created_at))
    if limit:
        stmt = stmt.limit(limit)

    rows = await db.execute(stmt)
    return [StudentRow(user=row[0], participant=row[1], last_diag=row[2], last_activity=row[3]) for row in rows.all()]
