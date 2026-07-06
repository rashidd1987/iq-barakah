from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict
from pathlib import Path
import jwt, bcrypt, os, asyncpg, time, secrets, json

SECRET = os.environ.get('JWT_SECRET', 'change-me-in-production')
DATABASE_URL = os.environ.get('DATABASE_URL', '')
ALGORITHM = 'HS256'
TOKEN_EXPIRE_DAYS = 30

app = FastAPI(title='IQ Barakah PWA API')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

# ── Rate limiting ─────────────────────────────────────────────────────────────
_rate_store: Dict[str, List[float]] = defaultdict(list)
RATE_LIMITS = {
    '/auth/login': (10, 60),     # 10 req / 60s
    '/auth/register': (5, 60),   # 5 req / 60s
    'default': (120, 60),        # 120 req / 60s
}

@app.middleware('http')
async def rate_limit_middleware(request: Request, call_next):
    ip = request.client.host if request.client else 'unknown'
    path = request.url.path
    limit, window = RATE_LIMITS.get(path, RATE_LIMITS['default'])
    key = f'{ip}:{path}'
    now = time.time()
    hits = _rate_store[key]
    _rate_store[key] = [t for t in hits if now - t < window]
    if len(_rate_store[key]) >= limit:
        return JSONResponse({'detail': 'Too many requests'}, status_code=429)
    _rate_store[key].append(now)
    return await call_next(request)

security = HTTPBearer()
db_pool: asyncpg.Pool = None

async def _init_connection(conn: asyncpg.Connection):
    # Without this, asyncpg hands back/expects raw JSON text for json/jsonb columns
    # instead of Python dicts — every JSONB read/write in this file relies on the codec.
    await conn.set_type_codec(
        'jsonb', encoder=json.dumps, decoder=json.loads, schema='pg_catalog'
    )
    await conn.set_type_codec(
        'json', encoder=json.dumps, decoder=json.loads, schema='pg_catalog'
    )

@app.on_event('startup')
async def startup():
    global db_pool
    if DATABASE_URL:
        try:
            db_pool = await asyncpg.create_pool(DATABASE_URL.replace('+asyncpg', ''), init=_init_connection)
            print('DB connected OK')
            await _run_migrations()
        except Exception as e:
            print(f'DB connection failed: {e} — running without DB')

async def _run_migrations():
    stmts = [
        '''CREATE TABLE IF NOT EXISTS pwa_users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            tg_id BIGINT UNIQUE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )''',
        '''CREATE TABLE IF NOT EXISTS pwa_tracker (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL REFERENCES pwa_users(id) ON DELETE CASCADE,
            date DATE NOT NULL,
            data JSONB NOT NULL DEFAULT '{}',
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, date)
        )''',
        '''CREATE TABLE IF NOT EXISTS pwa_wheel (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL REFERENCES pwa_users(id) ON DELETE CASCADE,
            scores JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )''',
        '''CREATE TABLE IF NOT EXISTS pwa_ship (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL REFERENCES pwa_users(id) ON DELETE CASCADE,
            type TEXT NOT NULL,
            scores JSONB NOT NULL DEFAULT '{}',
            avg FLOAT NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )''',
        '''CREATE TABLE IF NOT EXISTS pwa_analytics (
            id BIGSERIAL PRIMARY KEY,
            uid TEXT NOT NULL,
            event TEXT NOT NULL,
            screen TEXT,
            ts TIMESTAMP NOT NULL DEFAULT NOW()
        )''',
        'CREATE INDEX IF NOT EXISTS idx_pwa_tracker_user_date ON pwa_tracker(user_id, date)',
        'CREATE INDEX IF NOT EXISTS idx_pwa_wheel_user ON pwa_wheel(user_id)',
        'CREATE INDEX IF NOT EXISTS idx_pwa_ship_user ON pwa_ship(user_id)',
        'CREATE INDEX IF NOT EXISTS idx_pwa_analytics_uid ON pwa_analytics(uid)',
        '''CREATE TABLE IF NOT EXISTS pwa_tg_sessions (
            session_id TEXT PRIMARY KEY,
            tg_id BIGINT,
            tg_name TEXT,
            confirmed BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )''',
        # Mobile app push tokens. Keyed by bot_v2 users.id (tg_id) — not pwa_users — since
        # the mobile app reads/writes bot_v2's real program tables directly (see /mobile/*).
        '''CREATE TABLE IF NOT EXISTS push_tokens (
            user_id BIGINT PRIMARY KEY,
            expo_token TEXT NOT NULL,
            platform TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )''',
    ]
    async with db_pool.acquire() as conn:
        for stmt in stmts:
            try:
                await conn.execute(stmt)
            except Exception as e:
                print(f'Migration note: {e}')
    print('Migration OK')

