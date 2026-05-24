SUPPORTED_LANGS = ("ru", "en", "ar", "tr")
RTL_LANGS = {"ar"}

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
        "gender.ask": "Прежде чем начать — ты:",
        "gender.male": "👨 Брат",
        "gender.female": "👩 Сестра",
        "diag.result_title": "🎯 *Результат диагностики*",
        "diag.recommended_path": "📍 Рекомендованный путь:",
        "diag.open_menu": "Напиши /start чтобы открыть меню. 🌿",
        "diag.level_a": "Уровень А — Начинаю с нуля",
        "diag.level_b": "Уровень Б — Иногда практикую",
        "diag.level_c": "Уровень В — Практикую регулярно",
        "diag.intro_a": "Это честный результат. Точка силы, не слабости.",
        "diag.intro_b": "Ты уже на пути. Практика есть, но систему ещё надо укрепить.",
        "diag.intro_c": "МашаАллах. У тебя уже есть основа, теперь важно выстроить устойчивую систему.",
        "diag.path_a": "🌱 ВАКТ — Тайм-менеджмент мусульманина",
        "diag.path_b": "🌱 ВАКТ → 📗 Сезон 1 · Основание",
        "diag.path_c": "📗 Сезон 1 → 📘 Сезон 2 · Строительство",
        "tariffs.title": "🎓 *Тарифы IQ Barakah*\n\nВыбери программу:",
        "tariffs.not_found": "Тариф не найден.",
        "tariffs.pay": "💳 Оплатить",
        "tariffs.back": "← Назад",
        "payments.unavailable": "Оплата временно недоступна. Напишите куратору.",
        "payments.email": "📧 Введи email для чека ЮKassa:\n_(нажми /skip если не нужен)_",
        "payments.manager": "Для записи свяжитесь с менеджером:\n📞 *+7 989 470 80 66* (WhatsApp)\n\nМенеджер расскажет об условиях и ответит на вопросы.",
        "payments.success": "✅ *Оплата получена!*\n\n*{tariff}* — {amount} ₽\n\nКуратор активирует тебя в программе в течение 24 часов. ин ша Аллах 🌿",
        "progress.not_active": "Ты пока не в программе. Напиши куратору для активации. 🌿",
        "progress.title": "📊 *Твой прогресс*",
        "progress.week": "📅 Неделя {week}/{max_weeks} · {pct}% пройдено",
        "week.not_active": "Ты не активирован в программе.",
        "week.graduated": "🎓 *Поздравляем!*\n\nТы завершил *{level}*!\n\nБаракАллах фикум. Напиши куратору для перехода на следующий уровень. 🌿",
        "week.acked": "✅ *Неделя {week} засчитана!*\n\nСледующий урок придёт в воскресенье ин ша Аллах. 🌿",
        "lesson.ready": "Урок недели готов! Открой Mini App чтобы изучить материал.",
        "lesson.open": "📱 Открыть Mini App",
        "jarwas.start": "🤖 *Джарвас — AI-ментор IQ Barakah*\n\nПривет! Я здесь чтобы помочь тебе в рамках программы IQ Barakah.\nЗадай любой вопрос о программе, своём прогрессе или о том, с чего начать. 🌿\n\n_Для завершения нажми кнопку ниже._",
        "jarwas.end": "БаракАллах фикум. Напиши /start чтобы вернуться в меню. 🌿",
        "jarwas.close": "❌ Закрыть чат с Джарвасом",
        "jarwas.diag": "🎯 Пройти диагностику",
        "jarwas.buy_vakt": "🌱 Купить ВАКТ",
        "jarwas.buy_s1": "📗 Купить Сезон 1",
        "jarwas.curator": "🤝 Написать куратору",
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
        "gender.ask": "Before we begin, you are:",
        "gender.male": "👨 Brother",
        "gender.female": "👩 Sister",
        "diag.result_title": "🎯 *Diagnostic result*",
        "diag.recommended_path": "📍 Recommended path:",
        "diag.open_menu": "Send /start to open the menu. 🌿",
        "diag.level_a": "Level A — Starting from zero",
        "diag.level_b": "Level B — Practicing sometimes",
        "diag.level_c": "Level C — Practicing regularly",
        "diag.intro_a": "This is an honest result. A point of strength, not weakness.",
        "diag.intro_b": "You are already on the path. The practice is there, but the system needs strengthening.",
        "diag.intro_c": "MashaAllah. You already have a foundation; now build a stable system.",
        "diag.path_a": "🌱 VAKT — Muslim time management",
        "diag.path_b": "🌱 VAKT → 📗 Season 1 · Foundation",
        "diag.path_c": "📗 Season 1 → 📘 Season 2 · Building",
        "tariffs.title": "🎓 *IQ Barakah plans*\n\nChoose a program:",
        "tariffs.not_found": "Plan not found.",
        "tariffs.pay": "💳 Pay",
        "tariffs.back": "← Back",
        "payments.unavailable": "Payment is temporarily unavailable. Please contact the curator.",
        "payments.email": "📧 Enter your email for the receipt:\n_(send /skip if you do not need one)_",
        "payments.manager": "To join, contact our manager:\n📞 *+7 989 470 80 66* (WhatsApp)\n\nThe manager will explain the terms and answer your questions.",
        "payments.success": "✅ *Payment received!*\n\n*{tariff}* — {amount} ₽\n\nThe curator will activate your program within 24 hours, in sha Allah 🌿",
        "progress.not_active": "You are not in the program yet. Contact the curator for activation. 🌿",
        "progress.title": "📊 *Your progress*",
        "progress.week": "📅 Week {week}/{max_weeks} · {pct}% complete",
        "week.not_active": "You are not activated in the program.",
        "week.graduated": "🎓 *Congratulations!*\n\nYou completed *{level}*!\n\nBarakAllahu feek. Contact the curator to move to the next level. 🌿",
        "week.acked": "✅ *Week {week} counted!*\n\nThe next lesson will arrive on Sunday, in sha Allah. 🌿",
        "lesson.ready": "This week's lesson is ready! Open the Mini App to study the material.",
        "lesson.open": "📱 Open Mini App",
        "jarwas.start": "🤖 *Jarwas — IQ Barakah AI mentor*\n\nHi! I am here to help within the IQ Barakah program.\nAsk any question about the program, your progress, or where to begin. 🌿\n\n_To finish, press the button below._",
        "jarwas.end": "BarakAllahu feek. Send /start to return to the menu. 🌿",
        "jarwas.close": "❌ Close Jarwas chat",
        "jarwas.diag": "🎯 Take diagnostic",
        "jarwas.buy_vakt": "🌱 Buy VAKT",
        "jarwas.buy_s1": "📗 Buy Season 1",
        "jarwas.curator": "🤝 Contact curator",
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
        "gender.ask": "قبل أن نبدأ، أنت:",
        "gender.male": "👨 أخ",
        "gender.female": "👩 أخت",
        "diag.result_title": "🎯 *نتيجة التشخيص*",
        "diag.recommended_path": "📍 المسار المقترح:",
        "diag.open_menu": "اكتب /start لفتح القائمة. 🌿",
        "diag.level_a": "المستوى أ — أبدأ من الصفر",
        "diag.level_b": "المستوى ب — أمارس أحياناً",
        "diag.level_c": "المستوى ج — أمارس بانتظام",
        "diag.intro_a": "هذه نتيجة صادقة. هي نقطة قوة وليست ضعفاً.",
        "diag.intro_b": "أنت بالفعل في الطريق. توجد ممارسة، لكن النظام يحتاج إلى تقوية.",
        "diag.intro_c": "ما شاء الله. لديك أساس، والآن نحتاج إلى بناء نظام ثابت.",
        "diag.path_a": "🌱 VAKT — إدارة وقت المسلم",
        "diag.path_b": "🌱 VAKT → 📗 الموسم 1 · الأساس",
        "diag.path_c": "📗 الموسم 1 → 📘 الموسم 2 · البناء",
        "tariffs.title": "🎓 *باقات IQ Barakah*\n\nاختر البرنامج:",
        "tariffs.not_found": "الباقة غير موجودة.",
        "tariffs.pay": "💳 الدفع",
        "tariffs.back": "← رجوع",
        "payments.unavailable": "الدفع غير متاح مؤقتاً. تواصل مع المشرف.",
        "payments.email": "📧 أدخل البريد الإلكتروني للإيصال:\n_(أرسل /skip إذا لم تكن تحتاجه)_",
        "payments.manager": "للانضمام تواصل مع المدير:\n📞 *+7 989 470 80 66* (WhatsApp)\n\nسيشرح لك الشروط ويجيب عن الأسئلة.",
        "payments.success": "✅ *تم استلام الدفع!*\n\n*{tariff}* — {amount} ₽\n\nسيقوم المشرف بتفعيل البرنامج خلال 24 ساعة إن شاء الله 🌿",
        "progress.not_active": "لم يتم تفعيلك في البرنامج بعد. تواصل مع المشرف. 🌿",
        "progress.title": "📊 *تقدمك*",
        "progress.week": "📅 الأسبوع {week}/{max_weeks} · اكتمل {pct}%",
        "week.not_active": "لم يتم تفعيلك في البرنامج.",
        "week.graduated": "🎓 *مبارك!*\n\nلقد أتممت *{level}*!\n\nبارك الله فيك. تواصل مع المشرف للانتقال إلى المستوى التالي. 🌿",
        "week.acked": "✅ *تم احتساب الأسبوع {week}!*\n\nسيصل الدرس التالي يوم الأحد إن شاء الله. 🌿",
        "lesson.ready": "درس هذا الأسبوع جاهز! افتح التطبيق المصغر لدراسة المادة.",
        "lesson.open": "📱 افتح التطبيق المصغر",
        "jarwas.start": "🤖 *جروَاس — مرشد IQ Barakah بالذكاء الاصطناعي*\n\nمرحباً! أنا هنا لمساعدتك داخل برنامج IQ Barakah.\nاسأل أي سؤال عن البرنامج أو تقدمك أو من أين تبدأ. 🌿\n\n_للإنهاء اضغط الزر أدناه._",
        "jarwas.end": "بارك الله فيك. اكتب /start للعودة إلى القائمة. 🌿",
        "jarwas.close": "❌ إغلاق محادثة جروَاس",
        "jarwas.diag": "🎯 ابدأ التشخيص",
        "jarwas.buy_vakt": "🌱 شراء VAKT",
        "jarwas.buy_s1": "📗 شراء الموسم 1",
        "jarwas.curator": "🤝 تواصل مع المشرف",
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
        "gender.ask": "Bevor wir beginnen, bist du:",
        "gender.male": "👨 Bruder",
        "gender.female": "👩 Schwester",
        "diag.result_title": "🎯 *Diagnose-Ergebnis*",
        "diag.recommended_path": "📍 Empfohlener Weg:",
        "diag.open_menu": "Sende /start, um das Menü zu öffnen. 🌿",
        "diag.level_a": "Level A — Ich beginne bei null",
        "diag.level_b": "Level B — Ich praktiziere manchmal",
        "diag.level_c": "Level C — Ich praktiziere regelmäßig",
        "diag.intro_a": "Das ist ein ehrliches Ergebnis. Ein Punkt der Stärke, nicht der Schwäche.",
        "diag.intro_b": "Du bist bereits auf dem Weg. Praxis ist da, das System muss stärker werden.",
        "diag.intro_c": "MashaAllah. Du hast eine Grundlage; jetzt braucht es ein stabiles System.",
        "diag.path_a": "🌱 VAKT — Zeitmanagement für Muslime",
        "diag.path_b": "🌱 VAKT → 📗 Saison 1 · Fundament",
        "diag.path_c": "📗 Saison 1 → 📘 Saison 2 · Aufbau",
        "tariffs.title": "🎓 *IQ Barakah Tarife*\n\nWähle ein Programm:",
        "tariffs.not_found": "Tarif nicht gefunden.",
        "tariffs.pay": "💳 Bezahlen",
        "tariffs.back": "← Zurück",
        "payments.unavailable": "Zahlung ist vorübergehend nicht verfügbar. Kontaktiere den Kurator.",
        "payments.email": "📧 Gib deine E-Mail für den Beleg ein:\n_(sende /skip, wenn du keinen brauchst)_",
        "payments.manager": "Zur Anmeldung kontaktiere den Manager:\n📞 *+7 989 470 80 66* (WhatsApp)\n\nDer Manager erklärt die Bedingungen und beantwortet Fragen.",
        "payments.success": "✅ *Zahlung erhalten!*\n\n*{tariff}* — {amount} ₽\n\nDer Kurator aktiviert dich innerhalb von 24 Stunden, in sha Allah 🌿",
        "progress.not_active": "Du bist noch nicht im Programm. Kontaktiere den Kurator zur Aktivierung. 🌿",
        "progress.title": "📊 *Dein Fortschritt*",
        "progress.week": "📅 Woche {week}/{max_weeks} · {pct}% abgeschlossen",
        "week.not_active": "Du bist im Programm nicht aktiviert.",
        "week.graduated": "🎓 *Glückwunsch!*\n\nDu hast *{level}* abgeschlossen!\n\nBarakAllahu feek. Kontaktiere den Kurator für das nächste Level. 🌿",
        "week.acked": "✅ *Woche {week} gezählt!*\n\nDie nächste Lektion kommt am Sonntag, in sha Allah. 🌿",
        "lesson.ready": "Die Wochenlektion ist bereit! Öffne die Mini App, um das Material zu lernen.",
        "lesson.open": "📱 Mini App öffnen",
        "jarwas.start": "🤖 *Jarwas — IQ Barakah AI-Mentor*\n\nHi! Ich helfe dir im Rahmen des IQ Barakah Programms.\nStelle eine Frage zum Programm, deinem Fortschritt oder zum Start. 🌿\n\n_Zum Beenden drücke die Taste unten._",
        "jarwas.end": "BarakAllahu feek. Sende /start, um zum Menü zurückzukehren. 🌿",
        "jarwas.close": "❌ Jarwas-Chat schließen",
        "jarwas.diag": "🎯 Diagnose starten",
        "jarwas.buy_vakt": "🌱 VAKT kaufen",
        "jarwas.buy_s1": "📗 Saison 1 kaufen",
        "jarwas.curator": "🤝 Kurator kontaktieren",
    },
}

