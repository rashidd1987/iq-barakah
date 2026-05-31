"""Уроки программы, подтверждение недели, прогресс."""
import logging
from urllib.parse import urlencode

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.config import Config
from bot_v2.db.models import WeekAck
from bot_v2.db.repositories import ParticipantRepo, UserRepo
from bot_v2.keyboards import kb_week_ack
from bot_v2.services.i18n import t
from bot_v2.services.program import LEVEL_NAMES, LEVEL_WEEKS
from bot_v2.services.program_content import PROGRAM

logger = logging.getLogger(__name__)

router = Router(name="program")


@router.message(Command("progress"))
async def cmd_progress(message: Message, session: AsyncSession):
    lang = await _user_lang(session, message.from_user.id)
    repo = ParticipantRepo(session)
    p = await repo.get(message.from_user.id)
    if not p:
        await message.answer(t(lang, "progress.not_active"))
        return

    max_weeks = LEVEL_WEEKS.get(p.level, 8)
    pct = round((p.week - 1) / max_weeks * 100)
    text = (
        f"{t(lang, 'progress.title')}\n\n"
        f"📍 {LEVEL_NAMES.get(p.level, p.level)}\n"
        f"{t(lang, 'progress.week', week=p.week, max_weeks=max_weeks, pct=pct)}"
    )
    await message.answer(text, parse_mode="Markdown")


@router.callback_query(F.data == "week_ack")
async def cb_week_ack(call: CallbackQuery, session: AsyncSession, config: Config = None):
    await call.answer()
    uid = call.from_user.id
    lang = await _user_lang(session, uid)
    repo = ParticipantRepo(session)
    p = await repo.get(uid)
    if not p:
        await call.message.answer(t(lang, "week.not_active"))
        return

    level = p.level
    current_week = p.week
    max_weeks = LEVEL_WEEKS.get(level, 8)

    stmt = insert(WeekAck).values(user_id=uid, level=level, week=current_week)
    stmt = stmt.on_conflict_do_nothing(constraint="uq_week_ack")
    await session.execute(stmt)

    if current_week >= max_weeks:
        await repo.graduate(uid)
        await call.message.answer(
            t(lang, "week.graduated", level=LEVEL_NAMES.get(level, level)),
            parse_mode="Markdown"
        )
    else:
        await repo.advance_week(uid)
        await call.message.answer(
            t(lang, "week.acked", week=current_week),
            parse_mode="Markdown"
        )
        # Сдал досрочно — сразу даём следующий урок, не ждём понедельника
        try:
            p_next = await repo.get(uid)
            if p_next:
                await send_weekly_lesson(call.bot, uid, p_next, session, config)
        except Exception as e:
            logger.warning("send_weekly_lesson after week_ack failed for %s: %s", uid, e)


async def send_weekly_lesson(bot, user_id: int, participant, session: AsyncSession, config):
    """Отправить урок недели участнику. BOT = LEARNING — полный текст урока."""
    from bot_v2.db.repositories import LessonMediaRepo

    level = participant.level
    week = participant.week
    max_weeks = LEVEL_WEEKS.get(level, 8)
    lang = await _user_lang(session, user_id)
    user = await UserRepo(session).get(user_id)
    name = (user.name or "Брат").split()[0] if user else "Брат"

    if week > max_weeks:
        return

    # Получаем контент урока
    lessons = PROGRAM.get(level, [])
    week_idx = week - 1
    if week_idx >= len(lessons):
        return

    lesson = lessons[week_idx]
    title = lesson["title"]

    # Уровень навыка участника (I / II / III) — общий для всех программ
    skill_level = participant.vakt_level or "I"

    # Текст урока по уровню навыка
    raw_text = lesson["text"]
    if isinstance(raw_text, dict):
        text_body = raw_text.get(skill_level, raw_text.get("I", ""))
    else:
        text_body = raw_text.replace("{name}", name)

    # Задания по уровню навыка
    raw_tasks = lesson["tasks"]
    if isinstance(raw_tasks, dict):
        level_tasks = raw_tasks.get(skill_level, raw_tasks.get("I", []))
        tasks = "\n".join(f"  {t_}" for t_ in level_tasks)
    else:
        tasks = "\n".join(f"  {t_}" for t_ in raw_tasks)

    lesson_text = (
        f"📅 *{title}*\n"
        f"_{LEVEL_NAMES.get(level, level)} · Неделя {week} из {max_weeks}_\n\n"
        f"{text_body}\n\n"
        f"*Задания на эту неделю:*\n{tasks}"
    )

    sep = "&" if "?" in config.miniapp_url else "?"
    miniapp_link = f"{config.miniapp_url}{sep}{urlencode({'lvl': level, 'wk': week, 'lang': lang, 'skill': skill_level})}"

    media_repo = LessonMediaRepo(session)
    video = await media_repo.get(level, week, "video")
    audio = await media_repo.get(level, week, "audio")

    # Кнопка подтверждения
    if level == "А":
        ack_label = "✅ Выполнил задания — открыть следующую неделю"
    else:
        ack_label = "✅ Понял, иду делать"

    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Открыть карту пути", web_app=WebAppInfo(url=miniapp_link))],
        [InlineKeyboardButton(ack_label, callback_data="week_ack")],
    ])

    if video:
        try:
            if video.startswith("http"):
                await bot.send_message(
                    chat_id=user_id,
                    text=f"🎬 *Видео-урок — Неделя {week}*\n\n{video}",
                    parse_mode="Markdown",
                )
            else:
                await bot.send_video(
                    chat_id=user_id, video=video,
                    caption=f"🎬 *Видео-урок — Неделя {week}*",
                    parse_mode="Markdown",
                )
        except Exception:
            pass

    if audio:
        try:
            await bot.send_voice(
                chat_id=user_id, voice=audio,
                caption="🎙 *Аудио-версия* — слушай где удобно",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    # Максимальная длина caption Telegram — 1024 символа
    if len(lesson_text) > 4096:
        lesson_text = lesson_text[:4090] + "…"

    await bot.send_message(
        chat_id=user_id,
        text=lesson_text,
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def _user_lang(session: AsyncSession, user_id: int) -> str:
    user = await UserRepo(session).get(user_id)
    return user.language_code if user else "ru"
