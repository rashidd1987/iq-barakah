"""Команды куратора: /activate, /deactivate, /participants, /setcalllink, /pair."""
import logging
from datetime import timezone, datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.config import Config
from bot_v2.db.models import DiagResult, Participant, Payment, TrackerRecord, User, WeekAck, WheelRecord
from bot_v2.db.repositories import ParticipantRepo, UserRepo, SettingsRepo, PairRepo
from bot_v2.services.program import LEVEL_NAMES, LEVEL_WEEKS
from bot_v2.services.insights import analyze_participant

logger = logging.getLogger(__name__)
router = Router(name="curator")


def is_curator(user_id: int, config: Config) -> bool:
    return user_id in config.curator_ids


@router.message(Command("health"))
async def cmd_health(message: Message, session: AsyncSession, config: Config):
    if not is_curator(message.from_user.id, config):
        return

    try:
        users_count = await _scalar_count(session, User.id)
        active_count = await _scalar_count(session, Participant.id, Participant.is_active == True)
        diag_count = await _scalar_count(session, DiagResult.id)
        payment_count = await _scalar_count(session, Payment.id)
        tracker_count = await _scalar_count(session, TrackerRecord.id)

        checks = [
            "✅ База данных: подключена",
            f"✅ Пользователи: {users_count}",
            f"✅ Активные участники: {active_count}",
            f"✅ Диагностики: {diag_count}",
            f"✅ Платежи: {payment_count}",
            f"✅ Записи трекера: {tracker_count}",
            f"{'✅' if config.anthropic_api_key else '⚠️'} ANTHROPIC_API_KEY: {'задан' if config.anthropic_api_key else 'не задан'}",
            f"{'✅' if config.payments_provider_token else '⚠️'} PAYMENTS_TOKEN: {'задан' if config.payments_provider_token else 'не задан'}",
            f"{'✅' if config.yookassa_shop_id and config.yookassa_secret_key else '⚠️'} YooKassa: {'задана' if config.yookassa_shop_id and config.yookassa_secret_key else 'не задана'}",
        ]
        await message.answer("🩺 *Health check bot_v2*\n\n" + "\n".join(checks), parse_mode="Markdown")
    except Exception as exc:
        logger.exception("Health check failed")
        await message.answer(f"❌ Health check упал:\n`{type(exc).__name__}: {exc}`", parse_mode="Markdown")


@router.message(Command("analytics"))
async def cmd_analytics(message: Message, session: AsyncSession, config: Config):
    if not is_curator(message.from_user.id, config):
        return

    total_users = await _scalar_count(session, User.id)
    active_count = await _scalar_count(session, Participant.id, Participant.is_active == True)
    inactive_count = await _scalar_count(session, Participant.id, Participant.is_active == False)
    diag_count = await _scalar_count(session, DiagResult.id)
    week_ack_count = await _scalar_count(session, WeekAck.id)
    wheel_count = await _scalar_count(session, WheelRecord.id)

    level_rows = await session.execute(
        select(Participant.level, func.count(Participant.id))
        .where(Participant.is_active == True)
        .group_by(Participant.level)
        .order_by(Participant.level)
    )
    levels = {level: count for level, count in level_rows.all()}
    level_lines = [
        f"• {level} — {levels.get(level, 0)}"
        for level in LEVEL_WEEKS
    ]

    recent_rows = await session.execute(
        select(User)
        .order_by(User.created_at.desc())
        .limit(5)
    )
    recent_users = list(recent_rows.scalars())
    recent_lines = [
        f"• `{user.id}` — {user.name}" + (f" (@{user.username})" if user.username else "")
        for user in recent_users
    ] or ["• пока нет пользователей"]

    text = (
        "📊 *Аналитика IQ Barakah*\n\n"
        f"👥 Всего пользователей: *{total_users}*\n"
        f"🌿 Активные участники: *{active_count}*\n"
        f"⏸ Неактивные/завершившие: *{inactive_count}*\n"
        f"🎯 Диагностики: *{diag_count}*\n"
        f"✅ Подтверждения недель: *{week_ack_count}*\n"
        f"🧭 Колёса баланса: *{wheel_count}*\n\n"
        "*По уровням:*\n"
        + "\n".join(level_lines)
        + "\n\n*Последние пользователи:*\n"
        + "\n".join(recent_lines)
    )
    await message.answer(text, parse_mode="Markdown")


