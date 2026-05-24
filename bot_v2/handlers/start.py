"""Хендлер /start и главное меню."""
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.db.models import DiagResult
from bot_v2.db.repositories import UserRepo
from bot_v2.keyboards import (
    BTN_CURATOR,
    BTN_DIAG,
    BTN_LANGUAGE,
    BTN_MUHASABA,
    BTN_PAYMENT,
    BTN_PROGRAM,
    BTN_REMINDERS,
    BTN_SITE,
    kb_bottom_menu,
    kb_language,
    kb_main_menu,
    kb_onboarding_gender,
    kb_onboarding_occupation,
    kb_onboarding_source,
    kb_start_diag,
    kb_tariffs,
)
from bot_v2.config import Config
from bot_v2.services.i18n import language_name, normalize_lang, t
from bot_v2.services.program import TARIFFS

router = Router(name="start")


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
    db_user, _ = await repo.get_or_create(
        user_id=user.id,
        name=user.full_name or user.first_name or "Участник",
        username=user.username,
        language_code=normalize_lang(user.language_code),
    )

    lang = db_user.language_code or normalize_lang(user.language_code)

    await message.answer(
        f"Меню обновлено · {config.version}",
        reply_markup=kb_bottom_menu(config.miniapp_url, lang),
        parse_mode=None,
    )

    if not _profile_complete(db_user):
        await state.set_state(OnboardingStates.fio)
        await message.answer(
            "🌿 *Ассаляму алейкум! Добро пожаловать в IQ Barakah.*\n\n"
            "Ты попал в программу, где мы соединяем исламскую практику, "
            "дисциплину, время, семью, работу и баракат в одну понятную систему.\n\n"
            "Сначала я задам несколько коротких вопросов, чтобы куратор понимал, "
            "кто ты и какой путь тебе лучше предложить.\n\n"
            "1/5. Напиши, пожалуйста, своё *ФИО*:",
            parse_mode="Markdown",
            reply_markup=kb_bottom_menu(config.miniapp_url, lang),
        )
        return

    greeting = t(lang, "start.greeting", name=_md_escape(db_user.name))
    await message.answer(
        greeting,
        parse_mode="Markdown",
        reply_markup=kb_bottom_menu(config.miniapp_url, lang),
    )

    latest_diag = await _latest_diag(session, db_user.id)
    if latest_diag:
        await _send_program_after_diag(message, lang, latest_diag)
    else:
        await _send_diag_prompt(message, config, lang)


@router.callback_query(F.data == "back_main")
async def cb_back_main(call: CallbackQuery, session: AsyncSession, config: Config):
    await call.answer()
    repo = UserRepo(session)
    user = await repo.get(call.from_user.id)
    lang = user.language_code if user else normalize_lang(call.from_user.language_code)
    await call.message.edit_reply_markup(
        reply_markup=kb_main_menu(config.miniapp_url, config.ship_url, lang)
    )


@router.message(OnboardingStates.fio)
async def onboarding_fio(message: Message, state: FSMContext, session: AsyncSession):
    fio = (message.text or "").strip()
    if len(fio.split()) < 2:
        await message.answer("Напиши, пожалуйста, имя и фамилию. Например: `Рашид Мамедов`", parse_mode="Markdown")
        return
    await UserRepo(session).update(message.from_user.id, name=fio)
    await state.set_state(OnboardingStates.gender)
    await message.answer("2/5. Укажи пол:", reply_markup=kb_onboarding_gender())


@router.message(OnboardingStates.gender)
async def onboarding_gender(message: Message, state: FSMContext, session: AsyncSession):
    text = message.text or ""
    if "муж" in text.lower() or "👨" in text:
        is_female = False
    elif "жен" in text.lower() or "👩" in text:
        is_female = True
    else:
        await message.answer("Выбери один вариант кнопкой ниже:", reply_markup=kb_onboarding_gender())
        return
    await UserRepo(session).update(message.from_user.id, is_female=is_female)
    await state.set_state(OnboardingStates.age)
    await message.answer("3/5. Сколько тебе лет? Напиши числом, например: `29`", parse_mode="Markdown")


@router.message(OnboardingStates.age)
async def onboarding_age(message: Message, state: FSMContext, session: AsyncSession):
    age = (message.text or "").strip()
    if not age.isdigit() or not 8 <= int(age) <= 100:
        await message.answer("Напиши возраст числом от 8 до 100. Например: `29`", parse_mode="Markdown")
        return
    await UserRepo(session).update(message.from_user.id, age=age)
    await state.set_state(OnboardingStates.occupation)
    await message.answer("4/5. Чем ты сейчас занимаешься?", reply_markup=kb_onboarding_occupation())


@router.message(OnboardingStates.occupation)
async def onboarding_occupation(message: Message, state: FSMContext, session: AsyncSession):
    value = _occupation_key(message.text or "")
    if not value:
        await message.answer("Выбери вариант кнопкой ниже:", reply_markup=kb_onboarding_occupation())
        return
    await UserRepo(session).update(message.from_user.id, occupation=value)
    await state.set_state(OnboardingStates.source)
    await message.answer("5/5. Откуда ты узнал об IQ Barakah?", reply_markup=kb_onboarding_source())


@router.message(OnboardingStates.source)
async def onboarding_source(message: Message, state: FSMContext, session: AsyncSession, config: Config):
    source = _source_key(message.text or "")
    if not source:
        await message.answer("Выбери вариант кнопкой ниже:", reply_markup=kb_onboarding_source())
        return
    await UserRepo(session).update(message.from_user.id, source=source)
    await state.clear()
    await message.answer(
        "✅ Анкета сохранена.\n\n"
        "Теперь лучше пройти короткую диагностику: она определит твой уровень "
        "и покажет, с какого маршрута начать — ВАКТ, Сезон 1 или более глубокая программа.",
        reply_markup=kb_bottom_menu(config.miniapp_url),
    )
    await _send_diag_prompt(message, config, "ru")