# ── Models ────────────────────────────────────────────────────────────────────

class LoginReq(BaseModel):
    email: str
    password: str

class RegisterReq(BaseModel):
    name: str
    email: str
    password: str

class TrackerReq(BaseModel):
    date: str
    data: dict

class WheelReq(BaseModel):
    scores: dict

class ShipReq(BaseModel):
    type: str  # biz | per
    scores: dict
    avg: float

# ── Auth helpers ──────────────────────────────────────────────────────────────

def make_token(user_id: int, email: str) -> str:
    payload = {
        'sub': str(user_id),
        'email': email,
        'exp': datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)

def verify_token(creds: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(creds.credentials, SECRET, algorithms=[ALGORITHM])
        return int(payload['sub'])
    except Exception:
        raise HTTPException(status_code=401, detail='Токен недействителен')

# ── Routes ────────────────────────────────────────────────────────────────────

@app.post('/auth/register')
async def register(req: RegisterReq):
    if not db_pool:
        raise HTTPException(500, 'База данных не подключена')
    hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    async with db_pool.acquire() as conn:
        existing = await conn.fetchrow('SELECT id FROM pwa_users WHERE email=$1', req.email.lower())
        if existing:
            raise HTTPException(400, 'Email уже зарегистрирован')
        row = await conn.fetchrow(
            'INSERT INTO pwa_users (name, email, password_hash, created_at) VALUES ($1,$2,$3,$4) RETURNING id',
            req.name, req.email.lower(), hashed, datetime.utcnow()
        )
    token = make_token(row['id'], req.email)
    return {'access_token': token, 'token_type': 'bearer'}

@app.post('/auth/login')
async def login(req: LoginReq):
    if not db_pool:
        raise HTTPException(500, 'База данных не подключена')
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow('SELECT id, password_hash FROM pwa_users WHERE email=$1', req.email.lower())
    if not user or not bcrypt.checkpw(req.password.encode(), user['password_hash'].encode()):
        raise HTTPException(401, 'Неверный email или пароль')
    return {'access_token': make_token(user['id'], req.email), 'token_type': 'bearer'}

@app.get('/me')
async def me(user_id: int = Depends(verify_token)):
    if not db_pool:
        return {'id': user_id, 'name': 'Пользователь'}
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow('SELECT id, name, email, created_at FROM pwa_users WHERE id=$1', user_id)
    if not user:
        raise HTTPException(404, 'Пользователь не найден')
    return dict(user)

@app.get('/progress')
async def progress(user_id: int = Depends(verify_token)):
    if not db_pool:
        return {'week': 1, 'tracker': {}, 'wheel': {}, 'ship': {}}
    async with db_pool.acquire() as conn:
        tracker = await conn.fetch('SELECT date, data FROM pwa_tracker WHERE user_id=$1 ORDER BY date DESC LIMIT 30', user_id)
        wheel   = await conn.fetchrow('SELECT scores FROM pwa_wheel WHERE user_id=$1 ORDER BY created_at DESC LIMIT 1', user_id)
        ship    = await conn.fetch('SELECT type, scores, avg, created_at FROM pwa_ship WHERE user_id=$1 ORDER BY created_at DESC LIMIT 2', user_id)
    return {
        'tracker': {r['date']: r['data'] for r in tracker},
        'wheel':   dict(wheel['scores']) if wheel else {},
        'ship':    [dict(r) for r in ship],
    }

@app.post('/tracker')
async def save_tracker(req: TrackerReq, user_id: int = Depends(verify_token)):
    if not db_pool:
        return {'ok': True}
    async with db_pool.acquire() as conn:
        await conn.execute(
            '''INSERT INTO pwa_tracker (user_id, date, data, updated_at)
               VALUES ($1,$2,$3,$4)
               ON CONFLICT (user_id, date) DO UPDATE SET data=$3, updated_at=$4''',
            user_id, req.date, req.data, datetime.utcnow()
        )
    return {'ok': True}

@app.post('/wheel')
async def save_wheel(req: WheelReq, user_id: int = Depends(verify_token)):
    if not db_pool:
        return {'ok': True}
    async with db_pool.acquire() as conn:
        await conn.execute(
            'INSERT INTO pwa_wheel (user_id, scores, created_at) VALUES ($1,$2,$3)',
            user_id, req.scores, datetime.utcnow()
        )
    return {'ok': True}

@app.post('/ship')
async def save_ship(req: ShipReq, user_id: int = Depends(verify_token)):
    if not db_pool:
        return {'ok': True}
    async with db_pool.acquire() as conn:
        await conn.execute(
            'INSERT INTO pwa_ship (user_id, type, scores, avg, created_at) VALUES ($1,$2,$3,$4,$5)',
            user_id, req.type, req.scores, req.avg, datetime.utcnow()
        )
    return {'ok': True}

@app.delete('/me')
async def delete_account(user_id: int = Depends(verify_token)):
    if not db_pool:
        return {'ok': True}
    async with db_pool.acquire() as conn:
        await conn.execute('DELETE FROM pwa_tracker WHERE user_id=$1', user_id)
        await conn.execute('DELETE FROM pwa_wheel WHERE user_id=$1', user_id)
        await conn.execute('DELETE FROM pwa_ship WHERE user_id=$1', user_id)
        await conn.execute('DELETE FROM pwa_analytics WHERE uid IN (SELECT $1::text)', str(user_id))
        await conn.execute('DELETE FROM pwa_users WHERE id=$1', user_id)
    return {'ok': True}

@app.get('/run-migrate')
async def run_migrate():
    if not db_pool:
        return {'error': 'no db pool'}
    await _run_migrations()
    return {'ok': True}

@app.get('/health')
async def health():
    db_ok = db_pool is not None
    db_url_set = bool(DATABASE_URL)
    return {'status': 'ok', 'db_connected': db_ok, 'db_url_set': db_url_set}

# ── Telegram Login ────────────────────────────────────────────────────────────

BOT_SECRET = os.environ.get('BOT_SECRET', 'pwa-internal-secret')

@app.post('/auth/tg-init')
async def tg_init():
    """PWA вызывает при нажатии кнопки. Возвращает session_id для polling."""
    if not db_pool:
        raise HTTPException(500, 'База данных не подключена')
    session_id = secrets.token_urlsafe(16)
    async with db_pool.acquire() as conn:
        await conn.execute(
            'INSERT INTO pwa_tg_sessions (session_id, created_at) VALUES ($1, $2)',
            session_id, datetime.utcnow()
        )
    return {'session_id': session_id}

@app.get('/auth/tg-check')
async def tg_check(session_id: str):
    """PWA поллит каждые 2 сек. Возвращает токен когда пользователь подтвердил в боте."""
    if not db_pool:
        raise HTTPException(500, 'База данных не подключена')
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT tg_id, tg_name, confirmed, created_at FROM pwa_tg_sessions WHERE session_id=$1',
            session_id
        )
    if not row:
        raise HTTPException(404, 'Сессия не найдена')
    # Истекла через 10 минут
    if (datetime.utcnow() - row['created_at']).total_seconds() > 600:
        raise HTTPException(410, 'Сессия истекла')
    if not row['confirmed']:
        return {'status': 'pending'}
    # Найти или создать pwa_user по tg_id
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow('SELECT id, email FROM pwa_users WHERE tg_id=$1', row['tg_id'])
        if not user:
            # Автосоздание аккаунта
            email = f"tg_{row['tg_id']}@iq-barakah.ru"
            user = await conn.fetchrow(
                '''INSERT INTO pwa_users (name, email, password_hash, tg_id, created_at)
                   VALUES ($1,$2,$3,$4,$5) RETURNING id, email''',
                row['tg_name'] or 'Участник', email, '', row['tg_id'], datetime.utcnow()
            )
    token = make_token(user['id'], user['email'])
    return {'status': 'ok', 'access_token': token, 'token_type': 'bearer'}

