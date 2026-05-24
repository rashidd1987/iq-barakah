SUPPORTED_LANGS = ("ru", "en", "ar", "de", "tr", "id", "ur", "bn", "fr", "ms")
RTL_LANGS = {"ar", "ur"}

LANG_LABELS = {
    "ru": "Русский",
    "en": "English",
    "ar": "العربية",
    "de": "Deutsch",
    "tr": "Türkçe",
    "id": "Bahasa Indonesia",
    "ur": "اردو",
    "bn": "বাংলা",
    "fr": "Français",
    "ms": "Bahasa Melayu",
}

LANG_FLAGS = {
    "ru": "🇷🇺",
    "en": "🇬🇧",
    "ar": "🇸🇦",
    "de": "🇩🇪",
    "tr": "🇹🇷",
    "id": "🇮🇩",
    "ur": "🇵🇰",
    "bn": "🇧🇩",
    "fr": "🇫🇷",
    "ms": "🇲🇾",
}

TEXTS = {
    "ru": {
        "start.greeting": (
            "Ас-саляму алейкум, *{name}*! 🌿\n\n"
            "Добро пожаловать в IQ Barakah — программу для мусульманина, "
            "который хочет выстроить жизнь с Аллахом в центре.\n\n"
            "Выбери с чего начать 👇"
        ),
        "menu.miniapp": "📱 Mini App",
        "menu.ship": "🚢 Диагностика бизнеса",
        "menu.tariffs": "🎓 Тарифы",
        "menu.jarwas": "🤖 Джарвас — AI-ментор",
        "menu.language": "🌍 Язык",
        "language.choose": "🌍 Выбери язык интерфейса:",
        "language.saved": "✅ Язык сохранён: {language}",
    },
    "en": {
        "start.greeting": (
            "As-salamu alaykum, *{name}*! 🌿\n\n"
            "Welcome to IQ Barakah — a program for Muslims who want to build life "
            "with Allah at the center.\n\n"
            "Choose where to begin 👇"
        ),
        "menu.miniapp": "📱 Mini App",
        "menu.ship": "🚢 Business Diagnostic",
        "menu.tariffs": "🎓 Plans",
        "menu.jarwas": "🤖 Jarwas — AI mentor",
        "menu.language": "🌍 Language",
        "language.choose": "🌍 Choose interface language:",
        "language.saved": "✅ Language saved: {language}",
    },
    "ar": {
        "start.greeting": (
            "السلام عليكم، *{name}*! 🌿\n\n"
            "مرحباً بك في IQ Barakah — برنامج للمسلم الذي يريد أن يبني حياته "
            "وجعل رضا الله في المركز.\n\n"
            "اختر من أين تبدأ 👇"
        ),
        "menu.miniapp": "📱 التطبيق المصغر",
        "menu.ship": "🚢 تشخيص العمل",
        "menu.tariffs": "🎓 الباقات",
        "menu.jarwas": "🤖 جروَاس — مرشد AI",
        "menu.language": "🌍 اللغة",
        "language.choose": "🌍 اختر لغة الواجهة:",
        "language.saved": "✅ تم حفظ اللغة: {language}",
    },
    "de": {
        "start.greeting": (
            "As-salamu alaykum, *{name}*! 🌿\n\n"
            "Willkommen bei IQ Barakah — einem Programm für Muslime, die ihr Leben "
            "mit Allah im Zentrum aufbauen möchten.\n\n"
            "Wähle, womit du beginnen möchtest 👇"
        ),
        "menu.miniapp": "📱 Mini App",
        "menu.ship": "🚢 Business-Diagnose",
        "menu.tariffs": "🎓 Tarife",
        "menu.jarwas": "🤖 Jarwas — AI-Mentor",
        "menu.language": "🌍 Sprache",
        "language.choose": "🌍 Wähle die Sprache:",
        "language.saved": "✅ Sprache gespeichert: {language}",
    },
}


def normalize_lang(lang: str | None) -> str:
    if not lang:
        return "ru"
    lang = lang.lower().split("-")[0]
    return lang if lang in SUPPORTED_LANGS else "ru"


def t(lang: str | None, key: str, **kwargs) -> str:
    lang = normalize_lang(lang)
    value = TEXTS.get(lang, TEXTS["ru"]).get(key, TEXTS["ru"].get(key, key))
    return value.format(**kwargs) if kwargs else value


def language_name(lang: str | None) -> str:
    lang = normalize_lang(lang)
    return f"{LANG_FLAGS.get(lang, '')} {LANG_LABELS.get(lang, lang)}".strip()
