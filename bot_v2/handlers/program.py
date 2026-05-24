"""Уроки программы, подтверждение недели, прогресс."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.db.models import WeekAck
from bot_v2.db.repositories import ParticipantRepo, UserRepo
from bot_v2.keyboards import kb_week_ack
from bot_v2.services.i18n import t
from bot_v2.services.program import LEVEL_NAMES, LEVEL_WEEKS

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
async def cb_week_ack(call: CallbackQuery, session: AsyncSession):
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

    # Сохраняем подтверждение
    ack = WeekAck(user_id=uid, level=level, week=current_week)
    session.add(ack)

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


async def send_weekly_lesson(bot, user_id: int, participant, session: AsyncSession, config):
    """Отправить урок недели участнику. Вызывается из джоба."""
    from bot_v2.db.repositories import LessonMediaRepo
    from bot_v2.services.program import LEVEL_NAMES, LEVEL_WEEKS

    level = participant.level
    week = participant.week
    max_weeks = LEVEL_WEEKS.get(level, 8)
    lang = await _user_lang(session, user_id)

    if week > max_weeks:
        return

    media_repo = LessonMediaRepo(session)
    video = await media_repo.get(level, week, "video")
    audio = await media_repo.get(level, week, "audio")

    text = (
        f"📖 *{LEVEL_NAMES.get(level, level)}*\n"
        f"_Неделя {week} из {max_weeks}_\n\n"
        f"{t(lang, 'lesson.ready')}\n\n"
        f"[{t(lang, 'lesson.open')}]({config.miniapp_url}?lvl={level}&wk={week}&lang={lang})"
    )

    if video:
        try:
            await bot.send_video(chat_id=user_id, video=video,
                                 caption=text, parse_mode="Markdown",
                                 reply_markup=kb_week_ack())
            return
        except Exception:
            pass

    if audio:
        try:
            await bot.send_audio(chat_id=user_id, audio=audio,
                                 caption=text, parse_mode="Markdown",
                                 reply_markup=kb_week_ack())
            return
        except Exception:
            pass

    await bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown",
                           disable_web_page_preview=False,
                           reply_markup=kb_week_ack())


async def _user_lang(session: AsyncSession, user_id: int) -> str:
    user = await UserRepo(session).get(user_id)
    return user.language_code if user else "ru"
