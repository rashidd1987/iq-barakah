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

CREATE TABLE IF NOT EXISTS pwa_analytics (
    id         BIGSERIAL PRIMARY KEY,
    uid        TEXT NOT NULL,
    event      TEXT NOT NULL,
    screen     TEXT,
    ts         TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pwa_email_otp_challenges (
    challenge_id   TEXT PRIMARY KEY,
    email          TEXT NOT NULL,
    pending_name   TEXT,
    target_user_id INT REFERENCES pwa_users(id) ON DELETE CASCADE,
    client_scope   TEXT NOT NULL DEFAULT 'pwa',
    code_hash      TEXT NOT NULL,
    attempts       SMALLINT NOT NULL DEFAULT 0,
    expires_at     TIMESTAMP NOT NULL,
    consumed_at    TIMESTAMP,
    created_at     TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE pwa_email_otp_challenges
    ADD COLUMN IF NOT EXISTS client_scope TEXT NOT NULL DEFAULT 'pwa';

CREATE INDEX IF NOT EXISTS idx_pwa_tracker_user_date ON pwa_tracker(user_id, date);
CREATE INDEX IF NOT EXISTS idx_pwa_wheel_user ON pwa_wheel(user_id);
CREATE INDEX IF NOT EXISTS idx_pwa_ship_user ON pwa_ship(user_id);
CREATE INDEX IF NOT EXISTS idx_pwa_analytics_uid ON pwa_analytics(uid);
CREATE INDEX IF NOT EXISTS idx_pwa_analytics_event ON pwa_analytics(event);
CREATE INDEX IF NOT EXISTS idx_pwa_email_otp_email
    ON pwa_email_otp_challenges(email, created_at DESC);