@router.message(Command("language"))
async def cmd_language(message: Message, session: AsyncSession):
    repo = UserRepo(session)
    user, _ = await repo.get_or_create(
        user_id=message.from_user.id,
        name=message.from_user.full_name or message.from_user.first_name or "Участник",
        username=message.from_user.username,
        language_code=normalize_lang(message.from_user.language_code),
    )
    await message.answer(t(user.language_code, "language.choose"), reply_markup=kb_language())


@router.message(F.text == BTN_LANGUAGE)
async def msg_language(message: Message, session: AsyncSession):
    await cmd_language(message, session)


@router.message(F.text == BTN_PAYMENT)
async def msg_payment(message: Message, session: AsyncSession):
    user = await UserRepo(session).get(message.from_user.id)
    lang = user.language_code if user else normalize_lang(message.from_user.language_code)
    await message.answer(t(lang, "tariffs.title"), parse_mode="Markdown", reply_markup=kb_tariffs(lang))


@router.message(F.text == BTN_DIAG)
async def msg_diag_button(message: Message):
    await message.answer("🎯 Нажми кнопку ниже, чтобы пройти диагностику:", reply_markup=kb_start_diag())


@router.message(F.text == BTN_PROGRAM)
async def msg_program(message: Message, session: AsyncSession, config: Config):
    user = await UserRepo(session).get(message.from_user.id)
    lang = user.language_code if user else normalize_lang(message.from_user.language_code)
    latest_diag = await _latest_diag(session, message.from_user.id)
    if not latest_diag:
        await _send_diag_prompt(message, config, lang)
        return
    await _send_program_after_diag(message, lang, latest_diag)


@router.message(F.text == BTN_REMINDERS)
async def msg_reminders(message: Message):
    await message.answer("🔔 Напоминания скоро будут здесь. Сейчас главный шаг — пройти диагностику и выбрать маршрут.")


@router.message(F.text == BTN_CURATOR)
async def msg_curator(message: Message):
    await message.answer("💬 Напиши куратору: https://t.me/iqbarakah")


@router.message(F.text == BTN_MUHASABA)
async def msg_muhasaba(message: Message):
    await message.answer("🌙 Мухасаба будет доступна в личном кабинете после старта программы.")


@router.message(F.text == BTN_SITE)
async def msg_site(message: Message, config: Config):
    await message.answer(f"🌐 Сайт IQ Barakah:\n{config.site}")


@router.callback_query(F.data == "language")
async def cb_language(call: CallbackQuery, session: AsyncSession):
    repo = UserRepo(session)
    user = await repo.get(call.from_user.id)
    lang = user.language_code if user else normalize_lang(call.from_user.language_code)
    await call.answer()
    await call.message.answer(t(lang, "language.choose"), reply_markup=kb_language())


@router.callback_query(F.data.startswith("lang:"))
async def cb_set_language(call: CallbackQuery, session: AsyncSession, config: Config):
    lang = normalize_lang(call.data.split(":", 1)[1])
    repo = UserRepo(session)
    user, _ = await repo.get_or_create(
        user_id=call.from_user.id,
        name=call.from_user.full_name or call.from_user.first_name or "Участник",
        username=call.from_user.username,
        language_code=lang,
    )
    await repo.update(user.id, language_code=lang)
    await call.answer(t(lang, "language.saved", language=language_name(lang)), show_alert=False)
    await call.message.answer(
        t(lang, "language.saved", language=language_name(lang)),
        reply_markup=kb_bottom_menu(config.miniapp_url, lang),
        parse_mode="Markdown",
    )


def _profile_complete(user) -> bool:
    return bool(user.name and user.is_female is not None and user.age and user.occupation and user.source)


async def _latest_diag(session: AsyncSession, user_id: int) -> DiagResult | None:
    result = await session.execute(
        select(DiagResult)
        .where(DiagResult.user_id == user_id)
        .order_by(desc(DiagResult.created_at), desc(DiagResult.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _send_diag_prompt(message: Message, config: Config, lang: str):
    await message.answer(
        "🎯 Чтобы подобрать правильный маршрут, пройди короткую диагностику.",
        reply_markup=kb_bottom_menu(config.miniapp_url, lang),
    )
    await message.answer("Нажми кнопку ниже:", reply_markup=kb_start_diag())


async def _send_program_after_diag(message: Message, lang: str, diag: DiagResult):
    recommended = _recommended_tariff(diag.level_key)
    text = (
        "📚 *Твой следующий шаг — программа IQ Barakah*\n\n"
        f"По диагностике: *уровень {diag.level_key}* · {diag.pct}%.\n"
        f"Рекомендованный маршрут: *{recommended['name']}*.\n\n"
        "Выбери программу ниже. Если сомневаешься — напиши куратору, он поможет подобрать путь."
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=kb_tariffs(lang))


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
    if "предприним" in text:
        return "entrepreneur"
    if "сотруд" in text or "наём" in text or "наем" in text:
        return "employee"
    if "студ" in text:
        return "student"
    if "самозан" in text or "фриланс" in text:
        return "freelance"
    if "другое" in text:
        return "other"
    return None


def _source_key(text: str) -> str | None:
    text = text.lower()
    if "соц" in text:
        return "social"
    if "интернет" in text:
        return "internet"
    if "telegram" in text or "телеграм" in text:
        return "telegram"
    if "знаком" in text:
        return "word_of_mouth"
    if "youtube" in text or "reels" in text:
        return "video"
    if "другое" in text:
        return "other"
    return None