EXTRA_LANGUAGE_TEXTS = {
    "tr": {
        "start.greeting": "Esselamu aleykum, *{name}*! 🌿\n\nIQ Barakah'a hoş geldin — hayatını Allah merkezli kurmak isteyen Müslümanlar için bir program.\n\nNereden başlamak istediğini seç 👇",
        "menu.ship": "🚢 İş teşhisi",
        "menu.tariffs": "🎓 Tarifeler",
        "menu.jarwas": "🤖 Jarwas — AI mentor",
        "menu.language": "🌍 Dil",
        "language.choose": "🌍 Arayüz dilini seç:",
        "language.saved": "✅ Dil kaydedildi: {language}",
        "gender.ask": "Başlamadan önce, sen:",
        "gender.male": "👨 Kardeş",
        "gender.female": "👩 Kız kardeş",
        "tariffs.title": "🎓 *IQ Barakah tarifeleri*\n\nProgram seç:",
        "tariffs.pay": "💳 Öde",
        "tariffs.back": "← Geri",
        "progress.title": "📊 *İlerlemen*",
        "lesson.ready": "Haftanın dersi hazır! Materyali okumak için Mini App'i aç.",
        "jarwas.start": "🤖 *Jarwas — IQ Barakah AI mentoru*\n\nMerhaba! IQ Barakah programında sana yardımcı olmak için buradayım.\nProgram, ilerlemen veya nereden başlayacağın hakkında soru sor. 🌿\n\n_Bitirmek için aşağıdaki düğmeye bas._",
        "jarwas.close": "❌ Jarwas sohbetini kapat",
    },
    "id": {
        "start.greeting": "Assalamu'alaikum, *{name}*! 🌿\n\nSelamat datang di IQ Barakah — program untuk Muslim yang ingin membangun hidup dengan Allah sebagai pusat.\n\nPilih mulai dari mana 👇",
        "menu.ship": "🚢 Diagnostik bisnis",
        "menu.tariffs": "🎓 Paket",
        "menu.jarwas": "🤖 Jarwas — mentor AI",
        "menu.language": "🌍 Bahasa",
        "language.choose": "🌍 Pilih bahasa antarmuka:",
        "language.saved": "✅ Bahasa disimpan: {language}",
        "gender.ask": "Sebelum mulai, kamu:",
        "gender.male": "👨 Saudara",
        "gender.female": "👩 Saudari",
        "tariffs.title": "🎓 *Paket IQ Barakah*\n\nPilih program:",
        "tariffs.pay": "💳 Bayar",
        "tariffs.back": "← Kembali",
        "progress.title": "📊 *Progresmu*",
        "lesson.ready": "Pelajaran minggu ini siap! Buka Mini App untuk belajar.",
        "jarwas.start": "🤖 *Jarwas — mentor AI IQ Barakah*\n\nHai! Saya di sini untuk membantu dalam program IQ Barakah.\nTanyakan apa pun tentang program, progresmu, atau dari mana harus mulai. 🌿\n\n_Untuk selesai, tekan tombol di bawah._",
        "jarwas.close": "❌ Tutup chat Jarwas",
    },
    "ur": {
        "start.greeting": "السلام علیکم، *{name}*! 🌿\n\nIQ Barakah میں خوش آمدید — یہ ان مسلمانوں کے لیے پروگرام ہے جو اپنی زندگی اللہ کو مرکز بنا کر بنانا چاہتے ہیں۔\n\nشروع کرنے کے لیے انتخاب کریں 👇",
        "menu.ship": "🚢 کاروباری تشخیص",
        "menu.tariffs": "🎓 پیکجز",
        "menu.jarwas": "🤖 Jarwas — AI mentor",
        "menu.language": "🌍 زبان",
        "language.choose": "🌍 انٹرفیس کی زبان منتخب کریں:",
        "language.saved": "✅ زبان محفوظ ہوگئی: {language}",
        "gender.ask": "شروع کرنے سے پہلے، آپ:",
        "gender.male": "👨 بھائی",
        "gender.female": "👩 بہن",
        "tariffs.title": "🎓 *IQ Barakah پیکجز*\n\nپروگرام منتخب کریں:",
        "tariffs.pay": "💳 ادائیگی",
        "tariffs.back": "← واپس",
        "progress.title": "📊 *آپ کی پیش رفت*",
        "lesson.ready": "اس ہفتے کا سبق تیار ہے! مواد پڑھنے کے لیے Mini App کھولیں۔",
        "jarwas.start": "🤖 *Jarwas — IQ Barakah AI mentor*\n\nالسلام علیکم! میں IQ Barakah پروگرام میں آپ کی مدد کے لیے حاضر ہوں۔\nپروگرام، اپنی پیش رفت یا آغاز کے بارے میں سوال پوچھیں۔ 🌿\n\n_ختم کرنے کے لیے نیچے بٹن دبائیں۔_",
        "jarwas.close": "❌ Jarwas چیٹ بند کریں",
    },
    "bn": {
        "start.greeting": "আসসালামু আলাইকুম, *{name}*! 🌿\n\nIQ Barakah-তে স্বাগতম — আল্লাহকে কেন্দ্র করে জীবন গড়তে চান এমন মুসলিমদের জন্য একটি প্রোগ্রাম।\n\nকোথা থেকে শুরু করবেন বেছে নিন 👇",
        "menu.ship": "🚢 ব্যবসা ডায়াগনস্টিক",
        "menu.tariffs": "🎓 প্যাকেজ",
        "menu.jarwas": "🤖 Jarwas — AI mentor",
        "menu.language": "🌍 ভাষা",
        "language.choose": "🌍 ইন্টারফেসের ভাষা নির্বাচন করুন:",
        "language.saved": "✅ ভাষা সংরক্ষিত হয়েছে: {language}",
        "gender.ask": "শুরু করার আগে, আপনি:",
        "gender.male": "👨 ভাই",
        "gender.female": "👩 বোন",
        "tariffs.title": "🎓 *IQ Barakah প্যাকেজ*\n\nপ্রোগ্রাম নির্বাচন করুন:",
        "tariffs.pay": "💳 পেমেন্ট",
        "tariffs.back": "← ফিরে যান",
        "progress.title": "📊 *আপনার অগ্রগতি*",
        "lesson.ready": "এই সপ্তাহের পাঠ প্রস্তুত! পড়তে Mini App খুলুন।",
        "jarwas.start": "🤖 *Jarwas — IQ Barakah AI mentor*\n\nস্বাগতম! IQ Barakah প্রোগ্রামে আপনাকে সাহায্য করতে আমি এখানে আছি।\nপ্রোগ্রাম, অগ্রগতি বা শুরু নিয়ে প্রশ্ন করুন। 🌿\n\n_শেষ করতে নিচের বোতাম চাপুন।_",
        "jarwas.close": "❌ Jarwas chat বন্ধ করুন",
    },
    "fr": {
        "start.greeting": "As-salamu alaykum, *{name}* ! 🌿\n\nBienvenue dans IQ Barakah — un programme pour les musulmans qui veulent construire leur vie avec Allah au centre.\n\nChoisis par où commencer 👇",
        "menu.ship": "🚢 Diagnostic business",
        "menu.tariffs": "🎓 Offres",
        "menu.jarwas": "🤖 Jarwas — mentor IA",
        "menu.language": "🌍 Langue",
        "language.choose": "🌍 Choisis la langue de l'interface :",
        "language.saved": "✅ Langue enregistrée : {language}",
        "gender.ask": "Avant de commencer, tu es :",
        "gender.male": "👨 Frère",
        "gender.female": "👩 Sœur",
        "tariffs.title": "🎓 *Offres IQ Barakah*\n\nChoisis un programme :",
        "tariffs.pay": "💳 Payer",
        "tariffs.back": "← Retour",
        "progress.title": "📊 *Ta progression*",
        "lesson.ready": "La leçon de la semaine est prête ! Ouvre la Mini App pour étudier.",
        "jarwas.start": "🤖 *Jarwas — mentor IA IQ Barakah*\n\nSalut ! Je suis là pour t'aider dans le programme IQ Barakah.\nPose une question sur le programme, ta progression ou par où commencer. 🌿\n\n_Pour terminer, appuie sur le bouton ci-dessous._",
        "jarwas.close": "❌ Fermer le chat Jarwas",
    },
    "ms": {
        "start.greeting": "Assalamu'alaikum, *{name}*! 🌿\n\nSelamat datang ke IQ Barakah — program untuk Muslim yang mahu membina hidup dengan Allah sebagai pusat.\n\nPilih mula dari mana 👇",
        "menu.ship": "🚢 Diagnostik bisnes",
        "menu.tariffs": "🎓 Pakej",
        "menu.jarwas": "🤖 Jarwas — mentor AI",
        "menu.language": "🌍 Bahasa",
        "language.choose": "🌍 Pilih bahasa antara muka:",
        "language.saved": "✅ Bahasa disimpan: {language}",
        "gender.ask": "Sebelum bermula, anda:",
        "gender.male": "👨 Saudara",
        "gender.female": "👩 Saudari",
        "tariffs.title": "🎓 *Pakej IQ Barakah*\n\nPilih program:",
        "tariffs.pay": "💳 Bayar",
        "tariffs.back": "← Kembali",
        "progress.title": "📊 *Kemajuan anda*",
        "lesson.ready": "Pelajaran minggu ini sudah tersedia! Buka Mini App untuk belajar.",
        "jarwas.start": "🤖 *Jarwas — mentor AI IQ Barakah*\n\nHai! Saya di sini untuk membantu anda dalam program IQ Barakah.\nTanya apa sahaja tentang program, kemajuan anda atau dari mana hendak bermula. 🌿\n\n_Untuk tamat, tekan butang di bawah._",
        "jarwas.close": "❌ Tutup chat Jarwas",
    },
}

