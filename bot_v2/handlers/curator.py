"""Команды куратора: /activate, /deactivate, /participants, /setcalllink, /pair, /analyzestats."""
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
from bot_v2.services.i18n import language_name
from bot_v2.services.program import LEVEL_NAMES, LEVEL_WEEKS
from bot_v2.services.insights import analyze_participant
from bot_v2.api.analyze import get_stats

logger = logging.getLogger(__name__)
router = Router(name="curator")


def is_curator(user_id: int, config: Config) -> bool:
    return user_id in config.curator_ids


@router.message(Command("testjarwas"))
async def cmd_testjarwas(message: Message, config: Config):
    """Куратор: тестирует Jarwas API и показывает точную ошибку."""
    if not is_curator(message.from_user.id, config):
        return

    from bot_v2.services import jarwas as jarwas_svc

    await message.answer("🔄 Тестирую Jarwas API...")

    if not jarwas_svc._client:
        await message.answer(
            "❌ `_client = None`\n\n"
            "ANTHROPIC\\_API\\_KEY не задан или пустой.\n"
            f"Значение в config: `{'задан' if config.anthropic_api_key else 'ПУСТОЙ'}`\n"
            f"Длина ключа: {len(config.anthropic_api_key)} символов",
            parse_mode="Markdown",
        )
        return

    try:
        result = await jarwas_svc._client.messages.create(
            model=jarwas_svc.JARWAS_MODEL,
            max_tokens=50,
            messages=[{"role": "user", "content": "Скажи «Тест пройден» — одно предложение."}],
        )
        answer = result.content[0].text
        await message.answer(f"✅ Jarwas работает!\n\nОтвет: _{answer}_", parse_mode="Markdown")
    except Exception as e:
        await message.answer(
            f"❌ Ошибка API:\n\n"
            f"`{type(e).__name__}`\n\n"
            f"`{str(e)[:500]}`",
            parse_mode="Markdown",
        )


