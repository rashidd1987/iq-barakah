"""Отправка материалов форума участнику после оплаты."""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot
from aiogram.types import BufferedInputFile

from bot_v2.db.repositories import UserRepo, SettingsRepo
from bot_v2.services.png_generator import generate_checklist, generate_ticket

logger = logging.getLogger(__name__)

_COUNTER_KEY = "forum_27_06:ticket_counter"


async def _next_ticket_no(session: AsyncSession) -> str:
    repo = SettingsRepo(session)
    current = await repo.get(_COUNTER_KEY, "0")
    next_n = int(current) + 1
    await repo.set(_COUNTER_KEY, str(next_n))
    return str(next_n)


async def send_forum_materials(bot: Bot, user_id: int, session: AsyncSession):
    user = await UserRepo(session).get(user_id)
    name = (user.name or "Гость").split()[0] if user else "Гость"
    ticket_no = await _next_ticket_no(session)

    try:
        cl_bytes = generate_checklist()
        await bot.send_document(
            chat_id=user_id,
            document=BufferedInputFile(cl_bytes, filename="5_pravil_dnya.png"),
            caption="🌿 *5 правил дня с барака*\n\nСохрани — пригодится до форума.",
            parse_mode="Markdown",
        )

        tk_bytes = generate_ticket(name, ticket_no)
        await bot.send_document(
            chat_id=user_id,
            document=BufferedInputFile(tk_bytes, filename="bilet_forum_27_06.png"),
            caption="🎟 *Твой билет на Форум IQ Barakah · 27 июня*\n\nПокажи на входе — и до встречи в Ресторане Шатёр!",
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("Failed to send forum materials to %s", user_id)
