-- PWA tables (добавить к существующей БД bot_v2)
-- Запустить один раз: psql $DATABASE_URL -f migration.sql

CREATE TABLE IF NOT EXISTS pwa_users (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    email        TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    tg_id        BIGINT UNIQUE,
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pwa_tracker (
    id         SERIAL PRIMARY KEY,
    user_id    INT NOT NULL REFERENCES pwa_users(id) ON DELETE CASCADE,
    date       DATE NOT NULL,
    data       JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, date)
);

CREATE TABLE IF NOT EXISTS pwa_wheel (
    id         SERIAL PRIMARY KEY,
    user_id    INT NOT NULL REFERENCES pwa_users(id) ON DELETE CASCADE,
    scores     JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pwa_ship (
    id         SERIAL PRIMARY KEY,
    user_id    INT NOT NULL REFERENCES pwa_users(id) ON DELETE CASCADE,
    type       TEXT NOT NULL,
    scores     JSONB NOT NULL DEFAULT '{}',
    avg        FLOAT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pwa_tracker_user_date ON pwa_tracker(user_id, date);
CREATE INDEX IF NOT EXISTS idx_pwa_wheel_user ON pwa_wheel(user_id);
CREATE INDEX IF NOT EXISTS idx_pwa_ship_user ON pwa_ship(user_id);