for _lang, _texts in EXTRA_LANGUAGE_TEXTS.items():
    TEXTS[_lang] = {**TEXTS["en"], **_texts}

DIAG_QUESTIONS = {
    "ru": [
        ("1️⃣ Встаёшь на Фаджр?", [("😔 Никогда", 0), ("🔄 Иногда", 1), ("✅ Регулярно", 2), ("⭐️ Всегда + тахаджуд", 3)]),
        ("2️⃣ Читаешь утренние азкары?", [("❌ Не читаю", 0), ("🔄 Иногда помню", 1), ("📖 Не каждый день", 2), ("✅ Каждый день", 3)]),
        ("3️⃣ Планируешь свой день?", [("🌊 Живу как идёт", 0), ("💭 Список в голове", 1), ("📝 Пишу иногда", 2), ("⭐️ Фаджр-лист каждый день", 3)]),
        ("4️⃣ Делаешь мухасабу вечером?", [("❓ Что это?", 0), ("💭 Иногда", 1), ("🔄 Пробовал — бросил", 2), ("✅ Каждый вечер", 3)]),
        ("5️⃣ Как у тебя с телефоном утром?", [("📱 Телефон управляет мной", 0), ("🔄 Пытаюсь ограничить", 1), ("⚖️ Есть правила — срываюсь", 2), ("✅ Контролирую", 3)]),
        ("6️⃣ Читаешь Коран?", [("❌ Не читаю", 0), ("🌙 По праздникам", 1), ("📖 Иногда в неделю", 2), ("✅ Каждый день", 3)]),
        ("7️⃣ Как твой бизнес или работа?", [("🌀 Полный хаос", 0), ("⚙️ Без системы", 1), ("📊 Система есть — нет баракта", 2), ("✨ Ищу смысл", 3)]),
        ("8️⃣ Как дела в твоей семье?", [("🏃 Почти не бываю дома", 0), ("📱 Бываю — но в телефоне", 1), ("❤️ Уделяю — хочу больше", 2), ("🏠 Семья — моя крепость", 3)]),
    ],
    "en": [
        ("1️⃣ Do you wake up for Fajr?", [("😔 Never", 0), ("🔄 Sometimes", 1), ("✅ Regularly", 2), ("⭐️ Always + tahajjud", 3)]),
        ("2️⃣ Do you read morning adhkar?", [("❌ I don't", 0), ("🔄 Sometimes", 1), ("📖 Not daily", 2), ("✅ Every day", 3)]),
        ("3️⃣ Do you plan your day?", [("🌊 I go with the flow", 0), ("💭 In my head", 1), ("📝 Sometimes write it", 2), ("⭐️ Fajr-list daily", 3)]),
        ("4️⃣ Do you do evening muhasabah?", [("❓ What is that?", 0), ("💭 Sometimes", 1), ("🔄 Tried and stopped", 2), ("✅ Every evening", 3)]),
        ("5️⃣ How is your phone use in the morning?", [("📱 Phone controls me", 0), ("🔄 I try to limit it", 1), ("⚖️ I have rules but slip", 2), ("✅ I control it", 3)]),
        ("6️⃣ Do you read Qur'an?", [("❌ I don't", 0), ("🌙 On special days", 1), ("📖 Sometimes weekly", 2), ("✅ Every day", 3)]),
        ("7️⃣ How is your work or business?", [("🌀 Total chaos", 0), ("⚙️ No system", 1), ("📊 System exists, little barakah", 2), ("✨ Searching for meaning", 3)]),
        ("8️⃣ How is your family life?", [("🏃 Barely home", 0), ("📱 Home but on phone", 1), ("❤️ I care, want more", 2), ("🏠 Family is my fortress", 3)]),
    ],
    "ar": [
        ("1️⃣ هل تستيقظ لصلاة الفجر؟", [("😔 أبداً", 0), ("🔄 أحياناً", 1), ("✅ بانتظام", 2), ("⭐️ دائماً + تهجد", 3)]),
        ("2️⃣ هل تقرأ أذكار الصباح؟", [("❌ لا أقرأ", 0), ("🔄 أحياناً", 1), ("📖 ليس كل يوم", 2), ("✅ كل يوم", 3)]),
        ("3️⃣ هل تخطط يومك؟", [("🌊 أسير بلا خطة", 0), ("💭 في رأسي", 1), ("📝 أكتب أحياناً", 2), ("⭐️ قائمة بعد الفجر يومياً", 3)]),
        ("4️⃣ هل تقوم بالمحاسبة مساءً؟", [("❓ ما هي؟", 0), ("💭 أحياناً", 1), ("🔄 جربت وتوقفت", 2), ("✅ كل مساء", 3)]),
        ("5️⃣ كيف علاقتك بالهاتف صباحاً؟", [("📱 الهاتف يتحكم بي", 0), ("🔄 أحاول التقليل", 1), ("⚖️ لدي قواعد وأتعثر", 2), ("✅ أتحكم به", 3)]),
        ("6️⃣ هل تقرأ القرآن؟", [("❌ لا أقرأ", 0), ("🌙 في المناسبات", 1), ("📖 أحياناً أسبوعياً", 2), ("✅ كل يوم", 3)]),
        ("7️⃣ كيف عملك أو تجارتك؟", [("🌀 فوضى كاملة", 0), ("⚙️ بلا نظام", 1), ("📊 يوجد نظام بلا بركة كافية", 2), ("✨ أبحث عن المعنى", 3)]),
        ("8️⃣ كيف حال أسرتك؟", [("🏃 نادراً ما أكون في البيت", 0), ("📱 في البيت لكن مع الهاتف", 1), ("❤️ أهتم وأريد أكثر", 2), ("🏠 الأسرة حصني", 3)]),
    ],
    "de": [
        ("1️⃣ Stehst du zum Fajr auf?", [("😔 Nie", 0), ("🔄 Manchmal", 1), ("✅ Regelmäßig", 2), ("⭐️ Immer + Tahajjud", 3)]),
        ("2️⃣ Liest du Morgen-Adhkar?", [("❌ Nein", 0), ("🔄 Manchmal", 1), ("📖 Nicht täglich", 2), ("✅ Jeden Tag", 3)]),
        ("3️⃣ Planst du deinen Tag?", [("🌊 Ich lasse es laufen", 0), ("💭 Im Kopf", 1), ("📝 Manchmal schriftlich", 2), ("⭐️ Fajr-Liste täglich", 3)]),
        ("4️⃣ Machst du abends Muhasabah?", [("❓ Was ist das?", 0), ("💭 Manchmal", 1), ("🔄 Versucht, aufgehört", 2), ("✅ Jeden Abend", 3)]),
        ("5️⃣ Wie ist dein Handy morgens?", [("📱 Handy kontrolliert mich", 0), ("🔄 Ich begrenze es", 1), ("⚖️ Regeln, aber Ausrutscher", 2), ("✅ Ich kontrolliere es", 3)]),
        ("6️⃣ Liest du Qur'an?", [("❌ Nein", 0), ("🌙 An besonderen Tagen", 1), ("📖 Manchmal wöchentlich", 2), ("✅ Jeden Tag", 3)]),
        ("7️⃣ Wie ist Arbeit oder Business?", [("🌀 Totales Chaos", 0), ("⚙️ Kein System", 1), ("📊 System, wenig Barakah", 2), ("✨ Suche Sinn", 3)]),
        ("8️⃣ Wie ist deine Familie?", [("🏃 Kaum zuhause", 0), ("📱 Zuhause, aber am Handy", 1), ("❤️ Ich gebe Zeit, will mehr", 2), ("🏠 Familie ist meine Festung", 3)]),
    ],
}

