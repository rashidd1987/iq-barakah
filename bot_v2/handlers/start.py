"""Хендлер /start и главное меню."""
from aiogram import Router, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.db.models import DiagResult, Participant
from bot_v2.db.repositories import UserRepo
from bot_v2.keyboards import (
    BTN_CURATOR,
    BTN_DIAG,
    BTN_MUHASABA,
    BTN_PAYMENT,
    BTN_PROGRAM,
    BTN_REMINDERS,
    BTN_SITE,
    BTN_HELP,
    kb_bottom_menu,
    kb_main_menu,
    kb_onboarding_gender,
    kb_onboarding_occupation,
    kb_onboarding_source,
    kb_onboard_step1,
    kb_onboard_step2,
    kb_onboard_step3,
    kb_program_overview,
    kb_start_diag,
    kb_tariffs,
)
from bot_v2.config import Config
from bot_v2.services.i18n import normalize_lang, t
from bot_v2.services.program import TARIFFS

router = Router(name="start")

BOTTOM_TEXTS = {
    "diag": {BTN_DIAG, t("ru", "bottom.diag")},
    "program": {BTN_PROGRAM, t("ru", "bottom.program")},
    "payment": {BTN_PAYMENT, t("ru", "bottom.payment")},
    "reminders": {BTN_REMINDERS, t("ru", "bottom.reminders")},
    "curator": {BTN_CURATOR, t("ru", "bottom.curator")},
    "muhasaba": {BTN_MUHASABA, t("ru", "bottom.muhasaba")},
    "site": {BTN_SITE, t("ru", "bottom.site")},
    "jarwas": {t("ru", "bottom.jarwas")},
    "help": {BTN_HELP, t("ru", "bottom.help")},
    "channel": {t("ru", "bottom.channel"), "📢 Канал", "📢 Channel", "📢 القناة", "📢 Kanal"},
}