@router.message(Command("myid"))
async def cmd_myid(message: Message, config: Config):
    """Любой: /myid — показывает свой Telegram ID."""
    uid = message.from_user.id
    is_cur = is_curator(uid, config)
    await message.answer(
        f"👤 Твой Telegram ID: `{uid}`\n"
        f"{'✅ Ты куратор' if is_cur else '👤 Обычный пользователь'}",
        parse_mode="Markdown",
    )


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

        from bot_v2.services import jarwas as jarwas_svc
        jarwas_ok = jarwas_svc._client is not None

        checks = [
            "✅ База данных: подключена",
            f"✅ Пользователи: {users_count}",
            f"✅ Активные участники: {active_count}",
            f"✅ Диагностики: {diag_count}",
            f"✅ Платежи: {payment_count}",
            f"✅ Записи трекера: {tracker_count}",
            f"{'✅' if jarwas_ok else '❌'} Джарвас (AI): {'работает' if jarwas_ok else 'НЕ РАБОТАЕТ — нет ANTHROPIC_API_KEY'}",
            f"{'✅' if config.anthropic_api_key else '❌'} ANTHROPIC_API_KEY: {'задан' if config.anthropic_api_key else 'НЕ ЗАДАН'}",
            f"{'✅' if config.payments_provider_token else '⚠️'} PAYMENTS_TOKEN: {'задан' if config.payments_provider_token else 'не задан'}",
            f"{'✅' if config.yookassa_shop_id and config.yookassa_secret_key else '⚠️'} YooKassa: {'задана' if config.yookassa_shop_id and config.yookassa_secret_key else 'не задана'}",
            f"ℹ️ Твой ID: `{message.from_user.id}` | Кураторы: {config.curator_ids}",
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

    lang_rows = await session.execute(
        select(User.language_code, func.count(User.id))
        .group_by(User.language_code)
        .order_by(func.count(User.id).desc())
    )
    language_lines = [
        f"• {language_name(lang)} — {count}"
        for lang, count in lang_rows.all()
    ] or ["• пока нет данных"]

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
        + "\n\n*По языкам:*\n"
        + "\n".join(language_lines)
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
    participant = await p_repo.activate(target_id, level, week)

    # Автопарринг
    pair_repo = PairRepo(session)
    partner_id = await _auto_pair(target_id, pair_repo, p_repo)
    pair_status = "🤝 Якорный партнёр назначен" if partner_id else "⏳ Ждёт пары"

    await message.answer(
        f"✅ *Активировано*\n\n"
        f"👤 ID: `{target_id}`\n"
        f"📍 Уровень: *{level}* — {LEVEL_NAMES.get(level, '')}\n"
        f"📅 Шаг: *{week}*\n"
        f"{pair_status}",
        parse_mode="Markdown"
    )
    await _notify_activation(message.bot, target_id, participant, session, config)


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
        lines.append(f"• `{p.user_id}` — {name} | {LEVEL_NAMES.get(p.level, p.level)} | шаг {p.week}/{max_w}")
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
        f"👤 {user.name} · {participant.level} шаг {participant.week}\n"
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
    participant = await repo.activate(user_id, level, week=1)

    await call.answer("Активировано!")
    await call.message.edit_text(
        call.message.text + f"\n\n✅ Активирован на уровень {level}"
    )

    if tariff_id == "forum_27_06":
        from bot_v2.services.forum_materials import send_forum_materials
        await send_forum_materials(call.bot, user_id, session)
    else:
        await _notify_activation(call.bot, user_id, participant, session, config)


@router.message(Command("send_now"))
async def cmd_send_now(message: Message, session: AsyncSession, config: Config):
    """Куратор: /send_now <user_id> — отправить текущий урок участнику прямо сейчас."""
    if not is_curator(message.from_user.id, config):
        return
    args = message.text.split()[1:]
    if not args:
        await message.answer(
            "Использование: `/send_now <user_id>`\n\nПример: `/send_now 123456789`",
            parse_mode="Markdown",
        )
        return
    try:
        target_uid = int(args[0])
    except ValueError:
        await message.answer("❌ user_id должен быть числом.")
        return

    repo = ParticipantRepo(session)
    participant = await repo.get(target_uid)
    if not participant:
        await message.answer(f"❌ Участник {target_uid} не найден или не активен.")
        return

    from bot_v2.handlers.program import send_weekly_lesson
    try:
        await send_weekly_lesson(message.bot, target_uid, participant, session, config)
        await message.answer(
            f"✅ Урок отправлен участнику {target_uid}\n"
            f"Уровень {participant.level} · Шаг {participant.week}"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("send_all"))
async def cmd_send_all(message: Message, session: AsyncSession, config: Config):
    """Куратор: /send_all — разослать текущий урок ВСЕМ активным участникам."""
    if not is_curator(message.from_user.id, config):
        return
    from bot_v2.handlers.program import send_weekly_lesson
    from sqlalchemy import select as sa_select

    result = await session.execute(
        sa_select(Participant).where(Participant.is_active == True)
    )
    participants = result.scalars().all()

    await message.answer(f"📤 Начинаю рассылку уроков для {len(participants)} участников...")
    ok = 0
    fail = 0
    for p in participants:
        try:
            await send_weekly_lesson(message.bot, p.user_id, p, session, config)
            ok += 1
        except Exception as e:
            logger.warning("send_all → %s: %s", p.user_id, e)
            fail += 1

    await message.answer(
        f"✅ Готово!\n\nОтправлено: {ok}\nОшибок: {fail}"
    )


@router.message(Command("forum_fix_pending"))
async def cmd_forum_fix_pending(message: Message, session: AsyncSession, config: Config):
    """Куратор: /forum_fix_pending — поставить gift_pending всем форумщикам без активации."""
    if not is_curator(message.from_user.id, config):
        return

    from sqlalchemy import select as sa_select, or_
    from bot_v2.db.models import Payment, Participant
    from bot_v2.db.repositories import SettingsRepo

    _settings = SettingsRepo(session)
    result = await session.execute(
        sa_select(Payment).where(
            Payment.tariff_id == "forum_27_06",
            or_(Payment.status == "paid", Payment.status == "pending"),
        )
    )
    payments = result.scalars().all()

    fixed = 0
    for pay in payments:
        participant = await session.scalar(
            sa_select(Participant).where(Participant.user_id == pay.user_id)
        )
        if not participant or not participant.is_active:
            await _settings.set(f"gift_pending:{pay.user_id}", "1")
            fixed += 1

    await message.answer(
        f"✅ Флаг gift_pending поставлен {fixed} участникам.\n\n"
        f"Теперь когда они пройдут диагностику — Старт откроется автоматически."
    )


@router.message(Command("forum_start"))
async def cmd_forum_start(message: Message, session: AsyncSession, config: Config):
    """Куратор: /forum_start — разослать диагностику всем оплатившим форум 27 июня."""
    if not is_curator(message.from_user.id, config):
        return

    from sqlalchemy import select as sa_select
    from bot_v2.db.models import Payment
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    from sqlalchemy import or_
    result = await session.execute(
        sa_select(Payment).where(
            Payment.tariff_id == "forum_27_06",
            or_(Payment.status == "paid", Payment.status == "pending"),
        )
    )
    payments = result.scalars().all()
    # дедупликация по user_id
    seen = set()
    unique_payments = []
    for p in payments:
        if p.user_id not in seen:
            seen.add(p.user_id)
            unique_payments.append(p)
    payments = unique_payments

    if not payments:
        await message.answer("❌ Нет билетов на форум в базе.")
        return

    await message.answer(f"📤 Отправляю диагностику {len(payments)} участникам форума...")

    from bot_v2.db.repositories import SettingsRepo
    _settings = SettingsRepo(session)

    ok = 0
    fail = 0
    for pay in payments:
        try:
            # Ставим флаг — после диагностики активировать Старт автоматически
            await _settings.set(f"gift_pending:{pay.user_id}", "1")

            user = await UserRepo(session).get(pay.user_id)
            name = (user.name or "").split()[0] if user else ""
            greeting = f", {name}" if name else ""
            await message.bot.send_message(
                chat_id=pay.user_id,
                text=(
                    f"🌿 Ас-саляму алейкум{greeting}!\n\n"
                    f"Форум IQ Barakah начинается.\n\n"
                    f"Прежде чем открыть тебе *6 шагов IQ Barakah Старт* — "
                    f"пройди короткую диагностику потенциала.\n\n"
                    f"Это 7 вопросов · 2 минуты · определит твой уровень.\n\n"
                    f"По результату сразу откроется первый урок — именно для тебя. 🌱"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚢 Пройти диагностику", callback_data="korablik_start")],
                ])
            )
            ok += 1
        except Exception as e:
            logger.warning("forum_start → %s: %s", pay.user_id, e)
            fail += 1

    await message.answer(f"✅ Готово!\n\nОтправлено: {ok}\nОшибок: {fail}")