class TgConfirmReq(BaseModel):
    session_id: str
    tg_id: int
    tg_name: str
    secret: str

@app.post('/auth/tg-confirm')
async def tg_confirm(req: TgConfirmReq):
    """Бот вызывает этот эндпоинт когда пользователь нажал «Подтвердить» в Telegram."""
    if req.secret != BOT_SECRET:
        raise HTTPException(403, 'Forbidden')
    if not db_pool:
        raise HTTPException(500, 'База данных не подключена')
    async with db_pool.acquire() as conn:
        await conn.execute(
            'UPDATE pwa_tg_sessions SET tg_id=$1, tg_name=$2, confirmed=TRUE WHERE session_id=$3',
            req.tg_id, req.tg_name, req.session_id
        )
    return {'ok': True}

@app.get('/debug/db')
async def debug_db():
    if not db_pool:
        return {'db': 'not connected', 'url_set': bool(DATABASE_URL), 'url_prefix': DATABASE_URL[:40] if DATABASE_URL else None}
    try:
        async with db_pool.acquire() as conn:
            tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'pwa_%'")
            return {'db': 'connected', 'pwa_tables': [r['tablename'] for r in tables]}
    except Exception as e:
        return {'db': 'error', 'error': str(e)}

# ── Analytics ─────────────────────────────────────────────────────────────────