class OnboardingStates(StatesGroup):
    fio = State()
    gender = State()
    age = State()
    occupation = State()
    source = State()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, config: Config, state: FSMContext):
    await state.clear()
    user = message.from_user
    repo = UserRepo(session)
    db_user, created = await repo.get_or_create(
        user_id=user.id,
        name=user.full_name or user.first_name or "Участник",
        username=user.username,
        language_code=normalize_lang(user.language_code),
    )

    lang = db_user.language_code or normalize_lang(user.language_code)
    participant = await _get_participant(session, db_user.id)

    # Парсим deep link payload: /start quiz_a_22
    payload = ""
    parts = message.text.split() if message.text else []
    if len(parts) > 1:
        payload = parts[1]

    # PWA Telegram Login: /start pwa_<session_id>
    if payload.startswith("pwa_"):
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        session_id = payload[4:]
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Подтвердить вход в IQ Barakah", callback_data=f"pwa_confirm_{session_id}")
        ]])
        await message.answer(
            "🔐 Подтвердите вход в IQ Barakah PWA\n\nНажмите кнопку ниже — вы будете авторизованы на сайте.",
            reply_markup=kb
        )
        return

    # UTM deep link utm__<source>__<campaign>__...
    if payload.startswith("utm__"):
        db_user.last_utm_source = payload          # всегда обновляем
        if not db_user.utm_source:                 # первый источник не перезаписываем
            db_user.utm_source = payload
        await session.flush()

    # Реферальный deep link ref_<code>
    if payload.startswith("ref_") and created:
        ref_code = payload[4:]
        from sqlalchemy import select as _sa_sel
        from bot_v2.db.models import User as _User
        referrer = await session.scalar(
            _sa_sel(_User).where(_User.referral_code == ref_code)
        )
        if referrer and referrer.id != db_user.id:
            db_user.referred_by = referrer.id
            await session.flush()

    # Пришёл из НамазВдом (партнёрский deep link nmv_*)
    if payload.startswith("nmv_"):
        # Сохраняем источник в БД
        try:
            await UserRepo(session).update(db_user.id, source="namazdom")
        except Exception:
            pass

        name_first = (db_user.name or "").split()[0] or "друг"
        await message.answer(
            t(lang, "menu.updated", version=config.version),
            reply_markup=kb_bottom_menu(config.miniapp_url, lang, participant),
            parse_mode=None,
        )
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        greeting = (
            f"🌿 Ас-саляму алейкум, *{name_first}*!\n\n"
            f"Ты здесь потому что хочешь, чтобы намаз *менял жизнь* — "
            f"а не просто занимал место в расписании.\n\n"
            f"Я — *Джарвас*, AI-наставник IQ Barakah.\n\n"
            f"У нас есть 7-минутная диагностика — *Кораблик*.\n"
            f"Она покажет, какой из 7 отсеков твоей жизни "
            f"тянет всё остальное вниз.\n\n"
            f"Готов узнать? 🚢"
        )
        await message.answer(
            greeting,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚢 Пройти диагностику Кораблика", callback_data="korablik_start")],
                [InlineKeyboardButton(text="⏭ Сразу к программам", callback_data="show_tariffs")],
                [InlineKeyboardButton(text="❓ Как проходить программу", callback_data="show_howto")],
            ])
        )
        await message.answer(
            "📚 *Структура программы:*\n\n"
            "Каждый день в чат приходит новый урок → ты читаешь его → открываешь личный кабинет → "
            "проходишь задания и тест → следующий урок откроется автоматически 🔄",
            parse_mode="Markdown",
            reply_markup=kb_bottom_menu(config.miniapp_url, lang)
        )
        return

    # Пришёл с сайта после диагностики
    if payload.startswith("quiz_"):
        payload_parts = payload.split("_")

        # Форматы:
        #   новый: quiz_rashid_b_68  (имя + уровень + процент)
        #   anon:  quiz_anon_b_68    (без имени)
        #   старый: quiz_b_68        (обратная совместимость)
        if len(payload_parts) >= 4:
            site_name_raw = payload_parts[1]
            site_level = payload_parts[2]
            try:
                site_pct = int(payload_parts[3])
            except ValueError:
                site_pct = None
        else:
            site_name_raw = ""
            site_level = payload_parts[1] if len(payload_parts) > 1 else "a"
            try:
                site_pct = int(payload_parts[2]) if len(payload_parts) > 2 else None
            except ValueError:
                site_pct = None

        # Имя из квиза — приоритет над именем Telegram
        quiz_name = ""
        if site_name_raw and site_name_raw != "anon":
            quiz_name = site_name_raw.replace("_", " ").capitalize()
        name_first = quiz_name or (db_user.name or "").split()[0]

        # Если пришло имя с квиза — обновляем в БД
        if quiz_name:
            try:
                await UserRepo(session).update(db_user.id, name=quiz_name)
            except Exception:
                pass

        level_words = {"a": "Пробуждение", "b": "Пробуждение", "c": "Практика", "d": "Баракат"}
        level_label = level_words.get(site_level, "")

        pct_text = f"*{site_pct}% потенциала*" if site_pct else "твой потенциал"
        level_text = f" — уровень «{level_label}»" if level_label else ""

        await message.answer(
            t(lang, "menu.updated", version=config.version),
            reply_markup=kb_bottom_menu(config.miniapp_url, lang, participant),
            parse_mode=None,
        )

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        greeting = (
            f"🌿 Ас-саляму алейкум, *{name_first}*!\n\n"
            f"Я — *Джарвас*, AI-наставник IQ Barakah.\n\n"
            f"Ты только что прошёл диагностику на сайте.\n"
            f"Я вижу твой результат — {pct_text}{level_text}.\n"
            f"Это честная точка старта.\n\n"
            f"Я обещал тебе подарок — и готов его отдать.\n\n"
            f"Давай я задам несколько коротких вопросов — "
            f"не тест и не экзамен, просто хочу понять глубже.\n"
            f"А потом дам конкретную рекомендацию: с чего начать именно тебе. 🌱"
        )
        await message.answer(
            greeting,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Готов — задавай вопросы", callback_data="korablik_start")],
                [InlineKeyboardButton(text="⏭ Сразу к программам", callback_data="show_tariffs")],
            ])
        )
        return

    if payload.startswith("giftcode_"):
        from bot_v2.db.repositories import ParticipantRepo, SettingsRepo
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        code = payload[len("giftcode_"):]
        _settings = SettingsRepo(session)

        # Проверяем код
        code_status = await _settings.get(f"gift_code:{code}")
        if code_status is None:
            await message.answer("❌ Ссылка недействительна.")
            return
        if code_status == "used":
            await message.answer("❌ Эта ссылка уже была использована.")
            return

        # Проверяем — не активирован ли уже
        existing = await ParticipantRepo(session).get(message.from_user.id)
        if existing and existing.is_active:
            await message.answer(
                "🌱 У тебя уже открыт доступ к программе.\n\n"
                "Нажми *Мой путь* чтобы продолжить.",
                parse_mode="Markdown",
                reply_markup=kb_bottom_menu(config.miniapp_url, lang, existing),
            )
            return

        # Помечаем код как использованный
        await _settings.set(f"gift_code:{code}", "used")
        await _settings.set(f"gift_pending:{message.from_user.id}", "1")

        name_first = (db_user.name or "").split()[0] if db_user.name else ""
        greeting = f", {name_first}" if name_first else ""

        await message.answer(
            f"🌿 Ас-саляму алейкум{greeting}!\n\n"
            f"Тебе открыт *IQ Barakah Старт* — 6 шагов тайм-менеджмента мусульманина.\n\n"
            f"Прежде чем начать — пройди короткую диагностику.\n"
            f"7 вопросов · 2 минуты · определит твой уровень. 🌱",
            parse_mode="Markdown",
            reply_markup=kb_bottom_menu(config.miniapp_url, lang, None),
        )
        await message.answer(
            "👇 Нажми чтобы начать:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚢 Пройти диагностику", callback_data="korablik_start")],
            ]),
        )
        # Уведомляем куратора
        from bot_v2.keyboards.inline import kb_curator_contact
        _uname = db_user.username if db_user and db_user.username else None
        for curator_id in config.curator_ids:
            try:
                await message.bot.send_message(
                    curator_id,
                    f"🎁 *Gift-код активирован*\n\n"
                    f"👤 {db_user.name or '—'} (`{message.from_user.id}`)\n"
                    f"🔑 Код: `{code}`",
                    parse_mode="Markdown",
                    reply_markup=kb_curator_contact(message.from_user.id, _uname),
                )
            except Exception:
                pass
        return

    if payload.startswith("ol_"):
        # Ссылка для лидеров мнения — бесплатный доступ к Старту
        from bot_v2.db.repositories import ParticipantRepo, SettingsRepo
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        _settings = SettingsRepo(session)

        existing = await ParticipantRepo(session).get(message.from_user.id)
        if existing and existing.is_active:
            # Уже активирован — просто напомним реферальную ссылку
            from bot_v2.services.barakah import ensure_referral_code
            ref_code = await ensure_referral_code(session, db_user)
            await session.flush()
            await message.answer(
                "🌱 У тебя уже открыт доступ к программе.\n\nНажми *Мой путь* чтобы продолжить.",
                parse_mode="Markdown",
                reply_markup=kb_bottom_menu(config.miniapp_url, lang, existing),
            )
            await message.answer(
                f"🤝 *Твоя реферальная ссылка для аудитории:*\n\n"
                f"`https://t.me/iqbaraka_bot?start=ref_{ref_code}`\n\n"
                f"Делись ею — получишь 10% Баракатами с каждой оплаты твоих подписчиков.",
                parse_mode="Markdown",
            )
            return

        # Привязываем referred_by если в payload указан user_id лидера (ol_<uid>)
        ol_suffix = payload[3:]
        if ol_suffix.isdigit() and not db_user.referred_by:
            leader_id = int(ol_suffix)
            if leader_id != message.from_user.id:
                db_user.referred_by = leader_id
                await session.flush()

        # Генерируем реф. код заранее и сохраняем флаг — отправим ссылку после активации
        from bot_v2.services.barakah import ensure_referral_code
        ref_code = await ensure_referral_code(session, db_user)
        await _settings.set(f"gift_pending:{message.from_user.id}", "1")
        await _settings.set(f"partner_pending:{message.from_user.id}", ref_code)
        await session.flush()

        name_first = (db_user.name or "").split()[0] if db_user.name else ""
        greeting = f", {name_first}" if name_first else ""

        await message.answer(
            t(lang, "menu.updated", version=config.version),
            reply_markup=kb_bottom_menu(config.miniapp_url, lang, None),
            parse_mode=None,
        )
        await message.answer(
            f"🌿 Ас-саляму алейкум{greeting}!\n\n"
            f"Тебе открыт *IQ Barakah Старт* — 6 шагов тайм-менеджмента мусульманина.\n\n"
            f"Это не курс лекций. Это система, которая меняет день изнутри — через ният, фаджр и осознанность.\n\n"
            f"Прежде чем начать — пройди короткую диагностику.\n"
            f"7 вопросов · 2 минуты · определит твой уровень. 🌱",
            parse_mode="Markdown",
        )
        await message.answer(
            "👇 Нажми чтобы определить твой уровень:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚢 Пройти диагностику", callback_data="korablik_start")],
            ]),
        )

        # Уведомляем куратора
        from bot_v2.keyboards.inline import kb_curator_contact
        _uname = db_user.username if db_user and db_user.username else None
        for curator_id in config.curator_ids:
            try:
                await message.bot.send_message(
                    curator_id,
                    f"🌟 *Лидер мнения активировал партнёрскую ссылку*\n\n"
                    f"👤 {db_user.name or '—'} (`{message.from_user.id}`)\n"
                    f"🔗 Источник: `{payload}`\n"
                    f"🎯 Реф. код: `ref_{ref_code}`",
                    parse_mode="Markdown",
                    reply_markup=kb_curator_contact(message.from_user.id, _uname),
                )
            except Exception:
                pass
        return

    if payload == "gift":
        # Бесплатный доступ к IQ Barakah Старт — сначала диагностика, потом урок
        from bot_v2.db.repositories import ParticipantRepo, SettingsRepo
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        _settings = SettingsRepo(session)
        _GIFT_LIMIT = 50
        _GIFT_COUNTER_KEY = "gift:counter"

        existing = await ParticipantRepo(session).get(message.from_user.id)
        if existing and existing.is_active:
            await message.answer(
                "🌱 У тебя уже открыт доступ к программе.\n\n"
                "Нажми *Мой путь* чтобы продолжить.",
                parse_mode="Markdown",
                reply_markup=kb_bottom_menu(config.miniapp_url, lang, existing),
            )
            return

        # Проверяем лимит (не считаем тех кто уже имеет флаг gift_pending)
        already_pending = await _settings.get(f"gift_pending:{message.from_user.id}")
        if not already_pending:
            used = int(await _settings.get(_GIFT_COUNTER_KEY, "0"))
            if used >= _GIFT_LIMIT:
                await message.answer(
                    "🙏 К сожалению, все места по этой ссылке уже заняты.\n\n"
                    "Напиши куратору — @iqbarakah",
                )
                return
            await _settings.set(_GIFT_COUNTER_KEY, str(used + 1))

        # Ставим флаг — после Кораблика активировать бесплатно
        await _settings.set(f"gift_pending:{message.from_user.id}", "1")

        name_first = (db_user.name or "").split()[0] if db_user.name else ""
        greeting = f", {name_first}" if name_first else ""

        await message.answer(
            f"🌿 Ас-саляму алейкум{greeting}!\n\n"
            f"Тебе открыт *IQ Barakah Старт* — 6 шагов тайм-менеджмента мусульманина.\n\n"
            f"Прежде чем начать — пройди короткую диагностику потенциала.\n"
            f"7 вопросов · 2 минуты · определит твой уровень.\n\n"
            f"По результату сразу откроется первый шаг — именно для тебя. 🌱",
            parse_mode="Markdown",
            reply_markup=kb_bottom_menu(config.miniapp_url, lang, None),
        )
        await message.answer(
            "👇 Нажми чтобы начать:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚢 Пройти диагностику", callback_data="korablik_start")],
            ]),
        )
        return

    # Прямая ссылка на тариф: t.me/bot?start=tariff_s1_month
    if payload.startswith("tariff_"):
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from bot_v2.services.program import get_tariff, get_tariff_view
        tariff_id = payload[len("tariff_"):]
        tariff = get_tariff(tariff_id)
        if tariff:
            tariff_view = get_tariff_view(tariff_id, lang) or tariff
            await message.answer(
                t(lang, "menu.updated", version=config.version),
                reply_markup=kb_bottom_menu(config.miniapp_url, lang, participant),
                parse_mode=None,
            )
            price_str = f"{tariff['price']:,}".replace(",", " ")
            await message.answer(
                f"*{tariff_view['name']}*\n_{tariff_view['desc']}_\n\n💰 {price_str} ₽",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay:{tariff_id}")],
                    [InlineKeyboardButton(text="📋 Все тарифы", callback_data="show_tariffs")],
                ]),
            )
        else:
            await message.answer(
                t(lang, "menu.updated", version=config.version),
                reply_markup=kb_bottom_menu(config.miniapp_url, lang, participant),
                parse_mode=None,
            )
        return

    if payload == "forum2026":
        from bot_v2.db.repositories import ParticipantRepo, SettingsRepo
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from bot_v2.db.models import Payment as _Payment
        from sqlalchemy import select as _sa_select

        _settings = SettingsRepo(session)

        existing = await ParticipantRepo(session).get(message.from_user.id)
        if existing and existing.is_active:
            await message.answer(
                "🌱 У тебя уже открыт доступ к программе.\n\nНажми *Мой путь* чтобы продолжить.",
                parse_mode="Markdown",
                reply_markup=kb_bottom_menu(config.miniapp_url, lang, existing),
            )
            return


        # Ставим флаг — после диагностики активировать Старт бесплатно
        await _settings.set(f"gift_pending:{message.from_user.id}", "1")
        await _settings.set(f"forum2026:{message.from_user.id}", "1")

        # Сохраняем UTM-источник
        if not db_user.utm_source:
            db_user.utm_source = "forum2026"
        db_user.last_utm_source = "forum2026"
        await session.flush()

        name_first = (db_user.name or "").split()[0] if db_user.name else ""
        greeting = f", {name_first}" if name_first else ""

        await message.answer(
            f"🌿 Ас-саляму алейкум{greeting}!\n\n"
            f"*Твой подарок форума — IQ Barakah Старт*\n\n"
            f"6 шагов тайм-менеджмента мусульманина. Бесплатно — как мы и договорились. 🎁\n\n"
            f"Прежде чем открыть первый шаг — пройди короткую диагностику.\n"
            f"7 вопросов · 2 минуты · определит твой уровень. 🌱",
            parse_mode="Markdown",
            reply_markup=kb_bottom_menu(config.miniapp_url, lang, None),
        )
        await message.answer(
            "👇 Нажми чтобы начать:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚢 Пройти диагностику", callback_data="korablik_start")],
            ]),
        )
        # Уведомить куратора
        from bot_v2.keyboards.inline import kb_curator_contact
        _uname = db_user.username if db_user and db_user.username else None
        for curator_id in config.curator_ids:
            try:
                await message.bot.send_message(
                    curator_id,
                    f"🎟 *Участник форума зашёл в бот*\n\n"
                    f"👤 {db_user.name or '—'} (`{message.from_user.id}`)\n"
                    f"📌 Ожидает активации Старт (бесплатно)",
                    parse_mode="Markdown",
                    reply_markup=kb_curator_contact(message.from_user.id, _uname),
                )
            except Exception:
                pass
        return

    if payload == "forum":
        await message.answer(
            t(lang, "menu.updated", version=config.version),
            reply_markup=kb_bottom_menu(config.miniapp_url, lang, participant),
            parse_mode=None,
        )
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        name_first = (db_user.name or "").split()[0] if db_user.name else ""
        greeting_name = f", {name_first}" if name_first else ""
        forum_text = (
            f"🌿 Ас-саляму алейкум{greeting_name}!\n\n"
            f"*27 июня · Шатёр*\n\n"
            f"«Ты не потерял время. Ты потерял систему.»\n\n"
            f"Покажу всю архитектуру IQ Barakah — не мотивацию, а систему изменений.\n\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"*Билет 1 500 ₽:*\n"
            f"✅ Вход на форум\n"
            f"✅ Диагностика Бизнеса или Личной Жизни\n"
            f"✅ IQ Barakah Старт · 6 шагов (обычно отдельно)\n"
            f"✅ Обед в Шатёр после форума\n"
            f"✅ Подарки от партнёров\n\n"
            f"🎟 Места ограничены."
        )
        await message.answer(
            forum_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎟 Записаться — 1500₽", callback_data="tariff:forum_27_06")],
                [InlineKeyboardButton(text="🌐 Узнать об IQ Barakah", url="https://iq-barakah.ru")],
                [InlineKeyboardButton(text="💬 Есть вопрос", callback_data="contact_curator")],
            ])
        )
        return

    await message.answer(
        t(lang, "menu.updated", version=config.version),
        reply_markup=kb_bottom_menu(config.miniapp_url, lang, participant),
        parse_mode=None,
    )

    if not _profile_complete(db_user):
        # Новый пользователь — запускаем тёплый 3-шаговый онбординг
        await message.answer(
            t(lang, "onboard.step1"),
            reply_markup=kb_onboard_step1(lang),
            parse_mode="HTML",
        )
        return

    greeting = t(lang, "start.greeting", name=_md_escape(db_user.name))
    await message.answer(
        greeting,
        parse_mode="Markdown",
        reply_markup=kb_bottom_menu(config.miniapp_url, lang, participant),
    )

    latest_diag = await _latest_diag(session, db_user.id)
    if latest_diag:
        await _send_program_after_diag(message, lang, latest_diag)
    else:
        await _send_diag_prompt(message, config, lang)


