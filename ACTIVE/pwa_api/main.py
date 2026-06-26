from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict
import jwt, bcrypt, os, asyncpg, time

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
        db_pool = await asyncpg.create_pool(DATABASE_URL.replace('+asyncpg', ''))

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

@app.get('/health')
async def health():
    return {'status': 'ok'}

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