class AnalyticsEvent(BaseModel):
    e: str
    uid: str
    ts: int
    screen: Optional[str] = None

class AnalyticsBatch(BaseModel):
    events: List[AnalyticsEvent]

@app.post('/analytics')
async def analytics(batch: AnalyticsBatch):
    if not db_pool:
        return {'ok': True}
    async with db_pool.acquire() as conn:
        for ev in batch.events[:50]:  # cap per batch
            try:
                await conn.execute(
                    'INSERT INTO pwa_analytics (uid, event, screen, ts) VALUES ($1,$2,$3,to_timestamp($4/1000.0))',
                    ev.uid, ev.e[:64], ev.screen, ev.ts
                )
            except Exception:
                pass  # never fail the client
    return {'ok': True}

# ── Mobile app API ────────────────────────────────────────────────────────────
# Unlike the PWA endpoints above (which read/write the isolated pwa_* tables),
# the mobile app reads/writes bot_v2's real program tables directly (users,
# participants, tracker_records, week_acks) keyed by Telegram id — so a
# student's progress is visible to curators (CRM) and to the bot's own jobs,
# not stranded in a shadow table. See ACTIVE/pwa_api's plan doc for context.

LEVEL_WEEKS = {'А': 6, 'Б': 8, 'В': 8, 'Г': 8}

CONTENT_DIR = Path(__file__).parent / 'content'
_content_cache: Dict[str, dict] = {}

def _load_lesson_content(level: str, week: int) -> Optional[dict]:
    key = f'{level}_{week}'
    if key in _content_cache:
        return _content_cache[key]
    path = CONTENT_DIR / f'{level}.json'
    if not path.exists():
        return None
    try:
        weeks = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None
    if not (1 <= week <= len(weeks)):
        return None
    lesson = weeks[week - 1]
    _content_cache[key] = lesson
    return lesson

_quiz_cache: Dict[str, dict] = {}