@router.message(Command("forum_ship"))
async def cmd_forum_ship(message: Message, session: AsyncSession, config: Config):
    """Куратор: /forum_ship — разослать участникам форума ссылку на Разбор корабля."""
    if not is_curator(message.from_user.id, config):
        return

    from sqlalchemy import select as sa_select, or_
    from bot_v2.db.models import Payment
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    result = await session.execute(
        sa_select(Payment).where(
            Payment.tariff_id == "forum_27_06",
            or_(Payment.status == "paid", Payment.status == "pending"),
        )
    )
    payments = result.scalars().all()
    seen = set()
    unique = []
    for p in payments:
        if p.user_id not in seen:
            seen.add(p.user_id)
            unique.append(p)

    if not unique:
        await message.answer("❌ Нет участников форума в базе.")
        return

    await message.answer(f"📤 Отправляю Разбор корабля {len(unique)} участникам...")

    ship_url = "https://iq-barakah.ru/ship-report.html?utm=forum2026"
    ok = 0
    fail = 0
    for pay in unique:
        try:
            user = await UserRepo(session).get(pay.user_id)
            name = (user.name or "").split()[0] if user else ""
            greeting = f", {name}" if name else ""
            await message.bot.send_message(
                chat_id=pay.user_id,
                text=(
                    f"🚢 Ас-саляму алейкум{greeting}!\n\n"
                    f"На форуме мы говорили о системе.\n\n"
                    f"Следующий шаг — *Разбор корабля*.\n\n"
                    f"Это 8 вопросов о твоей жизни и деле. По ответам AI выстраивает "
                    f"персональный разбор: где течь, где ресурс, куда двигаться.\n\n"
                    f"Занимает 5 минут. Результат — сразу. 🌿"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚢 Пройти Разбор корабля", url=ship_url)],
                ]),
            )
            ok += 1
        except Exception as e:
            logger.warning("forum_ship → %s: %s", pay.user_id, e)
            fail += 1

    await message.answer(f"✅ Готово!\n\nОтправлено: {ok}\nОшибок: {fail}")


@router.message(Command("forum_list"))
async def cmd_forum_list(message: Message, session: AsyncSession, config: Config):
    """Куратор: /forum_list — список всех купивших билет на форум."""
    if not is_curator(message.from_user.id, config):
        return

    from sqlalchemy import select as sa_select, or_
    from bot_v2.db.models import Payment

    result = await session.execute(
        sa_select(Payment).where(
            Payment.tariff_id == "forum_27_06",
            or_(Payment.status == "paid", Payment.status == "pending"),
        )
    )
    payments = result.scalars().all()

    seen = set()
    unique = []
    for p in payments:
        if p.user_id not in seen:
            seen.add(p.user_id)
            unique.append(p)

    if not unique:
        await message.answer("Билетов на форум пока нет.")
        return

    from bot_v2.db.models import DiagResult, Participant
    from sqlalchemy import select as _sel

    lines = [f"🎟 *Участники форума — {len(unique)} чел.*\n"]
    activated = 0
    diag_done = 0

    for i, p in enumerate(unique, 1):
        user = await UserRepo(session).get(p.user_id)
        name = user.name if user else "—"

        # Диагностика
        diag = await session.scalar(
            _sel(DiagResult).where(DiagResult.user_id == p.user_id)
            .order_by(DiagResult.created_at.desc()).limit(1)
        )
        if diag:
            diag_done += 1
            level_map = {"А": "Пробуждение", "Б": "Практика", "В": "Баракат"}
            diag_str = f"📊 {level_map.get(diag.level_key, diag.level_key)} {diag.pct}%"
        else:
            diag_str = "📊 —"

        # Активация
        participant = await session.scalar(
            _sel(Participant).where(Participant.user_id == p.user_id)
        )
        if participant and participant.is_active:
            activated += 1
            act_str = f"✅ Шаг {participant.week}"
        else:
            act_str = "⏳ не активирован"

        uname = f" @{_md_escape(user.username)}" if user and user.username else ""
        uid_str = f"`{p.user_id}`"
        safe_name = _md_escape(name)
        lines.append(f"{i}. *{safe_name}*{uname} {uid_str} · {diag_str} · {act_str}")

    summary = (
        f"\n📈 Диагностику прошли: {diag_done}/{len(unique)}\n"
        f"🟢 Активировано в программе: {activated}/{len(unique)}"
    )

    # Разбиваем на части по 15 участников
    header = lines[0]
    entries = lines[1:]
    chunk_size = 15
    for idx in range(0, len(entries), chunk_size):
        chunk = entries[idx:idx + chunk_size]
        text = header + "\n" + "\n".join(chunk)
        if idx + chunk_size >= len(entries):
            text += summary
        await message.answer(text, parse_mode="Markdown")


