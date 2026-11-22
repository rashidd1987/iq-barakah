"""Durable single-execution queue for the owner's local Mac.

Running jobs are never automatically requeued: after a crash the outcome may
be unknown, and repeating a file write could duplicate an external effect.
"""

from contextlib import contextmanager
from pathlib import Path
import base64
import binascii
import secrets
import sqlite3
import time


class MacQueue:
    def __init__(self, data_dir: str):
        self.path = Path(data_dir) / "mac_jobs.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, source TEXT UNIQUE NOT NULL,
                owner INTEGER NOT NULL, task TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued', worker TEXT,
                claim_token TEXT, created REAL NOT NULL, started REAL,
                finished REAL, result TEXT, notified INTEGER NOT NULL DEFAULT 0
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS heartbeat (
                worker TEXT PRIMARY KEY, seen REAL NOT NULL
            )""")
            columns = {r[1] for r in db.execute('PRAGMA table_info(jobs)')}
            for name, definition in [('voice', 'TEXT'), ('ack_sent', 'INTEGER NOT NULL DEFAULT 0')]:
                if name not in columns:
                    db.execute(f'ALTER TABLE jobs ADD COLUMN {name} {definition}')
        self.path.chmod(0o600)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            db.row_factory = sqlite3.Row
            with db:
                yield db
        finally:
            db.close()

    def enqueue(self, owner: int, source: str, task: str) -> dict:
        if not isinstance(task, str) or not 3 <= len(task.strip()) <= 4000:
            raise ValueError("Задача должна содержать от 3 до 4000 символов")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM jobs WHERE source=?", (source,)).fetchone()
            if existing:
                return dict(existing)
            count = db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
            if count >= 20:
                raise ValueError("В очереди уже 20 задач. Дождитесь завершения")
            job_id = secrets.token_hex(6)
            db.execute("INSERT INTO jobs(id,source,owner,task,created) VALUES (?,?,?,?,?)",
                       (job_id, source, owner, task.strip(), time.time()))
            return dict(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def claim(self, worker: str) -> dict | None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO heartbeat VALUES (?,?) ON CONFLICT(worker) DO UPDATE SET seen=excluded.seen",
                       (worker, time.time()))
            # One task at a time, including across multiple processes.
            if db.execute("SELECT 1 FROM jobs WHERE status='running'").fetchone():
                return None
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if row is None:
                return None
            token = secrets.token_urlsafe(24)
            db.execute("UPDATE jobs SET status='running',worker=?,claim_token=?,started=? WHERE id=?",
                       (worker, token, time.time(), row['id']))
            return dict(db.execute("SELECT * FROM jobs WHERE id=?", (row['id'],)).fetchone())

    def finish(self, job_id: str, worker: str, token: str, status: str, result: str, voice=None) -> dict:
        if status not in {'done', 'failed', 'unknown'} or not isinstance(result, str) or not 1 <= len(result) <= 16000:
            raise ValueError('invalid result')
        if voice is not None:
            if not isinstance(voice, str) or len(voice) > 350000:
                raise ValueError('invalid voice')
            try:
                audio = base64.b64decode(voice, validate=True)
            except (ValueError, binascii.Error):
                raise ValueError('invalid voice') from None
            if not 500 <= len(audio) <= 260000 or not audio.startswith(b'OggS') or b'OpusHead' not in audio[:128]:
                raise ValueError('invalid voice')
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None or row['worker'] != worker or not secrets.compare_digest(row['claim_token'] or '', token):
                raise PermissionError('invalid claim')
            if row['status'] == 'running':
                db.execute("UPDATE jobs SET status=?,result=?,finished=?,voice=? WHERE id=?",
                           (status, result, time.time(), voice, job_id))
            elif row['status'] != status or row['result'] != result or row['voice'] != voice:
                raise ValueError('conflicting result')
            return dict(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def recover(self, worker: str) -> list[dict]:
        with self.connection() as db:
            return [dict(r) for r in db.execute("SELECT * FROM jobs WHERE worker=? AND status='running'", (worker,))]

    def recent(self, owner: int) -> list[dict]:
        with self.connection() as db:
            return [dict(r) for r in db.execute("SELECT id,status,task FROM jobs WHERE owner=? ORDER BY created DESC LIMIT 8", (owner,))]

    def last_seen(self) -> float | None:
        with self.connection() as db:
            return db.execute('SELECT max(seen) FROM heartbeat').fetchone()[0]

    def unnotified(self) -> list[dict]:
        with self.connection() as db:
            return [dict(r) for r in db.execute("SELECT * FROM jobs WHERE status IN ('done','failed','unknown') AND notified=0")]

    def mark_notified(self, job_id: str):
        with self.connection() as db:
            db.execute('UPDATE jobs SET notified=1 WHERE id=?', (job_id,))

    def claim_ack(self, job_id):
        with self.connection() as db:
            return db.execute('UPDATE jobs SET ack_sent=1 WHERE id=? AND ack_sent=0', (job_id,)).rowcount == 1
