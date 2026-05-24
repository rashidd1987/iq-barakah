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
    kb_program_overview,
    kb_start_diag,
    kb_tariffs,
)
from bot_v2.config import Config
from bot_v2.services.i18n import language_name, normalize_lang, t
from bot_v2.services.i18n import SUPPORTED_LANGS
from bot_v2.services.program import TARIFFS

router = Router(name="start")

BOTTOM_TEXTS = {
    "diag": {BTN_DIAG, *(t(lang, "bottom.diag") for lang in SUPPORTED_LANGS)},
    "program": {BTN_PROGRAM, *(t(lang, "bottom.program") for lang in SUPPORTED_LANGS)},
    "payment": {BTN_PAYMENT, *(t(lang, "bottom.payment") for lang in SUPPORTED_LANGS)},
    "reminders": {BTN_REMINDERS, *(t(lang, "bottom.reminders") for lang in SUPPORTED_LANGS)},
    "curator": {BTN_CURATOR, *(t(lang, "bottom.curator") for lang in SUPPORTED_LANGS)},
    "muhasaba": {BTN_MUHASABA, *(t(lang, "bottom.muhasaba") for lang in SUPPORTED_LANGS)},
    "site": {BTN_SITE, *(t(lang, "bottom.site") for lang in SUPPORTED_LANGS)},
    "language": {BTN_LANGUAGE, *(t(lang, "bottom.language") for lang in SUPPORTED_LANGS)},
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
    db_user, _ = await repo.get_or_create(
        user_id=user.id,
        name=user.full_name or user.first_name or "Участник",
        username=user.username,
        language_code=normalize_lang(user.language_code),
    )

    lang = db_user.language_code or normalize_lang(user.language_code)

    await message.answer(
        t(lang, "menu.updated", version=config.version),
        reply_markup=kb_bottom_menu(config.miniapp_url, lang),
        parse_mode=None,
    )

    if not _profile_complete(db_user):
        await state.set_state(OnboardingStates.fio)
        await message.answer(
            t(lang, "onboarding.welcome"),
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
    await message.answer(
        t(lang, "onboarding.saved"),
        reply_markup=kb_bottom_menu(config.miniapp_url, lang),
    )
    await _send_diag_prompt(message, config, lang)


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


@router.message(F.text.in_(BOTTOM_TEXTS["language"]))
async def msg_language(message: Message, session: AsyncSession):
    await cmd_language(message, session)


@router.message(F.text.in_(BOTTOM_TEXTS["payment"]))
async def msg_payment(message: Message, session: AsyncSession):
    user = await UserRepo(session).get(message.from_user.id)
    lang = user.language_code if user else normalize_lang(message.from_user.language_code)
    await message.answer(t(lang, "tariffs.title"), parse_mode="Markdown", reply_markup=kb_tariffs(lang))


@router.message(F.text.in_(BOTTOM_TEXTS["diag"]))
async def msg_diag_button(message: Message, session: AsyncSession):
    lang = await _message_lang(session, message)
    await message.answer(t(lang, "diag.prompt"), reply_markup=kb_start_diag(lang))


@router.message(F.text.in_(BOTTOM_TEXTS["program"]))
async def msg_program(message: Message, session: AsyncSession, config: Config):
    user = await UserRepo(session).get(message.from_user.id)
    lang = user.language_code if user else normalize_lang(message.from_user.language_code)
    latest_diag = await _latest_diag(session, message.from_user.id)
    if not latest_diag:
        await _send_program_overview(message, lang)
        return
    await _send_program_after_diag(message, lang, latest_diag)


@router.message(F.text.in_(BOTTOM_TEXTS["reminders"]))
async def msg_reminders(message: Message, session: AsyncSession):
    lang = await _message_lang(session, message)
    await message.answer(t(lang, "reminders.soon"))


@router.message(F.text.in_(BOTTOM_TEXTS["curator"]))
async def msg_curator(message: Message, session: AsyncSession):
    lang = await _message_lang(session, message)
    await message.answer(t(lang, "curator.contact", url="https://t.me/iqbarakah"))


@router.message(F.text.in_(BOTTOM_TEXTS["muhasaba"]))
async def msg_muhasaba(message: Message, session: AsyncSession):
    lang = await _message_lang(session, message)
    await message.answer(t(lang, "muhasaba.locked"))


@router.message(F.text.in_(BOTTOM_TEXTS["site"]))
async def msg_site(message: Message, session: AsyncSession, config: Config):
    lang = await _message_lang(session, message)
    await message.answer(t(lang, "site.open", url=config.site))


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


async def _message_lang(session: AsyncSession, message: Message) -> str:
    user = await UserRepo(session).get(message.from_user.id)
    return user.language_code if user else normalize_lang(message.from_user.language_code)


async def _send_diag_prompt(message: Message, config: Config, lang: str):
    await message.answer(
        t(lang, "diag.route_prompt"),
        reply_markup=kb_bottom_menu(config.miniapp_url, lang),
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
    lang = normalize_lang(lang)
    texts = _program_texts()
    data = texts.get(lang, texts["en"])
    diag_block = ""
    if diag:
        recommended = _program_tariff_name(lang, _recommended_tariff(diag.level_key)["id"])
        diag_block = data["diag"].format(level=diag.level_key, pct=diag.pct, recommended=recommended)
    return data["body"].format(diag_block=diag_block)


def _program_tariff_name(lang: str, tariff_id: str) -> str:
    lang = normalize_lang(lang)
    names = {
        "ru": {
            "vakt": "🌱 ВАКТ",
            "s1_full": "📗 IQ Barakah · Сезон 1",
            "s3_full": "🏆 IQ Barakah · 3 сезона",
            "jamaat": "👥 Джамаат",
            "leader": "👑 Лидер Уммы",
        },
        "en": {
            "vakt": "🌱 VAKT",
            "s1_full": "📗 IQ Barakah · Season 1",
            "s3_full": "🏆 IQ Barakah · 3 seasons",
            "jamaat": "👥 Jamaat",
            "leader": "👑 Ummah Leader",
        },
        "ar": {
            "vakt": "🌱 VAKT",
            "s1_full": "📗 IQ Barakah · الموسم 1",
            "s3_full": "🏆 IQ Barakah · 3 مواسم",
            "jamaat": "👥 الجماعة",
            "leader": "👑 قائد الأمة",
        },
        "tr": {
            "vakt": "🌱 VAKT",
            "s1_full": "📗 IQ Barakah · Sezon 1",
            "s3_full": "🏆 IQ Barakah · 3 sezon",
            "jamaat": "👥 Cemaat",
            "leader": "👑 Ümmet Lideri",
        },
    }
    return names.get(lang, names["en"]).get(tariff_id, TARIFFS[0]["name"])


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
                "🌱 *ВАКТ · Тайм-менеджмент мусульманина* · 6 недель · 1 500 ₽\n\n"
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
        "en": {
            "diag": (
                "🎯 *Your result:* level {level} · {pct}%\n"
                "🌿 *Recommended start:* {recommended}\n\n"
                "━━━━━━━━━━━━━━━━\n"
            ),
            "body": (
                "📚 *IQ Barakah Program*\n\n"
                "{diag_block}"
                "A program for Muslims who are tired of running in circles.\n\n"
                "You plan, but still feel there is no result or meaning?\n"
                "IQ Barakah helps connect:\n"
                "✅ Heart: calm, intention, sincerity\n"
                "✅ Mind: focus and clarity\n"
                "✅ Behavior: habits and actions\n\n"
                "The goal is to make work, family and worship support each other instead of competing.\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "🌱 *VAKT · Muslim Time Management* · 6 weeks\n\n"
                "B1 🌿 Niyyah — the hidden conversation\n"
                "B2 🏁 Fajr — the anchor of the day\n"
                "B3 🕊 Tawbah — a clean page\n"
                "B4 💪 Sabr — stay the course\n"
                "B5 📿 Dhikr — Allah in every matter\n"
                "B6 🏆 Result — your system\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📗 *Season 1 · Foundation · Who you are* — 8 weeks\n\n"
                "C1.1 🌿 The hidden conversation\n"
                "C1.2 🏠 Coming home\n"
                "C1.3 ✨ Sacred space\n"
                "C1.4 ⏱ Time as witness\n"
                "C1.5 📱 Who is your Lord?\n"
                "C1.6 🖊 Kilometer zero\n"
                "C1.7 💪 You are not a brain in a jar\n"
                "C1.8 🌿 Deep cleaning of the soul\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📘 *Season 2 · Building · How you live* — 8 weeks\n\n"
                "C2.1 🧠 How shaytan hacks the brain\n"
                "C2.2 🏛 Building the fortress\n"
                "C2.3 🔥 Burning the ships\n"
                "C2.4 ⚖️ What is heaviest on the scales?\n"
                "C2.5 🧳 Pay before the sweat dries\n"
                "C2.6 📖 The longest ayah\n"
                "C2.7 🤝 Partnership with Allah\n"
                "C2.8 🌍 Atlas syndrome\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📙 *Season 3 · Legacy · Why you live* — 8 weeks\n\n"
                "C3.1 👣 Beneath their feet\n"
                "C3.2 🏠 Leave the war outside\n"
                "C3.3 🧡 Mirror neurons\n"
                "C3.4 🌹 The blacksmith and the perfumer\n"
                "C3.5 👑 King without a crown\n"
                "C3.6 🏞 River and swamp\n"
                "C3.7 📊 Open account\n"
                "C3.8 🏛 Point of no return\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "The full path is 30 weeks. Each block gives a concrete result and leads into the next level.\n\n"
                "🗓 *Monday 9:00* — weekly lesson in the bot\n"
                "📞 *Friday 14:00* — live call with the founder of IQ Barakah\n"
                "🌙 *Daily* — adhkar and muhasabah\n\n"
                "🌿 _20% from each payment goes to charity_"
            ),
        },
        "tr": {
            "diag": (
                "🎯 *Sonucun:* seviye {level} · {pct}%\n"
                "🌿 *Önerilen başlangıç:* {recommended}\n\n"
                "━━━━━━━━━━━━━━━━\n"
            ),
            "body": (
                "📚 *IQ Barakah Programı*\n\n"
                "{diag_block}"
                "Aynı döngünün içinde dönmekten yorulan Müslümanlar için bir program.\n\n"
                "Plan yapıyorsun ama yine de sonuç ve anlam eksik mi?\n"
                "IQ Barakah şunları birleştirmeye yardım eder:\n"
                "✅ Kalp: huzur, niyet, ihlas\n"
                "✅ Akıl: odak ve açıklık\n"
                "✅ Davranış: alışkanlıklar ve ameller\n\n"
                "Amaç; iş, aile ve ibadetin birbirine engel değil destek olmasıdır.\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "🌱 *VAKT · Müslüman için zaman yönetimi* · 6 hafta\n\n"
                "B1 🌿 Niyet — gizli konuşma\n"
                "B2 🏁 Fecr — günün çapası\n"
                "B3 🕊 Tevbe — temiz sayfa\n"
                "B4 💪 Sabır — istikameti koru\n"
                "B5 📿 Zikir — her işte Allah\n"
                "B6 🏆 Sonuç — senin sistemin\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📗 *Sezon 1 · Temel · Kimsin* — 8 hafta\n\n"
                "C1.1 🌿 Gizli konuşma\n"
                "C1.2 🏠 Eve dönüş\n"
                "C1.3 ✨ Kutsal alan\n"
                "C1.4 ⏱ Şahit olarak zaman\n"
                "C1.5 📱 Rabbin kim?\n"
                "C1.6 🖊 Sıfır kilometre\n"
                "C1.7 💪 Sen kavanozdaki bir beyin değilsin\n"
                "C1.8 🌿 Ruhun genel temizliği\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📘 *Sezon 2 · İnşa · Nasıl yaşıyorsun* — 8 hafta\n\n"
                "C2.1 🧠 Şeytan beyni nasıl hackler\n"
                "C2.2 🏛 Kaleyi inşa etmek\n"
                "C2.3 🔥 Gemileri yakmak\n"
                "C2.4 ⚖️ Mizanda en ağır olan nedir?\n"
                "C2.5 🧳 Ter kurumadan ücretini ver\n"
                "C2.6 📖 En uzun ayet\n"
                "C2.7 🤝 Allah ile ortaklık bilinci\n"
                "C2.8 🌍 Atlas sendromu\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📙 *Sezon 3 · Miras · Neden yaşıyorsun* — 8 hafta\n\n"
                "C3.1 👣 Ayaklarının altında\n"
                "C3.2 🏠 Savaşı kapının dışında bırak\n"
                "C3.3 🧡 Ayna nöronlar\n"
                "C3.4 🌹 Demirci ve misk satıcısı\n"
                "C3.5 👑 Taçsız kral\n"
                "C3.6 🏞 Nehir ve bataklık\n"
                "C3.7 📊 Açık hesap\n"
                "C3.8 🏛 Geri dönüşsüz nokta\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "Tam yol 30 haftadır. Her blok somut bir sonuç verir ve seni bir sonraki seviyeye taşır.\n\n"
                "🗓 *Pazartesi 9:00* — botta haftalık ders\n"
                "📞 *Cuma 14:00* — IQ Barakah kurucusuyla canlı görüşme\n"
                "🌙 *Her gün* — zikir ve muhasebe\n\n"
                "🌿 _Her ödemenin %20'si hayra gider_"
            ),
        },
        "ar": {
            "diag": (
                "🎯 *نتيجتك:* المستوى {level} · {pct}%\n"
                "🌿 *البداية المقترحة:* {recommended}\n\n"
                "━━━━━━━━━━━━━━━━\n"
            ),
            "body": (
                "📚 *برنامج IQ Barakah*\n\n"
                "{diag_block}"
                "برنامج للمسلم الذي يريد الخروج من الدوران في نفس الدائرة.\n\n"
                "تخطط، لكن لا ترى نتيجة واضحة أو معنى عميقاً؟\n"
                "IQ Barakah يساعدك على ربط:\n"
                "✅ القلب: السكينة والنية\n"
                "✅ العقل: التركيز والوضوح\n"
                "✅ السلوك: العادات والأعمال\n\n"
                "الهدف أن تصبح العبادة والأسرة والعمل عناصر تدعم بعضها.\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "🌱 *VAKT · إدارة وقت المسلم* · 6 أسابيع\n\n"
                "B1 🌿 النية — الحديث الخفي\n"
                "B2 🏁 الفجر — مرساة اليوم\n"
                "B3 🕊 التوبة — صفحة جديدة\n"
                "B4 💪 الصبر — الثبات على الطريق\n"
                "B5 📿 الذكر — الله في كل أمر\n"
                "B6 🏆 النتيجة — نظامك\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📗 *الموسم 1 · الأساس · من أنت* — 8 أسابيع\n\n"
                "C1.1 🌿 الحديث الخفي\n"
                "C1.2 🏠 الرجوع إلى البيت\n"
                "C1.3 ✨ المساحة المقدسة\n"
                "C1.4 ⏱ الوقت كشاهد\n"
                "C1.5 📱 من ربك؟\n"
                "C1.6 🖊 الكيلومتر صفر\n"
                "C1.7 💪 أنت لست عقلاً في زجاجة\n"
                "C1.8 🌿 تنظيف عميق للروح\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📘 *الموسم 2 · البناء · كيف تعيش* — 8 أسابيع\n\n"
                "C2.1 🧠 كيف يخترق الشيطان الدماغ\n"
                "C2.2 🏛 بناء الحصن\n"
                "C2.3 🔥 إحراق السفن\n"
                "C2.4 ⚖️ ما أثقل شيء في الميزان؟\n"
                "C2.5 🧳 أعط الأجير أجره قبل أن يجف عرقه\n"
                "C2.6 📖 أطول آية\n"
                "C2.7 🤝 شراكة مع الله\n"
                "C2.8 🌍 متلازمة أطلس\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📙 *الموسم 3 · الأثر · لماذا تعيش* — 8 أسابيع\n\n"
                "C3.1 👣 تحت أقدامهن\n"
                "C3.2 🏠 اترك الحرب خارج الباب\n"
                "C3.3 🧡 الخلايا المرآتية\n"
                "C3.4 🌹 الحداد وبائع الطيب\n"
                "C3.5 👑 ملك بلا تاج\n"
                "C3.6 🏞 النهر والمستنقع\n"
                "C3.7 📊 الحساب المفتوح\n"
                "C3.8 🏛 نقطة اللاعودة\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "المسار الكامل 30 أسبوعاً. كل مرحلة تعطي نتيجة عملية وتنقلك إلى المستوى التالي.\n\n"
                "🗓 *الاثنين 9:00* — درس الأسبوع في البوت\n"
                "📞 *الجمعة 14:00* — لقاء مباشر مع مؤسس IQ Barakah\n"
                "🌙 *يومياً* — الأذكار والمحاسبة\n\n"
                "🌿 _20% من كل دفعة تذهب إلى الصدقة_"
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
    if "💼" in text or "предприним" in text or "entrepreneur" in text or "girişim" in text or "رائد" in text:
        return "entrepreneur"
    if "👔" in text or "сотруд" in text or "наём" in text or "наем" in text or "employee" in text or "çalışan" in text or "موظف" in text:
        return "employee"
    if "🎓" in text or "студ" in text or "student" in text or "öğrenci" in text or "طالب" in text:
        return "student"
    if "🧑‍💻" in text or "самозан" in text or "фриланс" in text or "self-employed" in text or "serbest" in text or "عمل حر" in text:
        return "freelance"
    if "🏠" in text or "другое" in text or "other" in text or "diğer" in text or "أخرى" in text:
        return "other"
    return None


def _source_key(text: str) -> str | None:
    text = text.lower()
    if "📱" in text or "соц" in text or "social" in text or "sosyal" in text or "التواصل" in text:
        return "social"
    if "🔍" in text or "интернет" in text or "internet" in text or "الإنترنت" in text:
        return "internet"
    if "telegram" in text or "телеграм" in text:
        return "telegram"
    if "👥" in text or "знаком" in text or "friends" in text or "tanıdık" in text or "المعارف" in text:
        return "word_of_mouth"
    if "youtube" in text or "reels" in text:
        return "video"
    if "📍" in text or "другое" in text or "other" in text or "diğer" in text or "أخرى" in text:
        return "other"
    return None