@router.message(Command("forum_reset_counter"))
async def cmd_forum_reset_counter(message: Message, session: AsyncSession, config: Config):
    """Куратор: /forum_reset_counter — сбросить счётчик билетов на 0."""
    if not is_curator(message.from_user.id, config):
        return
    from bot_v2.db.repositories import SettingsRepo
    await SettingsRepo(session).set("forum_27_06:ticket_counter", "0")
    await message.answer("✅ Счётчик билетов сброшен. Следующий билет будет № 1.")


@router.message(Command("forum_add"))
async def cmd_forum_add(message: Message, session: AsyncSession, config: Config):
    """/forum_add <user_id> — добавить тестовую запись билета форума."""
    if not is_curator(message.from_user.id, config):
        return
    args = message.text.split()[1:]
    if not args:
        await message.answer("Использование: `/forum_add <user_id>`", parse_mode="Markdown")
        return
    try:
        user_id = int(args[0])
    except ValueError:
        await message.answer("❌ user_id должен быть числом.")
        return

    from bot_v2.db.repositories import PaymentRepo
    await PaymentRepo(session).create(
        user_id=user_id,
        tariff_id="forum_27_06",
        amount=1500,
        yoo_payment_id=f"test_forum_{user_id}",
    )
    # Помечаем сразу как paid
    from bot_v2.db.models import Payment
    from sqlalchemy import select as sa_select
    pay = await session.scalar(
        sa_select(Payment).where(Payment.yoo_payment_id == f"test_forum_{user_id}")
    )
    if pay:
        pay.status = "paid"
        await session.flush()

    await message.answer(f"✅ Билет форума добавлен для `{user_id}`", parse_mode="Markdown")


@router.message(Command("gift"))
async def cmd_gift(message: Message, session: AsyncSession, config: Config):
    """/gift <user_id> — бесплатный доступ к IQ Barakah Старт."""
    if not is_curator(message.from_user.id, config):
        return
    args = message.text.split()[1:]
    if not args:
        await message.answer(
            "Использование: `/gift <user_id>`\n\n"
            "Или скинь ссылку: `t.me/iqbaraka_bot?start=gift`",
            parse_mode="Markdown",
        )
        return
    try:
        uid = int(args[0])
    except ValueError:
        await message.answer("❌ user_id должен быть числом.")
        return

    existing = await ParticipantRepo(session).get(uid)
    if existing:
        level_name = LEVEL_NAMES.get(existing.level, existing.level)
        await message.answer(
            f"⚠️ Пользователь `{uid}` уже активирован: {level_name}, шаг {existing.week}.",
            parse_mode="Markdown",
        )
        return

    user = await UserRepo(session).get(uid)
    if not user:
        await message.answer(f"❌ Пользователь `{uid}` не найден.", parse_mode="Markdown")
        return

    # Ставим флаг gift_pending — после Кораблика откроется урок
    from bot_v2.db.repositories import SettingsRepo
    await SettingsRepo(session).set(f"gift_pending:{uid}", "1")

    name = user.name or str(uid)
    await message.answer(
        f"✅ Бесплатный доступ выдан *{name}* (`{uid}`).\n\n"
        f"Отправляю им приглашение пройти диагностику — после неё откроется Шаг 1.",
        parse_mode="Markdown",
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    try:
        await message.bot.send_message(
            uid,
            "🌿 *Тебе открыт IQ Barakah Старт — 6 шагов тайм-менеджмента мусульманина.*\n\n"
            "Прежде чем начать — пройди короткую диагностику.\n"
            "7 вопросов · 2 минуты · определит твой уровень.\n\n"
            "По результату сразу откроется первый шаг. 🌱",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚢 Пройти диагностику", callback_data="korablik_start")],
            ]),
        )
    except Exception as e:
        logger.warning("gift cmd: send to %s failed: %s", uid, e)
        await message.answer(f"⚠️ Флаг поставлен, но сообщение не доставлено: {e}")