def _load_quiz(level: str, week: int) -> Optional[dict]:
    key = f'{level}_{week}'
    if key in _quiz_cache:
        return _quiz_cache[key]
    path = CONTENT_DIR / f'quiz_{level}.json'
    if not path.exists():
        return None
    try:
        weeks = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None
    if not (1 <= week <= len(weeks)):
        return None
    quiz = weeks[week - 1]
    _quiz_cache[key] = quiz
    return quiz

def make_mobile_token(tg_id: int) -> str:
    payload = {
        'tg_id': tg_id,
        'scope': 'mobile',
        'exp': datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)

def verify_mobile_token(creds: HTTPAuthorizationCredentials = Depends(security)) -> int:
    try:
        payload = jwt.decode(creds.credentials, SECRET, algorithms=[ALGORITHM])
        if payload.get('scope') != 'mobile':
            raise ValueError('wrong token scope')
        return int(payload['tg_id'])
    except Exception:
        raise HTTPException(status_code=401, detail='Токен недействителен')

@app.post('/mobile/auth/tg-init')
async def mobile_tg_init():
    """Мобильное приложение вызывает при нажатии «Войти через Telegram». Переиспользует
    ту же таблицу сессий и тот же bot-side колбэк (POST /auth/tg-confirm), что и PWA."""
    if not db_pool:
        raise HTTPException(500, 'База данных не подключена')
    session_id = secrets.token_urlsafe(16)
    async with db_pool.acquire() as conn:
        await conn.execute(
            'INSERT INTO pwa_tg_sessions (session_id, created_at) VALUES ($1, $2)',
            session_id, datetime.utcnow()
        )
    return {'session_id': session_id}

@app.get('/mobile/auth/tg-check')
async def mobile_tg_check(session_id: str):
    """Поллинг из мобильного приложения. В отличие от /auth/tg-check (PWA), не создаёт
    нового пользователя — ищет существующего ученика бота по tg_id и требует активной
    записи в participants (иначе куратор ещё не подключил его к программе)."""
    if not db_pool:
        raise HTTPException(500, 'База данных не подключена')
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT tg_id, confirmed, created_at FROM pwa_tg_sessions WHERE session_id=$1',
            session_id
        )
        if not row:
            raise HTTPException(404, 'Сессия не найдена')
        if (datetime.utcnow() - row['created_at']).total_seconds() > 600:
            raise HTTPException(410, 'Сессия истекла')
        if not row['confirmed']:
            return {'status': 'pending'}

        user = await conn.fetchrow('SELECT id FROM users WHERE id=$1', row['tg_id'])
        if not user:
            raise HTTPException(404, 'Пользователь не найден в системе IQ Barakah')
        participant = await conn.fetchrow(
            'SELECT id FROM participants WHERE user_id=$1 AND is_active=TRUE', row['tg_id']
        )
        if not participant:
            raise HTTPException(403, 'Программа ещё не активирована куратором')

    return {'status': 'ok', 'access_token': make_mobile_token(row['tg_id']), 'token_type': 'bearer'}

@app.get('/mobile/participant')
async def mobile_participant(tg_id: int = Depends(verify_mobile_token)):
    if not db_pool:
        raise HTTPException(500, 'База данных не подключена')
    async with db_pool.acquire() as conn:
        p = await conn.fetchrow(
            'SELECT level, week, vakt_level, is_active FROM participants WHERE user_id=$1 AND is_active=TRUE',
            tg_id
        )
    if not p:
        raise HTTPException(404, 'Участник не найден')
    return dict(p)

