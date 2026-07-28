"""Генератор PNG: билет на форум + чек-лист лид-магнит."""
import io
import os
from PIL import Image, ImageDraw, ImageFont

BG_DARK = (15, 35, 24)
GREEN_BRIGHT = (74, 222, 128)
GREEN_MID = (111, 207, 154)
GREEN_DIM = (138, 173, 153)
GREEN_FAINT = (74, 122, 94)
WHITE = (255, 255, 255)
CARD_BG = (255, 255, 255, 13)   # rgba(255,255,255,0.05)
CARD_BORDER = (255, 255, 255, 26)

W = 900


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    paths_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    paths_regular = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    paths = paths_bold if bold else paths_regular
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _text_center(draw: ImageDraw.Draw, y: int, text: str, font, color):
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (W - (bbox[2] - bbox[0])) // 2
    draw.text((x, y), text, font=font, fill=color)
    return bbox[3] - bbox[1]


def _wrap(text: str, font, max_w: int) -> list[str]:
    words = text.split()
    lines, cur = [], ""
    dummy = Image.new("RGB", (1, 1))
    dd = ImageDraw.Draw(dummy)
    for w in words:
        test = (cur + " " + w).strip()
        if dd.textbbox((0, 0), test, font=font)[2] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def generate_checklist() -> bytes:
    rules = [
        ("Встань до телефона", "Первые 5 минут утра — только ты и Аллах. Не лента."),
        ("Скажи зачем", "Перед каждым делом — 3 секунды. «Ради чего я это делаю?» Это ният."),
        ("Намаз — якорь, не пауза", "Планируй день вокруг молитв. Не молитвы вокруг дел."),
        ("Одно дело до конца", "Не список — одно. Сделай хорошо. Это и есть ихсан."),
        ("Три вопроса перед сном", "Что получилось · Что было тяжело · Что сделаю иначе завтра"),
    ]

    f_label = _font(22)
    f_title_big = _font(48, bold=True)
    f_sub = _font(26)
    f_num = _font(40, bold=True)
    f_rule = _font(32, bold=True)
    f_desc = _font(26)
    f_site = _font(22)

    pad = 60
    card_h = 100
    card_gap = 14
    total_cards = len(rules) * (card_h + card_gap)
    H = 200 + total_cards + 120

    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img, "RGBA")

    y = 50
    _text_center(draw, y, "IQ BARAKAH", f_label, GREEN_MID)
    y += 38
    _text_center(draw, y, "5 правил дня с барака", f_title_big, WHITE)
    y += 62
    _text_center(draw, y, "Не мотивация. Система.", f_sub, GREEN_DIM)
    y += 56

    for i, (title, desc) in enumerate(rules):
        x0, y0, x1, y1 = pad, y, W - pad, y + card_h
        draw.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=(255, 255, 255, 13), outline=(255, 255, 255, 26))
        draw.text((pad + 20, y + 18), str(i + 1), font=f_num, fill=GREEN_BRIGHT)
        draw.text((pad + 74, y + 14), title, font=f_rule, fill=WHITE)
        draw.text((pad + 74, y + 54), desc, font=f_desc, fill=GREEN_DIM)
        y += card_h + card_gap

    y += 20
    draw.line([(pad, y), (W - pad, y)], fill=(255, 255, 255, 26), width=1)
    y += 18
    _text_center(draw, y, "iq-barakah.ru", f_site, GREEN_FAINT)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()


def generate_ticket(name: str, ticket_no: str) -> bytes:
    f_label = _font(22)
    f_brand = _font(44, bold=True)
    f_event = _font(34, bold=True)
    f_date = _font(28)
    f_includes = _font(26)
    f_name_label = _font(22)
    f_name = _font(42, bold=True)
    f_num = _font(22)
    f_site = _font(20)

    H = 680
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img, "RGBA")

    pad = 60

    # Верхняя полоса
    draw.rectangle([0, 0, W, 6], fill=GREEN_BRIGHT)

    y = 36
    _text_center(draw, y, "IQ BARAKAH", f_label, GREEN_MID)
    y += 42
    _text_center(draw, y, "БИЛЕТ НА ФОРУМ", f_brand, WHITE)
    y += 64

    # Разделитель
    draw.line([(pad, y), (W - pad, y)], fill=(255, 255, 255, 26), width=1)
    y += 28

    _text_center(draw, y, "27 июня · Ресторан Шатёр", f_event, GREEN_BRIGHT)
    y += 46
    _text_center(draw, y, "Хасавюрт · начало в 11:00", f_date, GREEN_DIM)
    y += 36
    _text_center(draw, y, "пр. Имама Шамиля, 172", f_date, GREEN_FAINT)
    y += 36

    draw.line([(pad, y), (W - pad, y)], fill=(255, 255, 255, 26), width=1)
    y += 30

    # Что включено
    includes = [
        "•  Вход на форум",
        "•  IQ Barakah Старт · 6 шагов",
        "•  Обед в Шатёр после форума",
    ]
    for item in includes:
        draw.text((pad + 40, y), item, font=f_includes, fill=GREEN_MID)
        y += 40
    y += 20

    draw.line([(pad, y), (W - pad, y)], fill=(255, 255, 255, 26), width=1)
    y += 30

    # Имя
    draw.text((pad + 40, y), "УЧАСТНИК", font=f_name_label, fill=GREEN_DIM)
    y += 32
    draw.text((pad + 40, y), name or "Гость", font=f_name, fill=WHITE)
    y += 66

    # Нижняя полоса
    draw.rectangle([0, H - 60, W, H], fill=(255, 255, 255, 8))
    draw.text((pad + 40, H - 46), f"№ {ticket_no}", font=f_num, fill=GREEN_DIM)
    # Сайт справа
    site_bbox = draw.textbbox((0, 0), "iq-barakah.ru", font=f_site)
    site_w = site_bbox[2] - site_bbox[0]
    draw.text((W - pad - site_w, H - 44), "iq-barakah.ru", font=f_site, fill=GREEN_FAINT)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()