@router.message(Command("user_info"))
async def cmd_user_info(message: Message, session: AsyncSession, config: Config):
    """/user_info <user_id> — подробная информация об участнике."""
    if not is_curator(message.from_user.id, config):
        return
    args = message.text.split()[1:]
    if not args:
        await message.answer("Использование: `/user_info <user_id>`", parse_mode="Markdown")
        return
    try:
        uid = int(args[0])
    except ValueError:
        await message.answer("❌ user_id должен быть числом.")
        return

    from sqlalchemy import select as sa_select
    from bot_v2.db.models import Payment

    user = await UserRepo(session).get(uid)
    if not user:
        await message.answer(f"❌ Пользователь `{uid}` не найден в базе.", parse_mode="Markdown")
        return

    participant = await ParticipantRepo(session).get(uid)

    # Все платежи
    payments_result = await session.execute(
        sa_select(Payment).where(Payment.user_id == uid).order_by(Payment.created_at.desc())
    )
    payments = payments_result.scalars().all()

    # Строим ответ
    name = user.name or "—"
    username = f"@{user.username}" if user.username else "—"
    lang = user.language_code or "—"
    created = user.created_at.strftime("%d.%m.%Y %H:%M") if user.created_at else "—"

    lines = [
        f"👤 *{name}* (`{uid}`)",
        f"├ TG: {username}",
        f"├ Язык: {lang}",
        f"└ В боте с: {created}",
        "",
    ]

    if participant:
        level_name = LEVEL_NAMES.get(participant.level, participant.level)
        max_week = LEVEL_WEEKS.get(participant.level, 8)
        lines += [
            f"📊 *Прогресс:*",
            f"├ Уровень: {level_name}",
            f"├ Шаг: {participant.week}/{max_week}",
            f"└ Активирован: {participant.activated_at.strftime('%d.%m.%Y') if participant.activated_at else '—'}",
            "",
        ]
    else:
        lines += ["📊 *Прогресс:* не активирован\n"]

    if payments:
        lines.append("💳 *Платежи:*")
        for p in payments:
            date = p.created_at.strftime("%d.%m.%Y") if p.created_at else "—"
            status_icon = "✅" if p.status == "paid" else ("❌" if p.status == "canceled" else "⏳")
            from bot_v2.services.program import get_tariff
            tariff_info = get_tariff(p.tariff_id)
            tariff_label = tariff_info["name"] if tariff_info else p.tariff_id
            lines.append(f"{status_icon} {tariff_label} · {p.amount} ₽ · {date}")
    else:
        lines.append("💳 *Платежи:* нет")

    await message.answer("\n".join(lines), parse_mode="Markdown")


@router.message(Command("gift_code", "gift_codes"))
async def cmd_gift_code(message: Message, session: AsyncSession, config: Config):
    """/gift_code — создать одноразовый код. /gift_codes N — создать N кодов."""
    if not is_curator(message.from_user.id, config):
        return
    import secrets
    args = message.text.split()[1:]
    try:
        count = min(int(args[0]), 20) if args else 1
    except ValueError:
        count = 1

    repo = SettingsRepo(session)
    lines = []
    for _ in range(count):
        code = secrets.token_urlsafe(6).upper()[:6]
        await repo.set(f"gift_code:{code}", "unused")
        lines.append(f"`https://t.me/iqbaraka_bot?start=giftcode_{code}`")

    await message.answer(
        f"🎁 *{'Одноразовая ссылка' if count == 1 else f'{count} одноразовых ссылок'}:*\n\n" +
        "\n".join(lines) +
        "\n\n_Каждая ссылка работает один раз._",
        parse_mode="Markdown",
    )


@router.message(Command("gift_stats"))
async def cmd_gift_stats(message: Message, session: AsyncSession, config: Config):
    """/gift_stats — сколько мест использовано по gift-ссылке."""
    if not is_curator(message.from_user.id, config):
        return
    used = int(await SettingsRepo(session).get("gift:counter", "0"))
    limit = 50
    await message.answer(
        f"🎁 *Gift-доступ IQ Barakah Старт*\n\n"
        f"Использовано: *{used} / {limit}*\n"
        f"Осталось мест: *{limit - used}*\n\n"
        f"Сбросить счётчик: `/gift_reset`",
        parse_mode="Markdown",
    )


@router.message(Command("gift_reset"))
async def cmd_gift_reset(message: Message, session: AsyncSession, config: Config):
    """/gift_reset — сбросить счётчик gift-ссылки."""
    if not is_curator(message.from_user.id, config):
        return
    await SettingsRepo(session).set("gift:counter", "0")
    await message.answer("✅ Счётчик gift-ссылки сброшен. Снова доступно 50 мест.")


