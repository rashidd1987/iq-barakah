from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from urllib.parse import urlencode

from bot_v2.services.program import TARIFFS, get_tariff_view
from bot_v2.services.i18n import normalize_lang, t


BTN_DIAG = "🎯 Диагностика"
BTN_MINIAPP = "📱 Личный кабинет"
BTN_PROGRAM = "📚 Программа"
BTN_PAYMENT = "💳 Оплата"
BTN_REMINDERS = "🔔 Напоминания"
BTN_CURATOR = "💬 Связаться с куратором"
BTN_MUHASABA = "🌙 Мухасаба"
BTN_SITE = "🌐 Сайт"


def _miniapp_url_with_params(base_url: str, lang: str, participant=None) -> str:
    """Build miniapp URL with level/week/skill params if participant is active."""
    params: dict = {"lang": normalize_lang(lang)}
    if participant and participant.is_active and participant.level:
        from bot_v2.services.program import LEVEL_WEEKS
        level = participant.level
        offsets = {"А": 0, "Б": 6, "В": 14, "Г": 22}
        week_in_level = participant.week - offsets.get(level, 0)
        week_in_level = max(1, min(week_in_level, LEVEL_WEEKS.get(level, 8)))
        params["lvl"] = level
        params["wk"] = week_in_level
        params["skill"] = participant.vakt_level or "I"
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}{urlencode(params)}"


def kb_main_menu(miniapp_url: str, ship_url: str, lang: str = "ru", participant=None) -> InlineKeyboardMarkup:
    lang = normalize_lang(lang)
    b = InlineKeyboardBuilder()
    ship_sep = "&" if "?" in ship_url else "?"
    b.button(text=t(lang, "menu.miniapp"), web_app=WebAppInfo(url=_miniapp_url_with_params(miniapp_url, lang, participant)))
    b.button(text=t(lang, "menu.ship"), web_app=WebAppInfo(url=f"{ship_url}{ship_sep}lang={lang}"))
    b.button(text="🚢 Кораблик — диагностика жизни", callback_data="korablik_start")
    b.button(text=t(lang, "menu.tariffs"), callback_data="show_tariffs")
    b.button(text=t(lang, "menu.jarwas"), callback_data="jarwas_start")
    b.adjust(1)
    return b.as_markup()


def kb_bottom_menu(miniapp_url: str, lang: str = "ru", participant=None) -> ReplyKeyboardMarkup:
    lang = normalize_lang(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "bottom.diag")),
                KeyboardButton(text=t(lang, "bottom.miniapp"), web_app=WebAppInfo(url=_miniapp_url_with_params(miniapp_url, lang, participant))),
            ],
            [KeyboardButton(text=t(lang, "bottom.program")), KeyboardButton(text=t(lang, "bottom.payment"))],
            [KeyboardButton(text=t(lang, "bottom.reminders")), KeyboardButton(text=t(lang, "bottom.curator"))],
            [KeyboardButton(text=t(lang, "bottom.muhasaba")), KeyboardButton(text=t(lang, "bottom.site"))],
            [KeyboardButton(text=t(lang, "bottom.jarwas"))],
        ],
        resize_keyboard=True,
        input_field_placeholder=t(lang, "bottom.placeholder"),
    )


def _url_with_lang(url: str, lang: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}lang={normalize_lang(lang)}"


def kb_onboarding_gender(lang: str = "ru") -> ReplyKeyboardMarkup:
    lang = normalize_lang(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "onboarding.gender_male")),
                KeyboardButton(text=t(lang, "onboarding.gender_female")),
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def kb_onboarding_occupation(lang: str = "ru") -> ReplyKeyboardMarkup:
    lang = normalize_lang(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "onboarding.occ_entrepreneur")),
                KeyboardButton(text=t(lang, "onboarding.occ_employee")),
            ],
            [
                KeyboardButton(text=t(lang, "onboarding.occ_student")),
                KeyboardButton(text=t(lang, "onboarding.occ_freelance")),
            ],
            [KeyboardButton(text=t(lang, "onboarding.occ_other"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def kb_onboarding_source(lang: str = "ru") -> ReplyKeyboardMarkup:
    lang = normalize_lang(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "onboarding.src_social")),
                KeyboardButton(text=t(lang, "onboarding.src_internet")),
            ],
            [
                KeyboardButton(text=t(lang, "onboarding.src_telegram")),
                KeyboardButton(text=t(lang, "onboarding.src_word")),
            ],
            [
                KeyboardButton(text=t(lang, "onboarding.src_video")),
                KeyboardButton(text=t(lang, "onboarding.src_other")),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )



def kb_onboard_step1(lang: str = "ru") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "onboard.step1_btn"), callback_data="onboard_ready")
    b.adjust(1)
    return b.as_markup()


def kb_onboard_step2(lang: str = "ru") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "onboard.step2_btn"), callback_data="onboard_audit")
    b.adjust(1)
    return b.as_markup()


def kb_onboard_step3(miniapp_url: str, lang: str = "ru") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "onboard.step3_diag_btn"), web_app=WebAppInfo(url=miniapp_url))
    b.button(text=t(lang, "onboard.step3_skip_btn"), callback_data="onboard_to_fio")
    b.adjust(1)
    return b.as_markup()