async def _scalar_count(session: AsyncSession, column, *filters) -> int:
    stmt = select(func.count(column))
    if filters:
        stmt = stmt.where(*filters)
    result = await session.execute(stmt)
    return int(result.scalar_one() or 0)


@router.message(Command("activate"))
async def cmd_activate(message: Message, session: AsyncSession, config: Config):
    if not is_curator(message.from_user.id, config):
        return
    args = message.text.split()[1:]
    if len(args) < 2:
        await message.answer("Использование: `/activate <user_id> <level> [week]`", parse_mode="Markdown")
        return

    try:
        target_id = int(args[0])
        level = args[1].upper()
        week = int(args[2]) if len(args) >= 3 else 1
    except ValueError:
        await message.answer("❌ Неверные аргументы.")
        return

    if level not in LEVEL_WEEKS:
        await message.answer(f"❌ Уровень должен быть: {', '.join(LEVEL_WEEKS.keys())}")
        return

    week = max(1, min(week, LEVEL_WEEKS[level]))

    user_repo = UserRepo(session)
    await user_repo.get_or_create(target_id, f"Участник {target_id}")

    p_repo = ParticipantRepo(session)
    await p_repo.activate(target_id, level, week)

    # Автопарринг
    pair_repo = PairRepo(session)
    partner_id = await _auto_pair(target_id, pair_repo, p_repo)
    pair_status = "🤝 Якорный партнёр назначен" if partner_id else "⏳ Ждёт пары"

    await message.answer(
        f"✅ *Активировано*\n\n"
        f"👤 ID: `{target_id}`\n"
        f"📍 Уровень: *{level}* — {LEVEL_NAMES.get(level, '')}\n"
        f"📅 Неделя: *{week}*\n"
        f"{pair_status}",
        parse_mode="Markdown"
    )


async def _auto_pair(uid: int, pair_repo: PairRepo, p_repo: ParticipantRepo) -> int | None:
    paired = await pair_repo.paired_ids()
    if uid in paired:
        return None
    active = await p_repo.all_active()
    for p in active:
        if p.user_id != uid and p.user_id not in paired:
            await pair_repo.create_pair(uid, p.user_id)
            return p.user_id
    return None


@router.message(Command("deactivate"))
async def cmd_deactivate(message: Message, session: AsyncSession, config: Config):
    if not is_curator(message.from_user.id, config):
        return
    args = message.text.split()[1:]
    if not args:
        await message.answer("Использование: `/deactivate <user_id>`", parse_mode="Markdown")
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await message.answer("❌ Неверный user_id.")
        return

    repo = ParticipantRepo(session)
    await repo.deactivate(target_id)
    await message.answer(f"✅ Пользователь `{target_id}` деактивирован.", parse_mode="Markdown")


@router.message(Command("participants"))
async def cmd_participants(message: Message, session: AsyncSession, config: Config):
    if not is_curator(message.from_user.id, config):
        return
    repo = ParticipantRepo(session)
    all_p = await repo.all_active()
    if not all_p:
        await message.answer("Нет активных участников.")
        return
    lines = ["👥 *Активные участники:*\n"]
    for p in all_p:
        name = p.user.name if p.user else str(p.user_id)
        max_w = LEVEL_WEEKS.get(p.level, 8)
        lines.append(f"• `{p.user_id}` — {name} | {LEVEL_NAMES.get(p.level, p.level)} | нед {p.week}/{max_w}")
    await message.answer("\n".join(lines), parse_mode="Markdown")