@router.message(Command("db_check"))
async def cmd_db_check(message: Message, session: AsyncSession, config: Config):
    """/db_check — временная диагностика схемы таблицы payments."""
    if not is_curator(message.from_user.id, config):
        return
    from sqlalchemy import text
    lines = []

    try:
        rows = await session.execute(text(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_name = 'payments' ORDER BY ordinal_position"
        ))
        cols = rows.fetchall()
        lines.append("*Колонки payments:*")
        for r in cols:
            lines.append(f"  `{r[0]}` {r[1]} {'NULL' if r[2]=='YES' else 'NOT NULL'}")
        if not cols:
            lines.append("  _(таблица не найдена или пустая)_")
    except Exception as e:
        lines.append(f"*Ошибка колонок:* `{e}`")

    try:
        rows2 = await session.execute(text(
            "SELECT constraint_name, constraint_type "
            "FROM information_schema.table_constraints "
            "WHERE table_name = 'payments'"
        ))
        lines.append("\n*Ограничения:*")
        for r in rows2:
            lines.append(f"  `{r[0]}` — {r[1]}")
    except Exception as e:
        lines.append(f"\n*Ошибка ограничений:* `{e}`")

    try:
        col_names = [r[0] for r in cols] if cols else []
        safe_cols = ", ".join(f'"{c}"' for c in col_names[:6]) if col_names else "1"
        rows3 = await session.execute(text(f"SELECT {safe_cols} FROM payments LIMIT 2"))
        lines.append("\n*Примеры строк (первые 6 колонок):*")
        for r in rows3:
            lines.append(f"  {list(r)}")
    except Exception as e:
        lines.append(f"\n*Ошибка примеров:* `{e}`")

    await message.answer("\n".join(lines) or "Нет данных", parse_mode="Markdown")


@router.message(Command("reset"))
async def cmd_reset(message: Message, session: AsyncSession, config: Config):
    """
    /reset          — полный сброс самого себя (только куратор)
    /reset <uid>    — полный сброс любого пользователя
    Сбрасывает: неделя → 1, удаляет WeekAck (разблокирует уроки), is_active → True
    """
    if not is_curator(message.from_user.id, config):
        return

    args = message.text.split()[1:]
    target_id = message.from_user.id
    if args:
        try:
            target_id = int(args[0])
        except ValueError:
            await message.answer("❌ Формат: `/reset` или `/reset <uid>`", parse_mode="Markdown")
            return

    from sqlalchemy import delete
    from bot_v2.db.models import WeekAck

    repo = ParticipantRepo(session)
    p = await repo.reset(target_id)
    if not p:
        await message.answer(
            f"❌ Участник `{target_id}` не найден в базе.\n"
            f"Твой ID: `{message.from_user.id}`",
            parse_mode="Markdown"
        )
        return

    # Удаляем WeekAck чтобы уроки разблокировались в Mini App
    await session.execute(
        delete(WeekAck).where(WeekAck.user_id == target_id)
    )

    level_name = LEVEL_NAMES.get(p.level, p.level)
    await message.answer(
        f"♻️ *Полный сброс выполнен*\n\n"
        f"👤 `{target_id}`\n"
        f"📍 Уровень: {level_name}\n"
        f"📅 Шаг → *1 из {LEVEL_WEEKS.get(p.level, 8)}*\n"
        f"🗑 WeekAck удалены — все уроки разблокированы\n\n"
        f"Отправить первый урок: `/send_now {target_id}`",
        parse_mode="Markdown",
    )


@router.message(Command("preview"))
async def cmd_preview(message: Message, session: AsyncSession, config: Config):
    """
    /preview <week>              — переставить себя на нужную неделю
    /preview <uid> <week>        — переставить любого участника
    Позволяет куратору и команде проверять любой урок.
    """
    if not is_curator(message.from_user.id, config):
        return

    args = message.text.split()[1:]
    if not args:
        await message.answer(
            "📺 *Режим предпросмотра*\n\n"
            "Использование:\n"
            "`/preview <шаг>` — переставить себя\n"
            "`/preview <uid> <шаг>` — переставить участника\n\n"
            "Например: `/preview 3` или `/preview 123456789 5`",
            parse_mode="Markdown",
        )
        return

    try:
        if len(args) == 1:
            target_id = message.from_user.id
            week = int(args[0])
        else:
            target_id = int(args[0])
            week = int(args[1])
    except ValueError:
        await message.answer("❌ Формат: `/preview <шаг>` или `/preview <uid> <шаг>`", parse_mode="Markdown")
        return

    if week < 1:
        await message.answer("❌ Шаг должен быть ≥ 1")
        return

    repo = ParticipantRepo(session)
    p = await repo.set_week(target_id, week)
    if not p:
        await message.answer(f"❌ Участник `{target_id}` не найден.", parse_mode="Markdown")
        return

    max_w = LEVEL_WEEKS.get(p.level, 8)
    await message.answer(
        f"📺 *Предпросмотр установлен*\n\n"
        f"👤 `{target_id}` → шаг *{week}* из {max_w}\n"
        f"📍 {LEVEL_NAMES.get(p.level, p.level)}\n\n"
        "Открой Мини Апп или нажми «Открыть карту пути» — увидишь нужный урок.\n"
        "Чтобы получить урок текстом: `/send_now {target_id}`",
        parse_mode="Markdown",
    )


