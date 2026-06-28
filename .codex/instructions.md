# Codex — зоны ответственности

## ✅ Можно трогать
- ACTIVE/crm/
- ACTIVE/crm_dashboard/

## ❌ НЕЛЬЗЯ трогать (никогда, без явного запроса)
- ACTIVE/miniapp.html — боевой мини-апп, сложная логика
- ACTIVE/site/*.html — лендинги сайта
- bot_v2/ — Telegram бот (handlers, services, keyboards, migrations)
- amvera_v2.yml
- .gitignore

Если задача требует изменений вне CRM — остановись и сообщи.

---

# CRM — полная карта

## Стек
- FastAPI + Jinja2 + uvicorn
- PostgreSQL (та же БД что и у бота bot_v2)
- Хранилище JSON: ACTIVE/crm/storage/business_os.json, crm_users.json
- Деплой: ACTIVE/amvera.yml → git push amvera deploy-v2:master

## Файлы
```
ACTIVE/crm/
  main.py              — весь бэкенд (маршруты, логика, Jinja рендеринг)
  requirements.txt
  templates/
    base.html          — шапка, навигация, общий layout
    dashboard.html     — главная / (вкладки: обзор, воронка, финансы, команда, задачи)
    students.html      — список учеников /students
    student_detail.html — карточка ученика /students/{id}
    jarwas_stats.html  — аналитика Джарваса /jarwas
    login.html         — /login
    task_detail.html   — /tasks/{id}
    business_*.html    — CRM: клиенты, лиды, сделки, кэшфлоу
    _students_table.html — partial таблицы учеников
  static/
    styles.css         — все стили CRM
  storage/
    business_os.json   — оперативные данные CRM (клиенты, лиды, сделки, кэшфлоу, задачи, команда, календарь)
    crm_users.json     — пользователи CRM (логин/пароль-хэш/роль)
```

## Маршруты
| Метод | URL | Описание |
|-------|-----|----------|
| GET | / | Дашборд (вкладки: обзор, воронка, финансы, команда, задачи) |
| GET | /students | Список учеников бота |
| GET | /students/{id} | Карточка ученика |
| GET | /jarwas | Аналитика диагностики Джарваса |
| GET | /tasks/{id} | Детали задачи |
| GET | /business/clients/{id} | Детали клиента |
| GET | /business/leads/{id} | Детали лида |
| GET | /business/deals/{id} | Детали сделки |
| GET | /business/cashflow/{id} | Детали операции кэшфлоу |
| GET | /api/dashboard.json | JSON данные дашборда |
| POST | /tasks | Создать задачу |
| POST | /business/clients | Создать клиента |
| POST | /business/leads | Создать лид |
| POST | /business/deals | Создать сделку |
| POST | /business/cashflow | Создать операцию |
| POST | /login /logout | Авторизация |

## Навигация (base.html)
Обзор → /
Ученики → /students
Джарвас → /jarwas

## Джарвас (/jarwas)
- Тянет данные с бота: GET https://iq-barakah-v2-rashidiq.amvera.io/stats
- Показывает: всего анализов, сегодня, успешно/ошибок, средний балл, бизнес/жизнь, UTM-источники, последние 20 записей
- Данные хранятся на боте в /data/analyze_stats.log

## База данных (читает из bot_v2 БД)
Основные модели: User, Participant, Payment, DiagResult, MuhasabaLog, WeekAck, TrackerRecord, WheelRecord
Подключение через DATABASE_URL env var (postgresql+asyncpg://...)

## Авторизация
- Сессия через cookie session_token
- Пользователи в storage/crm_users.json
- Роли: owner, admin, manager

## Добавить новую вкладку/страницу — шаблон
1. Создать templates/my_page.html (extends "base.html")
2. Добавить маршрут в main.py: @app.get("/my-page", response_class=HTMLResponse)
3. Добавить ссылку в templates/base.html в блок <nav>
