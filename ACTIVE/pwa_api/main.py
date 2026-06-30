from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict
import jwt, bcrypt, os, asyncpg, time, secrets

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

@app.on_event('startup')
async def startup():
    global db_pool
    if DATABASE_URL:
        try:
            db_pool = await asyncpg.create_pool(DATABASE_URL.replace('+asyncpg', ''))
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