@router.message(Command("tester"))
async def cmd_tester(message: Message, session: AsyncSession, config: Config):
    """
    /tester <uid> [level]   — активировать тестера со всеми уроками открытыми
    Ставит уровень А (или указанный), неделя 1, vakt_level = I.
    Используй /preview после, чтобы перейти на нужную неделю.
    """
    if not is_curator(message.from_user.id, config):
        return

    args = message.text.split()[1:]
    if not args:
        await message.answer(
            "🧪 *Режим тестера*\n\n"
            "Использование: `/tester <uid> [уровень]`\n"
            "Уровни: А, Б, В, Г (по умолчанию А)\n\n"
            "Пример: `/tester 123456789 Б`\n\n"
            "После активации используй `/preview <uid> <шаг>` для перехода на нужный шаг.",
            parse_mode="Markdown",
        )
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await message.answer("❌ Неверный user_id.")
        return

    level = args[1].upper() if len(args) > 1 else "А"
    if level not in LEVEL_WEEKS:
        await message.answer(f"❌ Неверный уровень `{level}`. Допустимые: А, Б, В, Г", parse_mode="Markdown")
        return

    repo = ParticipantRepo(session)
    # Проверяем что пользователь существует
    user = await UserRepo(session).get(target_id)
    if not user:
        await message.answer(
            f"❌ Пользователь `{target_id}` не найден в базе.\n"
            "Он должен хотя бы раз написать боту /start",
            parse_mode="Markdown"
        )
        return

    p = await repo.activate(target_id, level=level, week=1, vakt_level="I")
    max_w = LEVEL_WEEKS.get(level, 8)
    await message.answer(
        f"🧪 *Тестер активирован*\n\n"
        f"👤 `{target_id}` — {user.name}\n"
        f"📍 {LEVEL_NAMES.get(level, level)} | Уровень навыка: I\n"
        f"📅 Шаг 1 из {max_w}\n\n"
        "Используй `/preview` для перехода на нужную неделю.\n"
        "Сбросить обратно: `/reset`",
        parse_mode="Markdown",
    )


async def _notify_activation(bot, user_id: int, participant: Participant, session: AsyncSession, config: Config):
    user = await UserRepo(session).get(user_id)
    is_female = user.is_female if user else False
    default_name = "сестра" if is_female else "брат"
    name = _md_escape(user.name) if user else default_name
    activated = "активирована" if is_female else "активирован"
    level_name = LEVEL_NAMES.get(participant.level, participant.level)
    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                f"🌿 *Бисмиллях, {name}!*\n\n"
                f"Ты {activated} в программе *IQ Barakah*.\n\n"
                f"📍 Маршрут: *{level_name}*\n"
                f"📅 Старт: шаг *{participant.week}* из *{LEVEL_WEEKS.get(participant.level, 8)}*\n\n"
                "Ниже отправляю первый урок и ссылку на личный кабинет."
            ),
            parse_mode="Markdown",
        )
        from bot_v2.handlers.program import send_weekly_lesson

        await send_weekly_lesson(bot, user_id, participant, session, config)
    except Exception:
        logger.exception("Failed to notify activated participant %s", user_id)



def _md_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")


@router.message(Command("addcurator"))
async def cmd_addcurator(message: Message, session: AsyncSession, config: Config):
    """/addcurator <telegram_id> — добавить куратора"""
    if not is_curator(message.from_user.id, config):
        return
    args = message.text.split()[1:]
    if not args or not args[0].lstrip("-").isdigit():
        await message.answer("Использование: `/addcurator <telegram_id>`", parse_mode="Markdown")
        return
    new_id = int(args[0])
    if new_id in config.curator_ids:
        await message.answer(f"✅ `{new_id}` уже куратор.", parse_mode="Markdown")
        return
    config.curator_ids.append(new_id)
    # Сохраняем в БД для постоянства
    repo = SettingsRepo(session)
    existing = await repo.get("extra_curators", "")
    ids = [i for i in existing.split(",") if i] if existing else []
    ids.append(str(new_id))
    await repo.set("extra_curators", ",".join(ids))
    await message.answer(f"✅ `{new_id}` добавлен как куратор.\n\nТеперь он может использовать все команды бота.", parse_mode="Markdown")


@router.message(Command("removecurator"))
async def cmd_removecurator(message: Message, session: AsyncSession, config: Config):
    """/removecurator <telegram_id> — убрать куратора"""
    if not is_curator(message.from_user.id, config):
        return
    args = message.text.split()[1:]
    if not args or not args[0].lstrip("-").isdigit():
        await message.answer("Использование: `/removecurator <telegram_id>`", parse_mode="Markdown")
        return
    rem_id = int(args[0])
    if rem_id not in config.curator_ids:
        await message.answer(f"❌ `{rem_id}` не является куратором.", parse_mode="Markdown")
        return
    config.curator_ids.remove(rem_id)
    repo = SettingsRepo(session)
    existing = await repo.get("extra_curators", "")
    ids = [i for i in existing.split(",") if i and int(i) != rem_id]
    await repo.set("extra_curators", ",".join(ids))
    await message.answer(f"✅ `{rem_id}` удалён из кураторов.", parse_mode="Markdown")


@router.message(Command("curators"))
async def cmd_curators(message: Message, session: AsyncSession, config: Config):
    """/curators — список всех кураторов"""
    if not is_curator(message.from_user.id, config):
        return
    lines = [f"`{uid}`" for uid in config.curator_ids]
    await message.answer(f"👥 *Кураторы:*\n" + "\n".join(lines), parse_mode="Markdown")


