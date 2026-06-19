# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Режим работы

Делай сам без запроса разрешения:
- Любые правки кода и файлов
- git commit и git push
- Деплой на Amvera
- Мелкие фиксы и улучшения

Спрашивай разрешения ТОЛЬКО в этих случаях:
- Необратимые действия (удаление данных, очистка базы)
- Кардинальная смена архитектуры бота
- Изменение платёжных настроек / ЮKassa
- Два равноценных пути — выбор направления за тобой

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)

## Repository layout

The repo has two roots:
- **`bot_v2/`** — active Telegram bot (tracked in git root, deployed via `amvera_v2.yml`)
- **`ACTIVE/`** — everything else: site, miniapp, CRM, legacy bot. Deployed via `ACTIVE/amvera.yml`

Key subdirectories:
```
bot_v2/          # aiogram 3.x bot — the primary product
  config.py      # loads env vars; BOT_TOKEN, DATABASE_URL, CURATOR_ID required
  main.py        # entry point; registers routers + APScheduler jobs
  db/
    models.py    # SQLAlchemy ORM: User, Participant, Payment, DiagResult, MuhasabaLog, WeekAck, TrackerRecord, WheelRecord
    engine.py    # async SQLAlchemy engine + session factory
    repositories/  # UserRepo, ParticipantRepo, PaymentRepo, SettingsRepo
  handlers/      # aiogram routers: start, program, curator, payments, jarwas, muhasaba, korablik, miniapp, diagnostics
  services/      # business logic: program.py, i18n.py, jarwas.py, insights.py, jobs.py (scheduled), yookassa_svc.py
  keyboards/inline.py
  middlewares/db.py  # injects async DB session into handler context
  migrations/    # Alembic; versions 001-003

ACTIVE/
  site/          # Static HTML landing pages (iq-barakah.ru); journey-lang.js drives i18n
  miniapp/       # Vite JS Telegram Mini App (src/app.js entry; screens: home, lessons, tracker, wheel, ship)
  crm/           # FastAPI + Jinja CRM dashboard reading bot_v2 DB
  crm_dashboard/ # Older CRM variant
  bot_v1_legacy/ # Deprecated single-file bot (do not touch)
```

## Running the bot locally

```bash
cd bot_v2
BOT_TOKEN=... DATABASE_URL=postgresql+asyncpg://... CURATOR_ID=140700248 python -m bot_v2.main
```

## DB migrations (Alembic)

```bash
cd bot_v2
alembic -c migrations/alembic.ini upgrade head
# generate new migration:
alembic -c migrations/alembic.ini revision --autogenerate -m "description"
```

## Miniapp (Vite)

```bash
cd ACTIVE/miniapp
npm install
npm run dev        # dev server
npm run build      # production build
python build_standalone.py  # bundle into single HTML for Telegram Mini App
```

## Deployment (Amvera)

- Bot: `git push amvera` — uses `amvera_v2.yml` (`run: python -m bot_v2.main`, persistence at `/data`)
- Site/miniapp: separate Amvera project using `ACTIVE/amvera.yml`

## Architecture notes

**Bot data flow:** Every handler receives an async DB session via `DbSessionMiddleware`. Repositories (`UserRepo`, `ParticipantRepo`, etc.) are thin wrappers over SQLAlchemy async sessions. Never bypass the repository layer to issue raw SQL.

**Program levels:** Users join at level А/Б/В/Г (field `Participant.level`). `services/program.py` computes what content to send based on level + week. Content is in `services/content_s1.py` / `content_s2.py` / `content_s3.py`.

**ВАКТ track:** Separate spiritual practice track with its own level (`Participant.vakt_level`) and content in `services/content_vakt.py`.

**Scheduled jobs (APScheduler):** `services/jobs.py` — jarwas fajr/friday push, silence checks, progress mirrors, payment follow-ups. Registered in `main.py`.

**i18n:** `services/i18n.py` for bot strings (ru/ar/tr/en). Site i18n handled by `ACTIVE/site/journey-lang.js`.

**Payments:** YooKassa integration via `services/yookassa_svc.py`. Payment webhook handled in `handlers/payments.py`. Changing payment config requires explicit permission (see Режим работы above).

**CRM:** `ACTIVE/crm/` is a FastAPI/Jinja app that reads the same PostgreSQL DB as the bot. It is a separate process with its own `requirements.txt`. See `ACTIVE/crm/ARCHITECTURE.md` for roadmap.

## CRM safety zone — НЕ ТРОГАТЬ без согласования

Параллельно настраивается IQ Barakah CRM и второй сервис. Они используют ту же PostgreSQL БД.

**Можно менять свободно:**
- `bot_v2/` — вся логика бота, handlers, services, keyboards
- `BOT_TOKEN`, `YOOKASSA_SECRET_KEY`, `ANTHROPIC_API_KEY`
- Баги double `session.commit()` в handlers бота
- Тексты, сценарии, команды бота

**НЕ ТРОГАТЬ без явного согласования:**
- `ACTIVE/crm/` — любые файлы CRM
- `DATABASE_URL` и пароль PostgreSQL
- Структуру таблиц БД (миграции ALTER TABLE, DROP)
- `root crm-bridge.js`, `root index.html`
- Настройки routing `/api/*`, порты `8765`, `8788`

Если нужно менять DATABASE_URL, пароль БД или общие таблицы — **остановиться и спросить**.