@router.callback_query(F.data == "onboard_ready")
async def cb_onboard_ready(call: CallbackQuery, session: AsyncSession):
    """Шаг 2 — объяснение ниятa."""
    await call.answer()
    user = await UserRepo(session).get(call.from_user.id)
    lang = user.language_code if user else normalize_lang(call.from_user.language_code)
    # Убираем кнопку у шага 1, шаг 2 — новое сообщение
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.message.answer(
        t(lang, "onboard.step2"),
        reply_markup=kb_onboard_step2(lang),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "onboard_audit")
async def cb_onboard_audit(call: CallbackQuery, session: AsyncSession, config: Config):
    """Шаг 3 — Корабль Бараката / миниапп."""
    await call.answer()
    user = await UserRepo(session).get(call.from_user.id)
    lang = user.language_code if user else normalize_lang(call.from_user.language_code)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.message.answer(
        t(lang, "onboard.step3"),
        reply_markup=kb_onboard_step3(config.miniapp_url, lang),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "onboard_to_fio")
async def cb_onboard_to_fio(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Пропуск диагностики — сразу к регистрации (ФИО)."""
    await call.answer()
    user = await UserRepo(session).get(call.from_user.id)
    lang = user.language_code if user else normalize_lang(call.from_user.language_code)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await state.set_state(OnboardingStates.fio)
    await call.message.answer(
        t(lang, "onboard.to_fio"),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "back_main")
async def cb_back_main(call: CallbackQuery, session: AsyncSession, config: Config):
    await call.answer()
    repo = UserRepo(session)
    user = await repo.get(call.from_user.id)
    lang = user.language_code if user else normalize_lang(call.from_user.language_code)
    participant = await _get_participant(session, call.from_user.id)
    await call.message.edit_reply_markup(
        reply_markup=kb_main_menu(config.miniapp_url, config.ship_url, lang, participant)
    )


@router.message(OnboardingStates.fio)
async def onboarding_fio(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _message_lang(session, message)
    fio = (message.text or "").strip()
    if len(fio.split()) < 2:
        await message.answer(t(lang, "onboarding.fio_invalid"), parse_mode="Markdown")
        return
    await UserRepo(session).update(message.from_user.id, name=fio)
    await state.set_state(OnboardingStates.gender)
    await message.answer(t(lang, "onboarding.gender"), reply_markup=kb_onboarding_gender(lang))


@router.message(OnboardingStates.gender)
async def onboarding_gender(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _message_lang(session, message)
    text = message.text or ""
    if "👨" in text:
        is_female = False
    elif "👩" in text:
        is_female = True
    else:
        await message.answer(t(lang, "onboarding.gender_invalid"), reply_markup=kb_onboarding_gender(lang))
        return
    await UserRepo(session).update(message.from_user.id, is_female=is_female)
    await state.set_state(OnboardingStates.age)
    await message.answer(t(lang, "onboarding.age"), parse_mode="Markdown")


@router.message(OnboardingStates.age)
async def onboarding_age(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _message_lang(session, message)
    age = (message.text or "").strip()
    if not age.isdigit() or not 8 <= int(age) <= 100:
        await message.answer(t(lang, "onboarding.age_invalid"), parse_mode="Markdown")
        return
    await UserRepo(session).update(message.from_user.id, age=age)
    await state.set_state(OnboardingStates.occupation)
    await message.answer(t(lang, "onboarding.occupation"), reply_markup=kb_onboarding_occupation(lang))


@router.message(OnboardingStates.occupation)
async def onboarding_occupation(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _message_lang(session, message)
    value = _occupation_key(message.text or "")
    if not value:
        await message.answer(t(lang, "onboarding.occupation_invalid"), reply_markup=kb_onboarding_occupation(lang))
        return
    await UserRepo(session).update(message.from_user.id, occupation=value)
    await state.set_state(OnboardingStates.source)
    await message.answer(t(lang, "onboarding.source"), reply_markup=kb_onboarding_source(lang))


@router.message(OnboardingStates.source)
async def onboarding_source(message: Message, state: FSMContext, session: AsyncSession, config: Config):
    lang = await _message_lang(session, message)
    source = _source_key(message.text or "")
    if not source:
        await message.answer(t(lang, "onboarding.source_invalid"), reply_markup=kb_onboarding_source(lang))
        return
    await UserRepo(session).update(message.from_user.id, source=source)
    await state.clear()
    participant = await _get_participant(session, message.from_user.id)
    await message.answer(
        t(lang, "onboarding.saved"),
        reply_markup=kb_bottom_menu(config.miniapp_url, lang, participant),
    )
    # Приглашаем познакомиться с AI-наставником
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await message.answer(
        "🤖 *Познакомься с Джарвасом — твоим AI-наставником!*\n\n"
        "Он поможет выбрать программу, ответит на вопросы и поддержит на пути. 🌿",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🤖 Поговорить с AI-наставником", callback_data="jarwas_start")],
        ]),
    )
    await _send_diag_prompt(message, config, lang)


@router.message(StateFilter("*"), F.text.in_(BOTTOM_TEXTS["payment"]))
async def msg_payment(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    user = await UserRepo(session).get(message.from_user.id)
    lang = user.language_code if user else normalize_lang(message.from_user.language_code)
    await message.answer(t(lang, "tariffs.title"), parse_mode="Markdown", reply_markup=kb_tariffs(lang))


@router.message(StateFilter("*"), F.text.in_(BOTTOM_TEXTS["diag"]))
async def msg_diag_button(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    lang = await _message_lang(session, message)
    await message.answer(t(lang, "diag.prompt"), reply_markup=kb_start_diag(lang))


@router.message(StateFilter("*"), F.text.in_(BOTTOM_TEXTS["program"]))
async def msg_program(message: Message, state: FSMContext, session: AsyncSession, config: Config):
    """📖 Мой путь — прогресс и текущее состояние."""
    await state.clear()
    from bot_v2.db.repositories import ParticipantRepo, SettingsRepo
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    uid = message.from_user.id
    user = await UserRepo(session).get(uid)
    lang = user.language_code if user else normalize_lang(message.from_user.language_code)
    participant = await _get_participant(session, uid)

    # Стрик
    streak_val = await SettingsRepo(session).get(f"streak:{uid}", "0")
    try:
        streak = int(streak_val)
    except ValueError:
        streak = 0

    if not participant or not participant.is_active:
        await message.answer(
            "Ты ещё не начал программу.\n\n"
            "Давай начнём — пройди диагностику и первый урок придёт бесплатно.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Пройти диагностику", callback_data="korablik_start")],
                [InlineKeyboardButton(text="🎓 Посмотреть программы", callback_data="show_tariffs")],
            ])
        )
        return

    from bot_v2.services.program import LEVEL_NAMES, LEVEL_WEEKS
    level_name = LEVEL_NAMES.get(participant.level, participant.level)
    max_weeks = LEVEL_WEEKS.get(participant.level, 6)
    streak_fire = f"🔥 {streak} дней подряд" if streak > 0 else "Начни вечерний разбор сегодня"

    await message.answer(
        f"📖 *Твой путь*\n\n"
        f"📍 {level_name}\n"
        f"📅 Шаг *{participant.week}* из {max_weeks}\n"
        f"{streak_fire}\n\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"Что делать сегодня:\n"
        f"🌅 Утро с намерением\n"
        f"📚 Урок недели\n"
        f"🌙 Вечерний разбор\n\n"
        f"Нажми вечером чтобы подвести итог дня.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌙 Вечерний разбор", callback_data="start_evening")],
            [InlineKeyboardButton(text="📚 Получить урок", callback_data="week_lesson")],
        ])
    )


@router.message(StateFilter("*"), F.text.in_(BOTTOM_TEXTS["reminders"]))
async def msg_reminders(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    lang = await _message_lang(session, message)
    await message.answer(t(lang, "reminders.soon"))


@router.message(StateFilter("*"), F.text.in_(BOTTOM_TEXTS["curator"]))
async def msg_curator(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    lang = await _message_lang(session, message)
    await message.answer(t(lang, "curator.contact", url="https://t.me/iqbarakah"))


@router.message(StateFilter("*"), F.text.in_(BOTTOM_TEXTS["muhasaba"]))
@router.callback_query(F.data == "start_evening")
async def msg_muhasaba(update, state: FSMContext, session: AsyncSession):
    from aiogram.types import ReplyKeyboardRemove
    from bot_v2.handlers.muhasaba import INTRO, MUH_QUESTIONS, MuhasabaStates
    if isinstance(update, Message):
        await state.clear()
        await state.set_state(MuhasabaStates.q1)
        await state.update_data(answers=[])
        await update.answer(
            INTRO + MUH_QUESTIONS[0],
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await update.answer()
        from bot_v2.handlers.muhasaba import cb_start_muhasaba
        await cb_start_muhasaba(update, state)


@router.message(StateFilter("*"), F.text.in_(BOTTOM_TEXTS["site"]))
async def msg_site(message: Message, state: FSMContext, session: AsyncSession, config: Config):
    await state.clear()
    lang = await _message_lang(session, message)
    await message.answer(t(lang, "site.open", url=config.site))


@router.message(StateFilter("*"), F.text.in_(BOTTOM_TEXTS["jarwas"]))
async def msg_jarwas(message: Message, state: FSMContext, session: AsyncSession, config: Config):
    await state.clear()
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    lang = await _message_lang(session, message)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😔 Я сорвался", callback_data="j_relapse")],
        [InlineKeyboardButton(text="😴 Устал и нет сил", callback_data="j_tired")],
        [InlineKeyboardButton(text="❓ Вопрос по программе", callback_data="jarwas_start")],
        [InlineKeyboardButton(text="💬 Просто поговорить", callback_data="jarwas_start")],
    ])
    await message.answer(
        "Ас-саляму алейкум.\nЯ здесь.\n\nЧто происходит?",
        reply_markup=kb,
    )


@router.callback_query(F.data == "j_relapse")
async def cb_j_relapse(call: CallbackQuery):
    await call.answer()
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await call.message.answer(
        "Ты вернулся — это уже больше, чем у многих.\n\nСколько дней прошло?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1–2 дня", callback_data="rl_12"),
             InlineKeyboardButton(text="3–7 дней", callback_data="rl_37")],
            [InlineKeyboardButton(text="Больше недели", callback_data="rl_more")],
        ])
    )


@router.callback_query(F.data == "rl_12")
async def cb_rl_12(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "Это не срыв — это пауза.\n\n"
        "Сделай одно действие прямо сейчас:\n"
        "→ Открой вечерний разбор и ответь на три вопроса.\n\n"
        "Не наверстывай всё. Один шаг — и ты снова в ритме.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌙 Вечерний разбор", callback_data="start_evening")]
        ])
    )


@router.callback_query(F.data == "rl_37")
async def cb_rl_37(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "Пауза — это нормально.\n\n"
        "Система не ломается от паузы — она ждёт.\n\n"
        "Начнём не сначала, а оттуда где остановился.\n"
        "Сделай вечерний разбор сегодня — и завтра утро станет якорем.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌙 Вечерний разбор", callback_data="start_evening")]
        ])
    )


@router.callback_query(F.data == "rl_more")
async def cb_rl_more(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "Хорошо, что ты вернулся.\nНеважно сколько прошло — ты здесь.\n\n"
        "Один вопрос: что чаще всего выбивало из ритма?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Телефон", callback_data="miss_phone"),
             InlineKeyboardButton(text="😤 Работа/стресс", callback_data="miss_work")],
            [InlineKeyboardButton(text="🤷 Не знаю", callback_data="miss_dunno")],
        ])
    )


@router.callback_query(F.data.in_({"miss_phone", "miss_work", "miss_dunno"}))
async def cb_miss(call: CallbackQuery):
    await call.answer()
    tips = {
        "miss_phone": "Телефон — главный конкурент системы.\n\nОдно правило: первые 15 минут после пробуждения — без телефона. Только намерение и одно действие.",
        "miss_work":  "Стресс на работе — сигнал что система нужна именно тебе.\n\nОдно действие: один тихий момент для себя в середине дня.",
        "miss_dunno": "Иногда мы сами не знаем почему срываемся.\n\nОдин вечерний разбор сегодня — и картина прояснится.",
    }
    await call.message.answer(
        tips[call.data] + "\n\nНачнём с одного шага?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌙 Вечерний разбор", callback_data="start_evening")],
        ])
    )


@router.callback_query(F.data == "j_tired")
async def cb_j_tired(call: CallbackQuery):
    await call.answer()
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await call.message.answer(
        "Слышу тебя.\n\nЧто сейчас больше всего забирает энергию?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="😤 Работа / дела", callback_data="tired_work")],
            [InlineKeyboardButton(text="👨‍👩‍👧 Семья", callback_data="tired_family")],
            [InlineKeyboardButton(text="📱 Телефон / соцсети", callback_data="tired_phone")],
            [InlineKeyboardButton(text="🤷 Не знаю", callback_data="tired_dunno")],
        ])
    )


@router.callback_query(F.data.startswith("tired_"))
async def cb_tired(call: CallbackQuery):
    await call.answer()
    tips = {
        "tired_work":   "Работа забирает — значит нет восстановления.\n\nОдно действие: 5 минут тишины в середине дня — без телефона, без задач.",
        "tired_family": "Семья + усталость = ты рядом, но не здесь.\n\nОдно действие: 10 минут с близкими без телефона. Просто рядом.",
        "tired_phone":  "Телефон забирает энергию незаметно.\n\nОдно действие: убери телефон на час. Просто попробуй.",
        "tired_dunno":  "Иногда тело устало от хаоса в голове, не от дел.\n\nОдно действие: вечерний разбор сегодня. Три вопроса — и станет яснее.",
    }
    await call.message.answer(
        tips.get(call.data, "Слышу тебя. Один шаг — не план на неделю."),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌙 Вечерний разбор", callback_data="start_evening")],
        ])
    )


@router.message(StateFilter("*"), F.text.in_(BOTTOM_TEXTS["help"]))
async def msg_help_btn(message: Message, state: FSMContext, session: AsyncSession, config: Config):
    """🙋 Нужна помощь."""
    await state.clear()
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await message.answer(
        "Я здесь. Чем помочь?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❓ Вопрос по программе", callback_data="help_program")],
            [InlineKeyboardButton(text="💸 Вопрос по оплате", callback_data="help_pay")],
            [InlineKeyboardButton(text="🔧 Техническая проблема", callback_data="help_tech")],
        ])
    )


@router.callback_query(F.data.in_({"help_program", "help_pay", "help_tech"}))
async def cb_help_curator(call: CallbackQuery):
    await call.answer()
    await call.message.answer("Напиши куратору — ответим в течение часа:\n@iqbarakah")


@router.callback_query(F.data == "help_rashid")
async def cb_help_rashid(call: CallbackQuery):
    await call.answer()
    await call.message.answer("Напиши Рашиду лично:\n@rasid_iqbarakah")


@router.message(StateFilter("*"), F.text.in_(BOTTOM_TEXTS["channel"]))
async def msg_channel_btn(message: Message, state: FSMContext):
    """📢 Канал."""
    await state.clear()
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await message.answer(
        "📢 Канал IQ Barakah — статьи, новости и обновления программы:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Открыть канал @iqbaraka", url="https://t.me/iqbaraka")],
        ])
    )


# ── Вечерний самоотчёт FSM теперь полностью в muhasaba.py ──────────────────


@router.callback_query(F.data == "week_lesson")
async def cb_week_lesson(call: CallbackQuery, session: AsyncSession, config: Config):
    await call.answer()
    from bot_v2.handlers.program import send_weekly_lesson
    participant = await _get_participant(session, call.from_user.id)
    if not participant or not participant.is_active:
        await call.message.answer("Сначала нужно активировать программу. Нажми «Оплата».")
        return
    try:
        await send_weekly_lesson(call.bot, call.from_user.id, participant, session, config)
    except Exception:
        await call.message.answer("Не удалось загрузить урок. Попробуй позже.")


@router.message(Command("partner"))
async def cmd_partner(message: Message, session: AsyncSession, config: Config):
    """/partner — показать реферальную ссылку для аудитории."""
    from bot_v2.services.barakah import ensure_referral_code
    from bot_v2.db.repositories import SettingsRepo
    user = await UserRepo(session).get(message.from_user.id)
    if not user:
        await message.answer("Сначала напиши /start")
        return
    ref_code = await ensure_referral_code(session, user)
    await session.flush()

    ref_link = f"https://t.me/iqbaraka_bot?start=ref_{ref_code}"
    balance = user.barakah_balance or 0

    from bot_v2.db.models import User as _User
    from sqlalchemy import select as _sel, func as _func
    referrals_count = await session.scalar(
        _sel(_func.count()).where(_User.referred_by == user.id)
    )

    await message.answer(
        f"🤝 *Твоя партнёрская ссылка*\n\n"
        f"`{ref_link}`\n\n"
        f"Поделись с аудиторией — когда они оплатят программу, "
        f"ты получишь *10% Баракатами* автоматически.\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👥 Привлечено: *{referrals_count or 0}* чел.\n"
        f"💰 Баланс Баракатов: *{balance}*\n\n"
        f"_Баракатами можно оплатить следующий месяц программы._",
        parse_mode="Markdown",
    )


@router.message(Command("resetme"))
async def cmd_resetme(message: Message, session: AsyncSession, state: FSMContext, config: Config):
    """Полный сброс профиля для тестирования — только кураторам."""
    if message.from_user.id not in config.curator_ids:
        return
    from bot_v2.db.models import User, WeekAck
    from sqlalchemy import delete
    uid = message.from_user.id
    # Сбрасываем профиль (User.id = Telegram ID)
    await session.execute(
        update(User)
        .where(User.id == uid)
        .values(name=message.from_user.first_name or "Участник",
                is_female=None, age=None, occupation=None, source=None)
    )
    # Удаляем participant (прогресс)
    await session.execute(delete(Participant).where(Participant.user_id == uid))
    # Удаляем диагностики
    await session.execute(delete(DiagResult).where(DiagResult.user_id == uid))
    # Удаляем подтверждения недель
    await session.execute(delete(WeekAck).where(WeekAck.user_id == uid))
    # Чистим settings через репозиторий (стрик, офер, follow-up)
    from bot_v2.db.repositories import SettingsRepo
    _repo = SettingsRepo(session)
    for key in [f"streak:{uid}", f"korablik_offer:{uid}", f"followup_at:{uid}"]:
        try:
            await _repo.set(key, "")
        except Exception:
            pass
    await state.clear()
    await message.answer(
        "✅ Полный сброс выполнен:\n\n"
        "• Профиль — сброшен\n"
        "• Прогресс — удалён\n"
        "• Диагностики — удалены\n"
        "• Стрик — обнулён\n"
        "• Мухасаба — очищена\n"
        "• Follow-up и скидки — сброшены\n\n"
        "Напиши /start — увидишь экран нового пользователя."
    )


def _profile_complete(user) -> bool:
    return bool(user.name and user.is_female is not None and user.age and user.occupation and user.source)


@router.callback_query(F.data == "show_howto")
async def cb_show_howto(call: CallbackQuery, session: AsyncSession):
    lang = await _message_lang(session, call.message) if call.message else "ru"
    await call.answer()
    await _send_howto_instruction_with_photos(call.message, lang)


@router.message(Command("howto"))
async def cmd_howto(message: Message, session: AsyncSession):
    lang = await _message_lang(session, message)
    await _send_howto_instruction_with_photos(message, lang)


@router.message(lambda msg: "Как проходить" in msg.text or "How to" in msg.text or "كيفية" in msg.text or "Nasıl" in msg.text)
async def msg_howto(message: Message, session: AsyncSession):
    lang = await _message_lang(session, message)
    await _send_howto_instruction_with_photos(message, lang)


async def _send_howto_instruction_with_photos(message: Message, lang: str):
    """Отправляет 6 шагов инструкции со скриншотами."""
    steps = _get_howto_steps(lang)
    for step in steps:
        await message.answer(step["text"], parse_mode="Markdown")
        if step.get("photo_url"):
            try:
                await message.answer_photo(
                    photo=step["photo_url"],
                    caption=step.get("caption", ""),
                    parse_mode="Markdown" if step.get("caption") else None
                )
            except Exception:
                pass


def _get_howto_steps(lang: str) -> list[dict]:
    """Возвращает список 6 шагов инструкции с текстом и URL скриншотов."""
    base_url = "https://iq-barakah.ru/site/screenshots"

    steps_data = {
        "ru": [
            {
                "text": "*Шаг 1️⃣ Выбираешь и оплачиваешь тариф*\n\nВыбираешь программу (Старт, Сезон 1, и т.д.) → оплачиваешь → получаешь доступ\n\nНа скриншоте видно окно выбора тарифов в боте.",
                "photo_url": f"{base_url}/step1.jpg",
                "caption": "Шаг 1: Выбор тарифа"
            },
            {
                "text": "*Шаг 2️⃣ Урок приходит в этот чат*\n\nКаждый день в этом чате появляется новый урок с текстом, хадисом и заданиями. Читаешь здесь, в боте 📱",
                "photo_url": f"{base_url}/step2.jpg",
                "caption": "Шаг 2: Урок приходит в чат бота"
            },
            {
                "text": "*Шаг 3️⃣ Открываешь личный кабинет*\n\nПосле урока нажимаешь кнопку 🏠 *Открыть личный кабинет* (она внизу каждого урока). Откроется мини-апп (приложение внутри Telegram)",
                "photo_url": f"{base_url}/step3.jpg",
                "caption": "Шаг 3: Открытие личного кабинета"
            },
            {
                "text": "*Шаг 4️⃣ Выполняешь задания в приложении*\n\nВ мини-апп видишь задания на день:\n• Практики (утром, днём, вечером)\n• Эпик недели\n• Коран\n• Вечерний отчёт\n\nОтмечаешь галочкой ✅ что выполнил",
                "photo_url": f"{base_url}/step4.jpg",
                "caption": "Шаг 4: Задания в мини-приложении"
            },
            {
                "text": "*Шаг 5️⃣ Проходишь тест в приложении*\n\nПосле всех заданий появляется тест — 3 вопроса по теме урока 📝\n\nОтветь правильно → следующий урок откроется автоматически 🚀",
                "photo_url": f"{base_url}/step5.jpg",
                "caption": "Шаг 5: Прохождение теста"
            },
            {
                "text": "*Шаг 6️⃣ Новый урок приходит в чат*\n\nВернись в этот чат → там уже новый урок. И начинаешь всё сначала 🔄\n\n━━━━━━━━━━━━━━━━━\n*Главное:* урок → приложение → задания → тест → новый урок\n\nВопросы? Пиши /help или нажми 🙋 *Нужна помощь*",
                "photo_url": f"{base_url}/step6.jpg",
                "caption": "Шаг 6: Новый урок приходит в чат"
            },
        ],
        "en": [
            {
                "text": "*Step 1️⃣ Choose & pay for a plan*\n\nSelect a program (Start, Season 1, etc.) → pay → get access\n\nYou can see the tariff selection window in the bot on the screenshot.",
                "photo_url": f"{base_url}/step1.jpg",
                "caption": "Step 1: Choose a plan"
            },
            {
                "text": "*Step 2️⃣ Lesson arrives in chat*\n\nEach day you'll get a new lesson here with text, hadith, and tasks. Read it here in the bot 📱",
                "photo_url": f"{base_url}/step2.jpg",
                "caption": "Step 2: Lesson arrives in chat"
            },
            {
                "text": "*Step 3️⃣ Open your personal cabinet*\n\nAfter reading, tap 🏠 *Open personal cabinet* (bottom of each lesson). Your mini app will open (a small app inside Telegram)",
                "photo_url": f"{base_url}/step3.jpg",
                "caption": "Step 3: Open personal cabinet"
            },
            {
                "text": "*Step 4️⃣ Complete tasks in the app*\n\nYou'll see daily tasks:\n• Practices (morning, noon, evening)\n• Weekly epic\n• Quran\n• Evening reflection\n\nCheck ✅ each task you complete",
                "photo_url": f"{base_url}/step4.jpg",
                "caption": "Step 4: Tasks in the app"
            },
            {
                "text": "*Step 5️⃣ Take the test in the app*\n\nAfter all tasks, you'll get a test — 3 questions about the lesson 📝\n\nAnswer correctly → next lesson unlocks automatically 🚀",
                "photo_url": f"{base_url}/step5.jpg",
                "caption": "Step 5: Take the test"
            },
            {
                "text": "*Step 6️⃣ New lesson arrives in chat*\n\nCome back here → you'll see a new lesson. Start all over again 🔄\n\n━━━━━━━━━━━━━━━━━\n*The cycle:* lesson → app → tasks → test → new lesson\n\nQuestions? Type /help or tap 🙋 *Need help*",
                "photo_url": f"{base_url}/step6.jpg",
                "caption": "Step 6: New lesson arrives"
            },
        ],
        "ar": [
            {
                "text": "*الخطوة 1️⃣ اختر خطتك ودفع*\n\nاختر البرنامج (البداية، الموسم 1، إلخ) → ادفع → احصل على الدخول\n\nيمكنك رؤية نافذة اختيار الخطة في البوت على لقطة الشاشة.",
                "photo_url": f"{base_url}/step1.jpg",
                "caption": "الخطوة 1: اختر خطة"
            },
            {
                "text": "*الخطوة 2️⃣ يصل الدرس إلى الدردشة*\n\nكل يوم ستحصل على درس جديد هنا مع النص والحديث والمهام. اقرأه هنا في البوت 📱",
                "photo_url": f"{base_url}/step2.jpg",
                "caption": "الخطوة 2: الدرس يصل إلى الدردشة"
            },
            {
                "text": "*الخطوة 3️⃣ افتح مكتبك الشخصي*\n\nبعد القراءة، اضغط 🏠 *افتح مكتبك الشخصي* (أسفل كل درس). ستفتح لك تطبيق صغير (تطبيق داخل Telegram)",
                "photo_url": f"{base_url}/step3.jpg",
                "caption": "الخطوة 3: افتح المكتب الشخصي"
            },
            {
                "text": "*الخطوة 4️⃣ أكمل المهام في التطبيق*\n\nستشاهد مهام يومية:\n• الممارسات (صباح، ظهيرة، مساء)\n• الملحمة الأسبوعية\n• القرآن\n• التأمل المسائي\n\nضع علامة ✅ على كل مهمة تكملها",
                "photo_url": f"{base_url}/step4.jpg",
                "caption": "الخطوة 4: المهام في التطبيق"
            },
            {
                "text": "*الخطوة 5️⃣ خذ الاختبار في التطبيق*\n\nبعد جميع المهام، ستحصل على اختبار — 3 أسئلة عن الدرس 📝\n\nأجب بشكل صحيح → يفتح الدرس التالي تلقائياً 🚀",
                "photo_url": f"{base_url}/step5.jpg",
                "caption": "الخطوة 5: خذ الاختبار"
            },
            {
                "text": "*الخطوة 6️⃣ يصل درس جديد إلى الدردشة*\n\nعد هنا → ستجد درساً جديداً. ابدأ مرة أخرى 🔄\n\n━━━━━━━━━━━━━━━━━\n*الدورة:* درس → تطبيق → مهام → اختبار → درس جديد\n\nأسئلة؟ اكتب /help أو اضغط 🙋 *تحتاج مساعدة*",
                "photo_url": f"{base_url}/step6.jpg",
                "caption": "الخطوة 6: درس جديد يصل"
            },
        ],
        "tr": [
            {
                "text": "*Adım 1️⃣ Plan seç ve öde*\n\nBir program seç (Başlama, Sezon 1, vb.) → öde → erişim kazan\n\nBotta plan seçim penceresini ekran görüntüsünde görebilirsin.",
                "photo_url": f"{base_url}/step1.jpg",
                "caption": "Adım 1: Plan seç"
            },
            {
                "text": "*Adım 2️⃣ Ders sohbete ulaşır*\n\nHer gün burada metin, hadis ve görevler içeren yeni bir ders alacaksın. Burada botta oku 📱",
                "photo_url": f"{base_url}/step2.jpg",
                "caption": "Adım 2: Ders sohbete ulaşır"
            },
            {
                "text": "*Adım 3️⃣ Kişisel kabinetini aç*\n\nOkuduktan sonra 🏠 *Kişisel kabineti aç* tuşuna bas (her dersin altında). Mini uygulamanız açılacak (Telegram içinde küçük uygulama)",
                "photo_url": f"{base_url}/step3.jpg",
                "caption": "Adım 3: Kişisel kabineti aç"
            },
            {
                "text": "*Adım 4️⃣ Uygulamadaki görevleri tamamla*\n\nGünlük görevleri göreceksin:\n• Pratikler (sabah, öğle, akşam)\n• Haftalık epik\n• Kuran\n• Akşam yansıması\n\nTamamladığın her görevi ✅ işaretle",
                "photo_url": f"{base_url}/step4.jpg",
                "caption": "Adım 4: Uygulamadaki görevler"
            },
            {
                "text": "*Adım 5️⃣ Uygulamada testi al*\n\nTüm görevlerden sonra test alacaksın — ders hakkında 3 soru 📝\n\nDoğru cevapla → sonraki ders otomatik olarak açılır 🚀",
                "photo_url": f"{base_url}/step5.jpg",
                "caption": "Adım 5: Testi al"
            },
            {
                "text": "*Adım 6️⃣ Yeni ders sohbete ulaşır*\n\nBuraya geri dön → yeni bir ders göreceksin. Baştan başla 🔄\n\n━━━━━━━━━━━━━━━━━\n*Döngü:* ders → uygulama → görevler → test → yeni ders\n\nSorular? /help yaz ya da 🙋 *Yardım gerekli* tuşuna bas",
                "photo_url": f"{base_url}/step6.jpg",
                "caption": "Adım 6: Yeni ders ulaşır"
            },
        ],
    }

    return steps_data.get(lang, steps_data["ru"])


def _build_howto_instruction(lang: str) -> str:
    if lang not in ("ru", "en", "ar", "tr"):
        lang = "ru"

    instructions = {
        "ru": (
            "❓ *КАК ПРОХОДИТЬ ПРОГРАММУ*\n\n"
            "Вот пошагово, как работает система IQ Barakah:\n\n"
            "*Шаг 1️⃣ Оплата тариф*\n"
            "Выбираешь программу (Старт, Сезон 1, и т.д.) → оплачиваешь → получаешь доступ\n\n"
            "*Шаг 2️⃣ Урок приходит в чат*\n"
            "Каждый день в этом чате появляется новый урок с текстом, хадисом и заданиями\n"
            "Читаешь здесь, в боте 📱\n\n"
            "*Шаг 3️⃣ Открываешь личный кабинет*\n"
            "После урока нажимаешь кнопку 🏠 *Открыть личный кабинет* (она внизу каждого урока)\n"
            "Откроется мини-апп (приложение внутри Telegram)\n\n"
            "*Шаг 4️⃣ Выполняешь задания в приложении*\n"
            "В мини-апп видишь задания на день:\n"
            "• Практики (утром, днём, вечером)\n"
            "• Эпик недели\n"
            "• Коран\n"
            "• Вечерний отчёт\n\n"
            "Отмечаешь галочкой ✅ что выполнил\n\n"
            "*Шаг 5️⃣ Проходишь тест в приложении*\n"
            "После всех заданий появляется тест — 3 вопроса по теме урока 📝\n"
            "Ответишь правильно → следующий урок откроется автоматически 🚀\n\n"
            "*Шаг 6️⃣ Новый урок приходит в чат*\n"
            "Вернись в этот чат → там уже новый урок\n"
            "И начинаешь всё сначала 🔄\n\n"
            "━━━━━━━━━━━━━━━━━\n"
            "*Главное:* урок → приложение → задания → тест → новый урок\n\n"
            "Вопросы? Пиши /help или нажми 🙋 *Нужна помощь*"
        ),
        "en": (
            "❓ *HOW TO PROGRESS THROUGH THE PROGRAM*\n\n"
            "Here's how IQ Barakah works step by step:\n\n"
            "*Step 1️⃣ Choose & pay for a plan*\n"
            "Select a program (Start, Season 1, etc.) → pay → get access\n\n"
            "*Step 2️⃣ Lesson arrives in chat*\n"
            "Each day you'll get a new lesson here with text, hadith, and tasks\n"
            "Read it here in the bot 📱\n\n"
            "*Step 3️⃣ Open your personal cabinet*\n"
            "After reading, tap 🏠 *Open personal cabinet* (bottom of each lesson)\n"
            "Your mini app will open (a small app inside Telegram)\n\n"
            "*Step 4️⃣ Complete tasks in the app*\n"
            "You'll see daily tasks:\n"
            "• Practices (morning, noon, evening)\n"
            "• Weekly epic\n"
            "• Quran\n"
            "• Evening reflection\n\n"
            "Check ✅ each task you complete\n\n"
            "*Step 5️⃣ Take the test in the app*\n"
            "After all tasks, you'll get a test — 3 questions about the lesson 📝\n"
            "Answer correctly → next lesson unlocks automatically 🚀\n\n"
            "*Step 6️⃣ New lesson arrives in chat*\n"
            "Come back here → you'll see a new lesson\n"
            "Start all over again 🔄\n\n"
            "━━━━━━━━━━━━━━━━━\n"
            "*The cycle:* lesson → app → tasks → test → new lesson\n\n"
            "Questions? Type /help or tap 🙋 *Need help*"
        ),
        "ar": (
            "❓ *كيفية المتابعة في البرنامج*\n\n"
            "إليك كيف يعمل نظام IQ Barakah خطوة بخطوة:\n\n"
            "*الخطوة 1️⃣ اختر خطتك ودفع*\n"
            "اختر البرنامج (البداية، الموسم 1، إلخ) → ادفع → احصل على الدخول\n\n"
            "*الخطوة 2️⃣ يصل الدرس إلى الدردشة*\n"
            "كل يوم ستحصل على درس جديد هنا مع النص والحديث والمهام\n"
            "اقرأه هنا في البوت 📱\n\n"
            "*الخطوة 3️⃣ افتح مكتبك الشخصي*\n"
            "بعد القراءة، اضغط 🏠 *افتح مكتبك الشخصي* (أسفل كل درس)\n"
            "ستفتح لك تطبيق صغير (تطبيق داخل Telegram)\n\n"
            "*الخطوة 4️⃣ أكمل المهام في التطبيق*\n"
            "ستشاهد مهام يومية:\n"
            "• الممارسات (صباح، ظهيرة، مساء)\n"
            "• الملحمة الأسبوعية\n"
            "• القرآن\n"
            "• التأمل المسائي\n\n"
            "ضع علامة ✅ على كل مهمة تكملها\n\n"
            "*الخطوة 5️⃣ خذ الاختبار في التطبيق*\n"
            "بعد جميع المهام، ستحصل على اختبار — 3 أسئلة عن الدرس 📝\n"
            "أجب بشكل صحيح → يفتح الدرس التالي تلقائياً 🚀\n\n"
            "*الخطوة 6️⃣ يصل درس جديد إلى الدردشة*\n"
            "عد هنا → ستجد درساً جديداً\n"
            "ابدأ مرة أخرى 🔄\n\n"
            "━━━━━━━━━━━━━━━━━\n"
            "*الدورة:* درس → تطبيق → مهام → اختبار → درس جديد\n\n"
            "أسئلة؟ اكتب /help أو اضغط 🙋 *تحتاج مساعدة*"
        ),
        "tr": (
            "❓ *PROGRAMA NASIL DEVAM EDİLİR*\n\n"
            "IQ Barakah sistemi adım adım nasıl çalışır:\n\n"
            "*Adım 1️⃣ Plan seç ve öde*\n"
            "Bir program seç (Başlama, Sezon 1, vb.) → öde → erişim kazan\n\n"
            "*Adım 2️⃣ Ders sohbete ulaşır*\n"
            "Her gün burada metin, hadis ve görevler içeren yeni bir ders alacaksın\n"
            "Burada botta oku 📱\n\n"
            "*Adım 3️⃣ Kişisel kabinetini aç*\n"
            "Okuduktan sonra 🏠 *Kişisel kabineti aç* tuşuna bas (her dersin altında)\n"
            "Mini uygulamanız açılacak (Telegram içinde küçük uygulama)\n\n"
            "*Adım 4️⃣ Uygulamadaki görevleri tamamla*\n"
            "Günlük görevleri göreceksin:\n"
            "• Pratikler (sabah, öğle, akşam)\n"
            "• Haftalık epik\n"
            "• Kuran\n"
            "• Akşam yansıması\n\n"
            "Tamamladığın her görevi ✅ işaretle\n\n"
            "*Adım 5️⃣ Uygulamada testi al*\n"
            "Tüm görevlerden sonra test alacaksın — ders hakkında 3 soru 📝\n"
            "Doğru cevapla → sonraki ders otomatik olarak açılır 🚀\n\n"
            "*Adım 6️⃣ Yeni ders sohbete ulaşır*\n"
            "Buraya geri dön → yeni bir ders göreceksin\n"
            "Baştan başla 🔄\n\n"
            "━━━━━━━━━━━━━━━━━\n"
            "*Döngü:* ders → uygulama → görevler → test → yeni ders\n\n"
            "Sorular? /help yaz ya da 🙋 *Yardım gerekli* tuşuna bas"
        ),
    }

    return instructions.get(lang, instructions["ru"])


async def _get_participant(session: AsyncSession, user_id: int) -> Participant | None:
    from sqlalchemy import select
    result = await session.execute(select(Participant).where(Participant.user_id == user_id))
    return result.scalar_one_or_none()


async def _latest_diag(session: AsyncSession, user_id: int) -> DiagResult | None:
    result = await session.execute(
        select(DiagResult)
        .where(DiagResult.user_id == user_id)
        .order_by(desc(DiagResult.created_at), desc(DiagResult.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _message_lang(session: AsyncSession, message: Message) -> str:
    user = await UserRepo(session).get(message.from_user.id)
    return user.language_code if user else normalize_lang(message.from_user.language_code)


async def _send_diag_prompt(message: Message, config: Config, lang: str):
    await message.answer(
        t(lang, "diag.route_prompt"),
        reply_markup=kb_bottom_menu(config.miniapp_url, lang),  # no participant yet at diag stage
    )
    await message.answer(t(lang, "diag.prompt"), reply_markup=kb_start_diag(lang))


async def _send_program_after_diag(message: Message, lang: str, diag: DiagResult):
    await message.answer(
        _program_overview_text(lang, diag),
        parse_mode="Markdown",
        reply_markup=kb_program_overview(
            has_diag=True,
            recommended_tariff_id=_recommended_tariff(diag.level_key)["id"],
            lang=lang,
        ),
    )


async def _send_program_overview(message: Message, lang: str):
    await message.answer(
        _program_overview_text(lang),
        parse_mode="Markdown",
        reply_markup=kb_program_overview(has_diag=False, lang=lang),
    )


def _program_overview_text(lang: str, diag: DiagResult | None = None) -> str:
    texts = _program_texts()
    data = texts["ru"]
    diag_block = ""
    if diag:
        recommended = _program_tariff_name("ru", _recommended_tariff(diag.level_key)["id"])
        diag_block = data["diag"].format(level=diag.level_key, pct=diag.pct, recommended=recommended)
    return data["body"].format(diag_block=diag_block)


def _program_tariff_name(lang: str, tariff_id: str) -> str:
    names = {
        "vakt": "🌱 IQ Barakah Старт",
        "s1_full": "📗 IQ Barakah · Сезон 1",
        "s3_full": "🏆 IQ Barakah · 3 сезона",
        "jamaat": "👥 Поток",
        "leader": "👑 Лидер Уммы",
    }
    return names.get(tariff_id, TARIFFS[0]["name"])


def _program_texts() -> dict[str, dict[str, str]]:
    return {
        "ru": {
            "diag": (
                "🎯 *Твой результат:* уровень {level} · {pct}%\n"
                "🌿 *Рекомендуемый старт:* {recommended}\n\n"
                "━━━━━━━━━━━━━━━━\n"
            ),
            "body": (
                "📚 *Программа IQ Barakah*\n\n"
                "{diag_block}"
                "Курс для тех, кто устал бегать по кругу.\n\n"
                "Планируете, но всё равно нет результата и смысла?\n"
                "IQ Barakah помогает соединить:\n"
                "✅ Ваше сердце (покой, намерение)\n"
                "✅ Разум (фокус, ясность)\n"
                "✅ Поведение (привычки и дела)\n\n"
                "Курс поможет сделать так, чтобы работа, семья и духовная жизнь не мешали, а поддерживали друг друга.\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "🌱 *IQ Barakah Старт · Тайм-менеджмент мусульманина* · 6 шагов · 1 500 ₽\n\n"
                "B1 🌿 Ният (намерение) — тайный разговор\n"
                "B2 🏁 Фаджр — якорь дня\n"
                "B3 🕊 Тауба (покаяние) — чистый лист\n"
                "B4 💪 Сабр (терпение) — держи курс\n"
                "B5 📿 Зикр — Аллах в каждом деле\n"
                "B6 🏆 Итог — твоя система\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📗 *Сезон 1 · Основание · Кто ты есть* — 8 недель\n\n"
                "C1.1 🌿 Тайный разговор\n"
                "C1.2 🏠 Возвращение домой\n"
                "C1.3 ✨ Священное пространство\n"
                "C1.4 ⏱ Время как свидетель\n"
                "C1.5 📱 Кто твой Господь?\n"
                "C1.6 🖊 Нулевой километр\n"
                "C1.7 💪 Ты — не мозг в банке\n"
                "C1.8 🌿 Генеральная уборка души\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📘 *Сезон 2 · Строительство · Как ты живёшь* — 8 недель\n\n"
                "C2.1 🧠 Как шайтан взламывает мозг\n"
                "C2.2 🏛 Строительство крепости\n"
                "C2.3 🔥 Сжигание кораблей\n"
                "C2.4 ⚖️ Что тяжелее всего на весах?\n"
                "C2.5 🧳 Дай плату пока не высох пот\n"
                "C2.6 📖 Самый длинный аят\n"
                "C2.7 🤝 Партнёрство с Аллахом\n"
                "C2.8 🌍 Синдром Атланта\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📙 *Сезон 3 · Наследие · Зачем ты живёшь* — 8 недель\n\n"
                "C3.1 👣 У подножия их ног\n"
                "C3.2 🏠 Оставь войну за порогом\n"
                "C3.3 🧡 Зеркальные нейроны\n"
                "C3.4 🌹 Кузнец и парфюмер\n"
                "C3.5 👑 Король без короны\n"
                "C3.6 🏞 Река и болото\n"
                "C3.7 📊 Открытый счёт\n"
                "C3.8 🏛 Точка невозврата\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "Курс рассчитан на 30 недель. Каждый блок даёт конкретный результат и плавно ведёт на следующий уровень.\n\n"
                "🗓 *Понедельник 9:00* — урок недели в боте\n"
                "📞 *Пятница 14:00* — живой созвон с основателем IQ Barakah\n"
                "🌙 *Ежедневно* — азкар + мухасаба\n\n"
                "🌿 _20% с каждой оплаты → благотворительность_"
            ),
        },
    }


def _recommended_tariff(level_key: str) -> dict:
    tariff_id = "vakt"
    if level_key == "Б":
        tariff_id = "s1_full"
    elif level_key in {"В", "Г"}:
        tariff_id = "s3_full"
    return next((tariff for tariff in TARIFFS if tariff["id"] == tariff_id), TARIFFS[0])


def _md_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")


def _occupation_key(text: str) -> str | None:
    text = text.lower()
    if "💼" in text or "предприним" in text:
        return "entrepreneur"
    if "👔" in text or "сотруд" in text or "наём" in text or "наем" in text:
        return "employee"
    if "🎓" in text or "студ" in text:
        return "student"
    if "🧑‍💻" in text or "самозан" in text or "фриланс" in text:
        return "freelance"
    if "🏠" in text or "другое" in text:
        return "other"
    return None


def _source_key(text: str) -> str | None:
    text = text.lower()
    if "📱" in text or "соц" in text:
        return "social"
    if "🔍" in text or "интернет" in text:
        return "internet"
    if "telegram" in text or "телеграм" in text:
        return "telegram"
    if "👥" in text or "знаком" in text:
        return "word_of_mouth"
    if "youtube" in text or "reels" in text:
        return "video"
    if "📍" in text or "другое" in text:
        return "other"
    return None


# ── PWA Telegram Login ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pwa_confirm_"))
async def cb_pwa_confirm(call: CallbackQuery, config: Config):
    """Пользователь нажал «Подтвердить вход в PWA»."""
    await call.answer()
    session_id = call.data.removeprefix("pwa_confirm_")
    tg_user = call.from_user
    import aiohttp
    try:
        async with aiohttp.ClientSession() as http:
            resp = await http.post(
                f"{config.pwa_api_url}/auth/tg-confirm",
                json={
                    "session_id": session_id,
                    "tg_id": tg_user.id,
                    "tg_name": tg_user.full_name or tg_user.first_name or "Участник",
                    "secret": config.pwa_bot_secret,
                },
                timeout=aiohttp.ClientTimeout(total=10),
            )
            if resp.status == 200:
                await call.message.edit_text(
                    "✅ Вы вошли в IQ Barakah!\n\nВернитесь на сайт — страница автоматически откроется.",
                )
            else:
                await call.message.edit_text("❌ Ошибка подтверждения. Попробуйте снова.")
    except Exception as e:
        await call.message.edit_text(f"❌ Ошибка соединения: {e}")