@app.get('/mobile/cohort-count')
async def mobile_cohort_count(tg_id: int = Depends(verify_mobile_token)):
    """Сколько ещё активных участников сейчас на том же шаге — для джамаат-эффекта
    на главном экране («с тобой ещё N братьев»). Считает только реальных активных
    участников, без выдумок."""
    if not db_pool:
        raise HTTPException(500, 'База данных не подключена')
    async with db_pool.acquire() as conn:
        me = await conn.fetchrow(
            'SELECT level, week FROM participants WHERE user_id=$1 AND is_active=TRUE', tg_id
        )
        if not me:
            raise HTTPException(404, 'Участник не найден')
        row = await conn.fetchrow(
            '''SELECT COUNT(*) AS cnt FROM participants
               WHERE level=$1 AND week=$2 AND is_active=TRUE AND user_id != $3''',
            me['level'], me['week'], tg_id
        )
    return {'count': row['cnt']}

@app.get('/mobile/content/{level}/{week}')
async def mobile_content(level: str, week: int, tg_id: int = Depends(verify_mobile_token)):
    lesson = _load_lesson_content(level, week)
    if not lesson:
        raise HTTPException(404, 'Урок не найден')
    return lesson

@app.get('/mobile/quiz/{level}/{week}')
async def mobile_quiz(level: str, week: int, tg_id: int = Depends(verify_mobile_token)):
    """Вопросы для проверки понимания шага — те же, что задаёт бот
    (bot_v2/services/step_tests.get_test), экспортированы в JSON заранее."""
    quiz = _load_quiz(level, week)
    if quiz is None:
        raise HTTPException(404, 'Тест не найден')
    return quiz

class WeekAckReq(BaseModel):
    level: str
    week: int

@app.post('/mobile/week-ack')
async def mobile_week_ack(req: WeekAckReq, tg_id: int = Depends(verify_mobile_token)):
    """Отмечает шаг пройденным. По достижении последнего шага уровня участник
    «выпускается» (is_active=FALSE, graduated_at=NOW()) — точно так же, как это
    делает бот (ParticipantRepo.graduate) при переходе на следующий сезон. Дальше
    вход в приложение снова возможен только после активации куратором на новый
    уровень — мобильное приложение НЕ продвигает участника между уровнями само."""
    if not db_pool:
        raise HTTPException(500, 'База данных не подключена')
    graduated = False
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                '''INSERT INTO week_acks (user_id, level, week, acked_at)
                   VALUES ($1,$2,$3,$4)
                   ON CONFLICT ON CONSTRAINT uq_week_ack DO NOTHING''',
                tg_id, req.level, req.week, datetime.utcnow()
            )
            p = await conn.fetchrow(
                'SELECT week FROM participants WHERE user_id=$1 AND is_active=TRUE', tg_id
            )
            if p and p['week'] == req.week:
                max_week = LEVEL_WEEKS.get(req.level, 8)
                if req.week < max_week:
                    await conn.execute(
                        'UPDATE participants SET week=week+1 WHERE user_id=$1 AND is_active=TRUE', tg_id
                    )
                else:
                    await conn.execute(
                        '''UPDATE participants SET is_active=FALSE, graduated_at=$2
                           WHERE user_id=$1 AND is_active=TRUE''',
                        tg_id, datetime.utcnow()
                    )
                    graduated = True
    return {'ok': True, 'graduated': graduated}

@app.get('/mobile/tracker')
async def mobile_tracker(days: int = 30, tg_id: int = Depends(verify_mobile_token)):
    if not db_pool:
        raise HTTPException(500, 'База данных не подключена')
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            'SELECT date, habits FROM tracker_records WHERE user_id=$1 ORDER BY date DESC LIMIT $2',
            tg_id, days
        )
    return [{'date': r['date'].isoformat(), 'habits': r['habits']} for r in rows]

class MobileTrackerReq(BaseModel):
    date: str
    habits: dict