@router.message(Command("setcalllink"))
async def cmd_setcalllink(message: Message, session: AsyncSession, config: Config):
    if not is_curator(message.from_user.id, config):
        return
    args = message.text.split()[1:]
    repo = SettingsRepo(session)
    if not args:
        current = await repo.get("call_link", config.default_call_link)
        await message.answer(f"Текущая ссылка: {current}\n\nЧтобы изменить:\n`/setcalllink <ссылка>`",
                             parse_mode="Markdown")
        return
    await repo.set("call_link", args[0])
    await message.answer(f"✅ Ссылка обновлена:\n{args[0]}")


@router.message(Command("pair"))
async def cmd_pair(message: Message, session: AsyncSession, config: Config):
    if not is_curator(message.from_user.id, config):
        return
    args = message.text.split()[1:]
    if len(args) < 2:
        await message.answer("Использование: `/pair <uid1> <uid2>`", parse_mode="Markdown")
        return
    try:
        uid1, uid2 = int(args[0]), int(args[1])
    except ValueError:
        await message.answer("❌ Неверные user_id.")
        return

    repo = PairRepo(session)
    await repo.create_pair(uid1, uid2)
    await message.answer(f"✅ Пара создана: `{uid1}` ↔ `{uid2}`", parse_mode="Markdown")


@router.message(Command("analyze"))
async def cmd_analyze(message: Message, session: AsyncSession, config: Config):
    """Анализ участника через AI: /analyze <user_id>"""
    if not is_curator(message.from_user.id, config):
        return
    args = message.text.split()[1:]
    if not args:
        await message.answer("Использование: `/analyze <user_id>`", parse_mode="Markdown")
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await message.answer("❌ Неверный user_id.")
        return

    user_repo = UserRepo(session)
    user = await user_repo.get(target_id)
    if not user:
        await message.answer("❌ Пользователь не найден.")
        return

    p_repo = ParticipantRepo(session)
    participant = await p_repo.get_by_user(target_id)
    if not participant:
        await message.answer("❌ Пользователь не является активным участником.")
        return

    # Считаем дни молчания
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    last_active = getattr(user, "updated_at", None)
    silence_days = (now - last_active).days if last_active else 0

    # Берём последние мухасаба и трекер
    muhasaba = [log.answers for log in user.muhasaba_logs[-5:]] if user.muhasaba_logs else []
    tracker = [r.habits for r in user.tracker_records[-7:]] if user.tracker_records else []

    await message.answer("🔍 Анализирую...")

    insight = await analyze_participant(
        name=user.name,
        level=participant.level,
        week=participant.week,
        occupation=user.occupation,
        age=user.age,
        silence_days=silence_days,
        muhasaba_answers=muhasaba,
        tracker_habits=tracker,
    )

    if not insight:
        await message.answer("❌ AI-анализ недоступен. Проверь ANTHROPIC_API_KEY.")
        return

    RISK_EMOJI = {"low": "🟢", "medium": "🟡", "high": "🔴"}
    await message.answer(
        f"🤖 *AI-анализ участника*\n\n"
        f"👤 {user.name} · {participant.level} нед {participant.week}\n"
        f"{RISK_EMOJI.get(insight.risk, '⚪')} Риск: *{insight.risk.upper()}*\n\n"
        f"📊 {insight.summary}\n\n"
        f"⚠️ *Проблема:* {insight.issue}\n\n"
        f"✅ *Действие:* {insight.action}",
        parse_mode="Markdown",
    )


@router.callback_query(F.data.startswith("curator_activate:"))
async def cb_curator_activate(call: CallbackQuery, session: AsyncSession, config: Config):
    if not is_curator(call.from_user.id, config):
        await call.answer("⛔️ Нет прав.")
        return
    _, user_id_str, tariff_id = call.data.split(":")
    user_id = int(user_id_str)

    # Определяем уровень по тарифу
    tariff_to_level = {"vakt": "А", "s1_full": "Б", "s3_full": "Б"}
    level = tariff_to_level.get(tariff_id, "Б")

    repo = ParticipantRepo(session)
    await repo.activate(user_id, level, week=1)

    await call.answer("Активировано!")
    await call.message.edit_text(
        call.message.text + f"\n\n✅ Активирован на уровень {level}"
    )
