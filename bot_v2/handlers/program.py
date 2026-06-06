"""Уроки программы, подтверждение недели, прогресс, апсейл после ВАКТ."""
import asyncio
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

    await call.message.answer(
        t(lang, "week.acked", week=current_week),
        parse_mode="Markdown"
    )


async def send_weekly_lesson(bot, user_id: int, participant, session: AsyncSession, config):
    """Отправить урок недели участнику."""
    from bot_v2.db.repositories import LessonMediaRepo

    level = participant.level
    week = participant.week
    max_weeks = LEVEL_WEEKS.get(level, 8)
    lang = await _user_lang(session, user_id)
    user = await UserRepo(session).get(user_id)
    is_female = user.is_female if user else False
    brother_sister = "сестра" if is_female else "брат"
    name = (user.name or ("Сестра" if is_female else "Брат")).split()[0] if user else ("Сестра" if is_female else "Брат")

    if week > max_weeks:
        return

    # Первый урок — введение в программу
    if week == 1:
        intro = (
            "📖 *Прежде чем начать — прочитай это*\n\n"
            "Эта программа — не экзамен и не суд. Здесь никто не скажет тебе, что ты «плохой» или «недостаточный» мусульманин/мусульманка. Таких слов здесь не будет вообще.\n\n"
            "Может быть, ты молишься пять раз в день. Может быть — иногда, когда получается. А может быть — пока совсем нет, но что-то внутри тебя тянется ближе, и поэтому ты сейчас читаешь эти строки.\n\n"
            "Где бы ты ни был — этого достаточно, чтобы начать. Ты мусульманин/мусульманка, и ты здесь. Дверь открыта ровно там, где ты стоишь сегодня.\n\n"
            "Каждая неделя даётся в трёх уровнях. Ты сам/сама выбираешь свой — честно, без давления. Начни с того, что тебе по силам именно сейчас.\n\n"
            "_Идём спокойно, шаг за шагом._ 🌿"
        )
        await bot.send_message(chat_id=user_id, text=intro, parse_mode="Markdown")

    # Контент урока
    lessons = PROGRAM.get(level, [])
    week_idx = week - 1
    if week_idx >= len(lessons):
        return

    lesson = lessons[week_idx]
    title = lesson["title"]
    skill_level = participant.vakt_level or "I"

    raw_text = lesson["text"]
    if isinstance(raw_text, dict):
        text_body = raw_text.get(skill_level, raw_text.get("I", ""))
    else:
        text_body = raw_text.replace("{name}", name)

    raw_tasks = lesson["tasks"]
    if isinstance(raw_tasks, dict):
        level_tasks = raw_tasks.get(skill_level, raw_tasks.get("I", []))
        tasks = "\n".join(f"  {t_}" for t_ in level_tasks)
    else:
        tasks = "\n".join(f"  {t_}" for t_ in raw_tasks)

    hadith = lesson.get("hadith", "")
    hadith_block = f"\n📌 *Хадис недели:*\n{hadith}\n" if hadith else ""

    lesson_text = (
        f"🌿 *{title}*\n"
        f"_{LEVEL_NAMES.get(level, level)} · Неделя {week} из {max_weeks}_\n"
        f"{hadith_block}\n"
        f"{text_body}\n\n"
        f"*Задания на эту неделю:*\n{tasks}"
    )

    sep = "&" if "?" in config.miniapp_url else "?"
    miniapp_link = f"{config.miniapp_url}{sep}{urlencode({'lvl': level, 'wk': week, 'lang': lang, 'skill': skill_level})}"

    media_repo = LessonMediaRepo(session)
    video = await media_repo.get(level, week, "video")
    audio = await media_repo.get(level, week, "audio")

    if level == "А":
        ack_label = "✅ Выполнил задания — открыть следующую неделю"
    else:
        ack_label = "✅ Понял, иду делать"

    reply_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Открыть карту пути", web_app=WebAppInfo(url=miniapp_link))],
        [InlineKeyboardButton(text=ack_label, callback_data="week_ack")],
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

    if len(lesson_text) > 4096:
        lesson_text = lesson_text[:4090] + "…"

    try:
        await bot.send_message(
            chat_id=user_id,
            text=lesson_text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )
    except Exception as md_err:
        logger.warning("send_message Markdown failed (%s), retrying plain text", md_err)
        plain = lesson_text.replace("*", "").replace("_", "")
        await bot.send_message(
            chat_id=user_id,
            text=plain,
            reply_markup=reply_markup,
        )

    # ── АПСЕЙЛ: последняя неделя ВАКТ → Сезон 1 ──────────────────────────
    if level == "А" and week == max_weeks:
        asyncio.create_task(
            _send_vakt_graduation_upsell(bot, user_id, is_female)
        )


async def _send_vakt_graduation_upsell(bot, user_id: int, is_female: bool = False):
    """Поздравление + оффер Сезон 1 после 6-й недели ВАКТ. Отправляется через 4 секунды."""
    await asyncio.sleep(4)

    brat = "сестра" if is_female else "брат"

    text = (
        f"🎓 *БаракАллаху фик (да благословит тебя Аллах), {brat}!*\n\n"
        f"Ты завершил *ВАКТ* — 6 недель системы дня.\n\n"
        f"Это не просто курс. Ты выстроил якорь утра, научился возвращаться к намерению "
        f"и прожил 6 недель осознанно. Аллах видит каждый шаг.\n\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"*Что дальше?*\n\n"
        f"ВАКТ — это фундамент. Теперь можно строить.\n\n"
        f"📗 *IQ Barakah · Сезон 1 · Основание*\n"
        f"8 недель: кто ты есть, как живёшь, зачем всё это.\n"
        f"Семья, дело, здоровье, смысл — в одной системе.\n\n"
        f"_Те кто прошёл ВАКТ идут в Сезон 1 с готовым ритмом. "
        f"Это лучший момент для следующего шага._ 🌿"
    )

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📗 Сезон 1 — 5 000 ₽/мес",
            callback_data="tariff:s1_month",
        )],
        [InlineKeyboardButton(
            text="📗 Сезон 1 полный — 10 000 ₽",
            callback_data="tariff:s1_full",
        )],
        [InlineKeyboardButton(
            text="🏆 Все 3 сезона — 27 000 ₽",
            callback_data="tariff:s3_full",
        )],
        [InlineKeyboardButton(
            text="💬 Поговорить с куратором",
            callback_data="contact_curator",
        )],
    ])

    try:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=markup,
        )
    except Exception as e:
        logger.warning("vakt_graduation_upsell failed for %s: %s", user_id, e)


async def _user_lang(session: AsyncSession, user_id: int) -> str:
    user = await UserRepo(session).get(user_id)
    return user.language_code if user else "ru"