@app.post('/mobile/tracker')
async def mobile_save_tracker(req: MobileTrackerReq, tg_id: int = Depends(verify_mobile_token)):
    if not db_pool:
        raise HTTPException(500, 'База данных не подключена')
    try:
        record_date = datetime.strptime(req.date, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(400, 'Некорректная дата, ожидается YYYY-MM-DD')
    async with db_pool.acquire() as conn:
        await conn.execute(
            '''INSERT INTO tracker_records (user_id, date, habits, updated_at)
               VALUES ($1,$2,$3,$4)
               ON CONFLICT ON CONSTRAINT uq_tracker_day DO UPDATE SET habits=$3, updated_at=$4''',
            tg_id, record_date, req.habits, datetime.utcnow()
        )
    return {'ok': True}

class MobileWheelReq(BaseModel):
    scores: dict

@app.get('/mobile/wheel')
async def mobile_get_wheel(tg_id: int = Depends(verify_mobile_token)):
    """Последняя оценка «Колеса баланса» — те же 8 сфер, что и в Mini App,
    но сохраняются в реальную таблицу бота (wheel_records), а не в localStorage."""
    if not db_pool:
        raise HTTPException(500, 'База данных не подключена')
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT scores, created_at FROM wheel_records WHERE user_id=$1 ORDER BY created_at DESC LIMIT 1',
            tg_id
        )
    if not row:
        return {'scores': None, 'created_at': None}
    return {'scores': row['scores'], 'created_at': row['created_at'].isoformat()}

@app.post('/mobile/wheel')
async def mobile_save_wheel(req: MobileWheelReq, tg_id: int = Depends(verify_mobile_token)):
    if not db_pool:
        raise HTTPException(500, 'База данных не подключена')
    async with db_pool.acquire() as conn:
        await conn.execute(
            'INSERT INTO wheel_records (user_id, scores, created_at) VALUES ($1,$2,$3)',
            tg_id, req.scores, datetime.utcnow()
        )
    return {'ok': True}

class MobileMuhasabaReq(BaseModel):
    answers: List[Dict[str, str]]  # [{q, a}, ...]

@app.post('/mobile/muhasaba')
async def mobile_save_muhasaba(req: MobileMuhasabaReq, tg_id: int = Depends(verify_mobile_token)):
    """Тот же вечерний самоотчёт (мухасаба), что и в боте — 3 вопроса, сохраняются
    в ту же таблицу muhasaba_logs, поэтому куратор видит записи независимо от того,
    ответил ученик в боте или в приложении."""
    if not db_pool:
        raise HTTPException(500, 'База данных не подключена')
    async with db_pool.acquire() as conn:
        await conn.execute(
            'INSERT INTO muhasaba_logs (user_id, answers, created_at) VALUES ($1,$2,$3)',
            tg_id, req.answers, datetime.utcnow()
        )
    return {'ok': True}

@app.get('/mobile/muhasaba/streak')
async def mobile_muhasaba_streak(tg_id: int = Depends(verify_mobile_token)):
    """Стрик считается напрямую по датам записей в muhasaba_logs (устойчив к тому,
    что запись могла прийти из бота или из приложения), а не по отдельному счётчику."""
    if not db_pool:
        raise HTTPException(500, 'База данных не подключена')
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT DISTINCT created_at::date AS d FROM muhasaba_logs WHERE user_id=$1 ORDER BY d DESC LIMIT 60",
            tg_id
        )
    dates = [r['d'] for r in rows]
    today = datetime.utcnow().date()
    done_today = bool(dates) and dates[0] == today
    streak = 0
    cursor = today if done_today else today - timedelta(days=1)
    for d in dates:
        if d == cursor:
            streak += 1
            cursor -= timedelta(days=1)
        elif d < cursor:
            break
    return {'streak': streak, 'done_today': done_today}

class PushRegisterReq(BaseModel):
    expo_token: str
    platform: str

@app.post('/push/register')
async def push_register(req: PushRegisterReq, tg_id: int = Depends(verify_mobile_token)):
    if not db_pool:
        raise HTTPException(500, 'База данных не подключена')
    async with db_pool.acquire() as conn:
        await conn.execute(
            '''INSERT INTO push_tokens (user_id, expo_token, platform, updated_at)
               VALUES ($1,$2,$3,$4)
               ON CONFLICT (user_id) DO UPDATE SET expo_token=$2, platform=$3, updated_at=$4''',
            tg_id, req.expo_token, req.platform, datetime.utcnow()
        )
    return {'ok': True}