def kb_start_diag(lang: str = "ru") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "diag.button"), callback_data="start_diag")
    b.adjust(1)
    return b.as_markup()


def kb_program_overview(
    has_diag: bool = False,
    recommended_tariff_id: str = "vakt",
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    recommended = next((tariff for tariff in TARIFFS if tariff["id"] == recommended_tariff_id), TARIFFS[0])
    names = {
        "vakt": "🌱 ВАКТ",
        "s1_full": "📗 IQ Barakah · Сезон 1",
        "s3_full": "🏆 IQ Barakah · 3 сезона",
        "jamaat": "👥 Джамаат",
        "leader": "👑 Лидер Уммы",
    }
    name = names.get(recommended["id"], recommended["name"])
    b.button(text=f"🌿 Рекомендовано: {name}", callback_data=f"tariff:{recommended['id']}")
    b.button(text="🎓 Все тарифы", callback_data="show_tariffs")
    if not has_diag:
        b.button(text="🎯 Пройти диагностику", callback_data="start_diag")
    b.adjust(1)
    return b.as_markup()


def kb_tariffs(lang: str = "ru") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for tariff in TARIFFS:
        tariff_view = get_tariff_view(tariff["id"], lang) or tariff
        price = tariff["price"]
        tid = tariff["id"]
        if price:
            price_str = f"{price:,}".replace(",", " ")
            if tid == "s1_month":
                label = f"{tariff_view['name']} · {price_str} ₽/мес"
            elif tid == "s1_full":
                label = f"⭐ {tariff_view['name']} · {price_str} ₽"
            else:
                label = f"{tariff_view['name']} · {price_str} ₽"
        else:
            label = f"{tariff_view['name']} · по запросу"
        b.button(text=label, callback_data=f"tariff:{tariff['id']}")
    b.button(text=t(lang, "tariffs.back"), callback_data="back_main")
    b.adjust(1)
    return b.as_markup()


def kb_tariff_detail(tariff_id: str, lang: str = "ru") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "tariffs.pay"), callback_data=f"pay:{tariff_id}")
    b.button(text=t(lang, "tariffs.back"), callback_data="show_tariffs")
    b.adjust(1)
    return b.as_markup()


def kb_gender(lang: str = "ru") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "gender.male"), callback_data="gender_m")
    b.button(text=t(lang, "gender.female"), callback_data="gender_f")
    b.adjust(2)
    return b.as_markup()


def kb_occupation() -> InlineKeyboardMarkup:
    opts = [
        ("💼 Предприниматель", "occ:entrepreneur"),
        ("👔 Наёмный сотрудник", "occ:employee"),
        ("🎓 Студент", "occ:student"),
        ("🧑‍💻 Самозанятый", "occ:freelance"),
    ]
    b = InlineKeyboardBuilder()
    for label, data in opts:
        b.button(text=label, callback_data=data)
    b.adjust(1)
    return b.as_markup()


def kb_source() -> InlineKeyboardMarkup:
    opts = [
        ("📍 Карты (2ГИС/Яндекс)", "src:maps"),
        ("📱 Соцсети", "src:social"),
        ("🔍 Интернет/поиск", "src:internet"),
        ("💬 Форумы/Telegram", "src:forums"),
        ("👥 От знакомых", "src:word_of_mouth"),
        ("📺 YouTube/Reels", "src:video"),
    ]
    b = InlineKeyboardBuilder()
    for label, data in opts:
        b.button(text=label, callback_data=data)
    b.adjust(1)
    return b.as_markup()


def kb_week_ack() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Выполнил задания — открыть следующую неделю", callback_data="week_ack")
    return b.as_markup()


def kb_jarwas_actions(btn_type: str | None = None) -> InlineKeyboardMarkup:
    return kb_jarwas_actions_i18n(btn_type, "ru")


def kb_jarwas_actions_i18n(btn_type: str | None = None, lang: str = "ru") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if btn_type == "diag":
        b.button(text=t(lang, "jarwas.diag"), callback_data="start_diag")
    elif btn_type == "buy_vakt":
        b.button(text=t(lang, "jarwas.buy_vakt"), callback_data="tariff:vakt")
    elif btn_type == "buy_s1":
        b.button(text=t(lang, "jarwas.buy_s1"), callback_data="tariff:s1_full")
    elif btn_type == "curator":
        b.button(text=t(lang, "jarwas.curator"), callback_data="contact_curator")
    b.button(text=t(lang, "jarwas.close"), callback_data="jarwas_end")
    b.adjust(1)
    return b.as_markup()


def kb_pd_consent() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Согласен(а) с условиями", callback_data="pd_agree")
    b.button(text="❌ Не согласен(а)", callback_data="pd_decline")
    b.adjust(1)
    return b.as_markup()


def kb_diag_answer(options: list[tuple[str, int]], q_idx: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for label, score in options:
        b.button(text=label, callback_data=f"dq:{q_idx}:{score}")
    b.adjust(1)
    return b.as_markup()


def kb_curator_notify(user_id: int, tariff_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Активировать", callback_data=f"curator_activate:{user_id}:{tariff_id}")
    return b.as_markup()
