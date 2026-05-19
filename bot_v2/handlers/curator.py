"""Команды куратора: /activate, /deactivate, /participants, /setcalllink, /pair."""
import logging
from datetime import timezone, datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.config import Config
from bot_v2.db.models import BotSetting
from bot_v2.db.repositories import ParticipantRepo, UserRepo, SettingsRepo, PairRepo
from bot_v2.services.program import LEVEL_NAMES, LEVEL_WEEKS

logger = logging.getLogger(__name__)
router = Router(name="curator")


def is_curator(user_id: int, config: Config) -> bool:
    return user_id in config.curator_ids


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
    db_user, _ = await user_repo.get_or_create(target_id, f"Участник {target_id}")

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