DIAG_QUESTIONS.update({
    "tr": [
        ("1️⃣ Sabah namazına kalkıyor musun?", [("😔 Hiç", 0), ("🔄 Bazen", 1), ("✅ Düzenli", 2), ("⭐️ Her zaman + teheccüd", 3)]),
        ("2️⃣ Sabah zikirlerini okuyor musun?", [("❌ Okumuyorum", 0), ("🔄 Bazen", 1), ("📖 Her gün değil", 2), ("✅ Her gün", 3)]),
        ("3️⃣ Gününü planlıyor musun?", [("🌊 Akışına bırakıyorum", 0), ("💭 Aklımda", 1), ("📝 Bazen yazıyorum", 2), ("⭐️ Her gün Fajr listesi", 3)]),
        ("4️⃣ Akşam muhasebesi yapıyor musun?", [("❓ Bu nedir?", 0), ("💭 Bazen", 1), ("🔄 Denedim bıraktım", 2), ("✅ Her akşam", 3)]),
        ("5️⃣ Sabah telefon kullanımın nasıl?", [("📱 Telefon beni yönetiyor", 0), ("🔄 Sınırlamaya çalışıyorum", 1), ("⚖️ Kurallar var ama bozuluyor", 2), ("✅ Kontrol bende", 3)]),
        ("6️⃣ Kur'an okuyor musun?", [("❌ Okumuyorum", 0), ("🌙 Özel günlerde", 1), ("📖 Haftada bazen", 2), ("✅ Her gün", 3)]),
        ("7️⃣ İşin veya ticaretin nasıl?", [("🌀 Tam kaos", 0), ("⚙️ Sistem yok", 1), ("📊 Sistem var, bereket az", 2), ("✨ Anlam arıyorum", 3)]),
        ("8️⃣ Aile hayatın nasıl?", [("🏃 Eve az geliyorum", 0), ("📱 Evdeyim ama telefondayım", 1), ("❤️ Zaman ayırıyorum, artırmak istiyorum", 2), ("🏠 Ailem kalemdir", 3)]),
    ],
    "id": [
        ("1️⃣ Apakah kamu bangun untuk Subuh?", [("😔 Tidak pernah", 0), ("🔄 Kadang-kadang", 1), ("✅ Rutin", 2), ("⭐️ Selalu + tahajjud", 3)]),
        ("2️⃣ Apakah membaca dzikir pagi?", [("❌ Tidak", 0), ("🔄 Kadang", 1), ("📖 Tidak setiap hari", 2), ("✅ Setiap hari", 3)]),
        ("3️⃣ Apakah merencanakan harimu?", [("🌊 Mengalir saja", 0), ("💭 Di kepala", 1), ("📝 Kadang ditulis", 2), ("⭐️ Daftar setelah Subuh setiap hari", 3)]),
        ("4️⃣ Apakah melakukan muhasabah malam?", [("❓ Apa itu?", 0), ("💭 Kadang", 1), ("🔄 Pernah coba lalu berhenti", 2), ("✅ Setiap malam", 3)]),
        ("5️⃣ Bagaimana penggunaan HP di pagi hari?", [("📱 HP mengendalikan saya", 0), ("🔄 Saya coba batasi", 1), ("⚖️ Ada aturan tapi sering gagal", 2), ("✅ Saya mengendalikan", 3)]),
        ("6️⃣ Apakah membaca Al-Qur'an?", [("❌ Tidak", 0), ("🌙 Pada hari tertentu", 1), ("📖 Kadang tiap minggu", 2), ("✅ Setiap hari", 3)]),
        ("7️⃣ Bagaimana kerja atau bisnismu?", [("🌀 Sangat kacau", 0), ("⚙️ Tanpa sistem", 1), ("📊 Ada sistem, kurang barakah", 2), ("✨ Mencari makna", 3)]),
        ("8️⃣ Bagaimana kehidupan keluargamu?", [("🏃 Jarang di rumah", 0), ("📱 Di rumah tapi di HP", 1), ("❤️ Peduli, ingin lebih", 2), ("🏠 Keluarga adalah bentengku", 3)]),
    ],
    "ur": [
        ("1️⃣ کیا آپ فجر کے لیے اٹھتے ہیں؟", [("😔 کبھی نہیں", 0), ("🔄 کبھی کبھی", 1), ("✅ باقاعدگی سے", 2), ("⭐️ ہمیشہ + تہجد", 3)]),
        ("2️⃣ کیا آپ صبح کے اذکار پڑھتے ہیں؟", [("❌ نہیں پڑھتا", 0), ("🔄 کبھی کبھی", 1), ("📖 روز نہیں", 2), ("✅ ہر روز", 3)]),
        ("3️⃣ کیا آپ اپنے دن کی منصوبہ بندی کرتے ہیں؟", [("🌊 جیسے چلتا ہے", 0), ("💭 ذہن میں", 1), ("📝 کبھی لکھتا ہوں", 2), ("⭐️ ہر روز فجر لسٹ", 3)]),
        ("4️⃣ کیا آپ شام کو محاسبہ کرتے ہیں؟", [("❓ یہ کیا ہے؟", 0), ("💭 کبھی کبھی", 1), ("🔄 آزمایا، پھر چھوڑ دیا", 2), ("✅ ہر شام", 3)]),
        ("5️⃣ صبح فون کے ساتھ آپ کا حال کیسا ہے؟", [("📱 فون مجھے کنٹرول کرتا ہے", 0), ("🔄 محدود کرنے کی کوشش کرتا ہوں", 1), ("⚖️ اصول ہیں مگر ٹوٹ جاتے ہیں", 2), ("✅ کنٹرول میرے پاس ہے", 3)]),
        ("6️⃣ کیا آپ قرآن پڑھتے ہیں؟", [("❌ نہیں", 0), ("🌙 خاص دنوں پر", 1), ("📖 ہفتے میں کبھی", 2), ("✅ ہر روز", 3)]),
        ("7️⃣ آپ کا کام یا کاروبار کیسا ہے؟", [("🌀 مکمل بے ترتیبی", 0), ("⚙️ کوئی نظام نہیں", 1), ("📊 نظام ہے مگر برکت کم", 2), ("✨ معنی تلاش کر رہا ہوں", 3)]),
        ("8️⃣ آپ کے گھر/خاندان کا حال کیسا ہے؟", [("🏃 گھر میں کم ہوتا ہوں", 0), ("📱 گھر میں ہوں مگر فون پر", 1), ("❤️ وقت دیتا ہوں، مزید چاہتا ہوں", 2), ("🏠 خاندان میری طاقت ہے", 3)]),
    ],
    "bn": [
        ("1️⃣ আপনি কি ফজরের জন্য ওঠেন?", [("😔 কখনও না", 0), ("🔄 মাঝে মাঝে", 1), ("✅ নিয়মিত", 2), ("⭐️ সবসময় + তাহাজ্জুদ", 3)]),
        ("2️⃣ আপনি কি সকালের আজকার পড়েন?", [("❌ পড়ি না", 0), ("🔄 মাঝে মাঝে", 1), ("📖 প্রতিদিন নয়", 2), ("✅ প্রতিদিন", 3)]),
        ("3️⃣ আপনি কি দিনের পরিকল্পনা করেন?", [("🌊 যেমন চলে", 0), ("💭 মাথায় রাখি", 1), ("📝 মাঝে মাঝে লিখি", 2), ("⭐️ প্রতিদিন ফজর-লিস্ট", 3)]),
        ("4️⃣ রাতে মুহাসাবা করেন?", [("❓ এটা কী?", 0), ("💭 মাঝে মাঝে", 1), ("🔄 চেষ্টা করে ছেড়েছি", 2), ("✅ প্রতিরাতে", 3)]),
        ("5️⃣ সকালে ফোন ব্যবহারে আপনার অবস্থা?", [("📱 ফোন আমাকে নিয়ন্ত্রণ করে", 0), ("🔄 কমানোর চেষ্টা করি", 1), ("⚖️ নিয়ম আছে, ভেঙে যায়", 2), ("✅ আমি নিয়ন্ত্রণ করি", 3)]),
        ("6️⃣ আপনি কি কুরআন পড়েন?", [("❌ পড়ি না", 0), ("🌙 বিশেষ দিনে", 1), ("📖 সপ্তাহে মাঝে মাঝে", 2), ("✅ প্রতিদিন", 3)]),
        ("7️⃣ আপনার কাজ বা ব্যবসা কেমন?", [("🌀 পুরো বিশৃঙ্খলা", 0), ("⚙️ সিস্টেম নেই", 1), ("📊 সিস্টেম আছে, বারাকাহ কম", 2), ("✨ অর্থ খুঁজছি", 3)]),
        ("8️⃣ আপনার পরিবার জীবন কেমন?", [("🏃 বাড়িতে কম থাকি", 0), ("📱 বাড়িতে থাকি, কিন্তু ফোনে", 1), ("❤️ সময় দিই, আরও চাই", 2), ("🏠 পরিবার আমার দুর্গ", 3)]),
    ],
    "fr": [
        ("1️⃣ Te lèves-tu pour Fajr ?", [("😔 Jamais", 0), ("🔄 Parfois", 1), ("✅ Régulièrement", 2), ("⭐️ Toujours + tahajjud", 3)]),
        ("2️⃣ Lis-tu les adhkar du matin ?", [("❌ Non", 0), ("🔄 Parfois", 1), ("📖 Pas chaque jour", 2), ("✅ Chaque jour", 3)]),
        ("3️⃣ Planifies-tu ta journée ?", [("🌊 Je laisse faire", 0), ("💭 Dans ma tête", 1), ("📝 J'écris parfois", 2), ("⭐️ Liste après Fajr chaque jour", 3)]),
        ("4️⃣ Fais-tu la muhasabah le soir ?", [("❓ C'est quoi ?", 0), ("💭 Parfois", 1), ("🔄 J'ai essayé puis arrêté", 2), ("✅ Chaque soir", 3)]),
        ("5️⃣ Ton téléphone le matin ?", [("📱 Il me contrôle", 0), ("🔄 J'essaie de limiter", 1), ("⚖️ J'ai des règles mais je dérape", 2), ("✅ Je contrôle", 3)]),
        ("6️⃣ Lis-tu le Coran ?", [("❌ Non", 0), ("🌙 Aux occasions", 1), ("📖 Parfois dans la semaine", 2), ("✅ Chaque jour", 3)]),
        ("7️⃣ Ton travail ou business ?", [("🌀 Chaos total", 0), ("⚙️ Pas de système", 1), ("📊 Système présent, peu de barakah", 2), ("✨ Je cherche du sens", 3)]),
        ("8️⃣ Ta vie de famille ?", [("🏃 Presque jamais à la maison", 0), ("📱 Présent mais sur le téléphone", 1), ("❤️ Je donne du temps, je veux plus", 2), ("🏠 Ma famille est ma forteresse", 3)]),
    ],
    "ms": [
        ("1️⃣ Adakah anda bangun untuk Subuh?", [("😔 Tidak pernah", 0), ("🔄 Kadang-kadang", 1), ("✅ Secara tetap", 2), ("⭐️ Sentiasa + tahajjud", 3)]),
        ("2️⃣ Adakah anda membaca zikir pagi?", [("❌ Tidak", 0), ("🔄 Kadang-kadang", 1), ("📖 Tidak setiap hari", 2), ("✅ Setiap hari", 3)]),
        ("3️⃣ Adakah anda merancang hari anda?", [("🌊 Ikut sahaja", 0), ("💭 Dalam kepala", 1), ("📝 Kadang-kadang tulis", 2), ("⭐️ Senarai selepas Subuh setiap hari", 3)]),
        ("4️⃣ Adakah anda buat muhasabah malam?", [("❓ Apa itu?", 0), ("💭 Kadang-kadang", 1), ("🔄 Pernah cuba lalu berhenti", 2), ("✅ Setiap malam", 3)]),
        ("5️⃣ Bagaimana penggunaan telefon pada waktu pagi?", [("📱 Telefon mengawal saya", 0), ("🔄 Saya cuba hadkan", 1), ("⚖️ Ada aturan tapi gagal", 2), ("✅ Saya mengawal", 3)]),
        ("6️⃣ Adakah anda membaca Al-Quran?", [("❌ Tidak", 0), ("🌙 Pada hari tertentu", 1), ("📖 Kadang-kadang setiap minggu", 2), ("✅ Setiap hari", 3)]),
        ("7️⃣ Bagaimana kerja atau bisnes anda?", [("🌀 Sangat kelam-kabut", 0), ("⚙️ Tiada sistem", 1), ("📊 Ada sistem, kurang barakah", 2), ("✨ Mencari makna", 3)]),
        ("8️⃣ Bagaimana kehidupan keluarga anda?", [("🏃 Jarang di rumah", 0), ("📱 Di rumah tapi dengan telefon", 1), ("❤️ Beri masa, mahu lebih", 2), ("🏠 Keluarga benteng saya", 3)]),
    ],
})


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


def diag_question(lang: str | None, idx: int) -> tuple[str, list[tuple[str, int]]]:
    lang = normalize_lang(lang)
    questions = DIAG_QUESTIONS.get(lang) or DIAG_QUESTIONS["ru"]
    return questions[idx]


def diag_result(lang: str | None, score: int) -> dict[str, str | int]:
    pct = round(score / (8 * 3) * 100)
    if pct <= 25:
        key = "a"
        emoji = "🔴"
    elif pct <= 50:
        key = "b"
        emoji = "🔵"
    else:
        key = "c"
        emoji = "💚" if pct <= 75 else "⭐️"

    return {
        "level_key": {"a": "А", "b": "Б", "c": "В"}[key],
        "pct": pct,
        "emoji": emoji,
        "level": t(lang, f"diag.level_{key}"),
        "intro": t(lang, f"diag.intro_{key}"),
        "path": t(lang, f"diag.path_{key}"),
    }
