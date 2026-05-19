from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot_v2.services.program import TARIFFS


def kb_main_menu(miniapp_url: str, ship_url: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📱 Mini App", web_app=WebAppInfo(url=miniapp_url))
    b.button(text="🚢 Диагностика бизнеса", web_app=WebAppInfo(url=ship_url))
    b.button(text="🎓 Тарифы", callback_data="show_tariffs")
    b.button(text="🤖 Джарвас — AI-ментор", callback_data="jarwas_start")
    b.adjust(1)
    return b.as_markup()


def kb_tariffs() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in TARIFFS:
        b.button(text=t["name"], callback_data=f"tariff:{t['id']}")
    b.button(text="← Назад", callback_data="back_main")
    b.adjust(1)
    return b.as_markup()


def kb_tariff_detail(tariff_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💳 Оплатить", callback_data=f"pay:{tariff_id}")
    b.button(text="← Назад", callback_data="show_tariffs")
    b.adjust(1)
    return b.as_markup()


def kb_gender() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="👨 Брат", callback_data="gender_m")
    b.button(text="👩 Сестра", callback_data="gender_f")
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
    b = InlineKeyboardBuilder()
    if btn_type == "diag":
        b.button(text="🎯 Пройти диагностику", callback_data="start_diag")
    elif btn_type == "buy_vakt":
        b.button(text="🌱 Купить ВАКТ", callback_data="tariff:vakt")
    elif btn_type == "buy_s1":
        b.button(text="📗 Купить Сезон 1", callback_data="tariff:s1_full")
    elif btn_type == "curator":
        b.button(text="🤝 Написать куратору", callback_data="contact_curator")
    b.button(text="❌ Закрыть чат с Джарвасом", callback_data="jarwas_end")
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
