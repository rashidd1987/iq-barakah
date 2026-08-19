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

CREATE TABLE IF NOT EXISTS pwa_tg_sessions (
    session_id     TEXT PRIMARY KEY,
    tg_id          BIGINT,
    tg_name        TEXT,
    confirmed      BOOLEAN NOT NULL DEFAULT FALSE,
    target_user_id INT REFERENCES pwa_users(id) ON DELETE CASCADE,
    consumed_at    TIMESTAMP,
    created_at     TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE pwa_tg_sessions
    ADD COLUMN IF NOT EXISTS target_user_id INT REFERENCES pwa_users(id) ON DELETE CASCADE;
ALTER TABLE pwa_tg_sessions
    ADD COLUMN IF NOT EXISTS consumed_at TIMESTAMP;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint c
        JOIN pg_class t ON t.oid=c.conrelid
        JOIN pg_namespace n ON n.oid=t.relnamespace
        WHERE n.nspname='public' AND t.relname='pwa_tg_sessions' AND c.contype='f'
          AND pg_get_constraintdef(c.oid) LIKE 'FOREIGN KEY (target_user_id)%'
    ) THEN
        ALTER TABLE pwa_tg_sessions
            ADD CONSTRAINT pwa_tg_sessions_target_user_id_fkey
            FOREIGN KEY (target_user_id) REFERENCES pwa_users(id) ON DELETE CASCADE;
    END IF;
END $$;

ALTER TABLE pwa_email_otp_challenges
    ADD COLUMN IF NOT EXISTS client_scope TEXT NOT NULL DEFAULT 'pwa';

CREATE INDEX IF NOT EXISTS idx_pwa_tracker_user_date ON pwa_tracker(user_id, date);
CREATE INDEX IF NOT EXISTS idx_pwa_wheel_user ON pwa_wheel(user_id);
CREATE INDEX IF NOT EXISTS idx_pwa_ship_user ON pwa_ship(user_id);
CREATE INDEX IF NOT EXISTS idx_pwa_analytics_uid ON pwa_analytics(uid);
CREATE INDEX IF NOT EXISTS idx_pwa_analytics_event ON pwa_analytics(event);
CREATE INDEX IF NOT EXISTS idx_pwa_email_otp_email
    ON pwa_email_otp_challenges(email, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pwa_tg_sessions_target
    ON pwa_tg_sessions(target_user_id, created_at DESC);