@router.message(Command("preview_all"))
async def cmd_preview_all(message: Message, session: AsyncSession, config: Config):
    """/preview_all <уровень> — прислать все уроки уровня сразу (для куратора)
    Пример: /preview_all А  или  /preview_all Б"""
    if not is_curator(message.from_user.id, config):
        return

    args = message.text.split()[1:]
    level = args[0].upper() if args else "А"

    # Нормализация: a→А, b→Б и т.д.
    latin_map = {"A": "А", "B": "Б", "C": "В", "D": "Г"}
    level = latin_map.get(level, level)

    if level not in LEVEL_WEEKS:
        await message.answer(
            f"❌ Неизвестный уровень. Доступные: А, Б, В, Г\n\nПример: `/preview_all А`",
            parse_mode="Markdown"
        )
        return

    max_weeks = LEVEL_WEEKS[level]
    await message.answer(
        f"📚 Отправляю все {max_weeks} уроков уровня *{level}* ({LEVEL_NAMES.get(level, level)})...\n\n"
        f"Подожди — это займёт несколько секунд.",
        parse_mode="Markdown"
    )

    from bot_v2.db.repositories import ParticipantRepo
    from bot_v2.handlers.program import send_weekly_lesson
    import asyncio as _asyncio

    p_repo = ParticipantRepo(session)
    uid = message.from_user.id

    for week in range(1, max_weeks + 1):
        # Ставим нужную неделю
        participant = await p_repo.activate(uid, level=level, week=week)
        await session.flush()
        try:
            await message.answer(f"━━━━━━━━━━━━━━━\n📅 *Шаг {week} из {max_weeks}*", parse_mode="Markdown")
            await send_weekly_lesson(message.bot, uid, participant, session, config)
        except Exception as e:
            await message.answer(f"⚠️ Шаг {week}: {e}")
        await _asyncio.sleep(0.5)

    await message.answer(
        f"✅ Все {max_weeks} уроков уровня *{level}* отправлены!\n\n"
        f"Чтобы сбросить: `/resetme`",
        parse_mode="Markdown"
    )


@router.message(Command("analyzestats"))
async def cmd_analyzestats(message: Message, config: Config):
    """Куратор: статистика запросов /analyze (Джарвас)."""
    if not is_curator(message.from_user.id, config):
        return
    await message.answer(get_stats(), parse_mode="Markdown")


@router.message(Command("shipreport"))
async def cmd_shipreport(message: Message, session: AsyncSession, config: Config):
    """/shipreport <user_id> [pro] — сгенерировать ссылку на ship-report для участника."""
    if not is_curator(message.from_user.id, config):
        return
    args = message.text.split()[1:]
    if not args:
        await message.answer(
            "Использование: `/shipreport <user_id> [pro]`\n\n"
            "Пример: `/shipreport 123456789`\n"
            "Для платной версии: `/shipreport 123456789 pro`",
            parse_mode="Markdown"
        )
        return
    try:
        user_id = int(args[0])
    except ValueError:
        await message.answer("❌ user_id должен быть числом.")
        return

    is_pro = len(args) > 1 and args[1].lower() == "pro"

    user = await UserRepo(session).get_by_id(user_id)
    if not user:
        await message.answer(f"❌ Пользователь {user_id} не найден.")
        return

    # Берём последний диагностический результат (корабль жизни или бизнес)
    from sqlalchemy import select as sa_select, desc
    diag = await session.scalar(
        sa_select(DiagResult)
        .where(DiagResult.user_id == user_id)
        .order_by(desc(DiagResult.created_at))
        .limit(1)
    )

    name = user.first_name or ""
    base = "https://iq-barakah.ru/ship-report-pro.html" if is_pro else "https://iq-barakah.ru/ship-report.html"

    if diag and diag.scores and len(diag.scores) == 15:
        # Конвертируем индексы ответов в проценты (0→85, 1→65, 2→42, 3→18)
        score_map = {0: 85, 1: 65, 2: 42, 3: 18}
        pct_scores = [score_map.get(int(s), 52) for s in diag.scores]
        scores_str = ",".join(str(s) for s in pct_scores)
        url = f"{base}?tab=personal&name={name}&scores={scores_str}&utm=curator"
        await message.answer(
            f"{'🔑 Платная версия' if is_pro else '📊 Базовая версия'} для *{name}* (ID: {user_id})\n\n"
            f"Результат диагностики от {diag.created_at.strftime('%d.%m.%Y')}:\n"
            f"{url}",
            parse_mode="Markdown"
        )
    else:
        # Нет диагностики — даём ссылку без scores (пройдёт квиз)
        import urllib.parse
        url = f"{base}?name={urllib.parse.quote(name)}&utm=curator"
        await message.answer(
            f"⚠️ Диагностика для *{name}* не найдена — ссылка без результатов (откроется квиз):\n\n{url}",
            parse_mode="Markdown"
        )
