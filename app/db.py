import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    team_lead TEXT,
    agent_id TEXT
);

CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    team TEXT NOT NULL,
    team_lead TEXT NOT NULL,
    default_shift TEXT NOT NULL,
    employment_status TEXT NOT NULL,
    productive_hours REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS roster (
    id INTEGER PRIMARY KEY,
    roster_date TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    shift TEXT NOT NULL,
    scheduled_status TEXT NOT NULL,
    attendance_status TEXT NOT NULL,
    absence_fraction REAL NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    updated_by TEXT,
    updated_at TEXT,
    UNIQUE (roster_date, agent_id)
);

CREATE TABLE IF NOT EXISTS forecast (
    roster_date TEXT PRIMARY KEY,
    forecast_volume INTEGER NOT NULL,
    aht_seconds INTEGER NOT NULL,
    shrinkage REAL NOT NULL,
    occupancy REAL NOT NULL,
    required_agents REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS leave_entries (
    id INTEGER PRIMARY KEY,
    roster_date TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    leave_type TEXT NOT NULL,
    day_part TEXT NOT NULL,
    comments TEXT NOT NULL,
    entered_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    roster_date TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    previous_attendance TEXT,
    new_attendance TEXT,
    previous_fraction REAL,
    new_fraction REAL,
    previous_scheduled TEXT,
    new_scheduled TEXT,
    updated_by TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    comment TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    csrf_token TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seed_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    seeded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_roster_date ON roster (roster_date);
CREATE INDEX IF NOT EXISTS idx_roster_agent ON roster (agent_id);
CREATE INDEX IF NOT EXISTS idx_audit_date ON audit_log (roster_date);
"""


def db_path() -> Path:
    raw = os.environ.get("DATABASE_PATH")
    path = Path(raw) if raw else PROJECT_ROOT / "data" / "roster.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def workbook_path() -> Path:
    raw = os.environ.get("WORKBOOK_PATH")
    return Path(raw) if raw else PROJECT_ROOT / "data" / "roster.xlsx"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


@contextmanager
def get_conn():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction():
    conn = connect()
    started = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        started = True
        yield conn
        conn.execute("COMMIT")
        started = False
    except Exception:
        if started:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def init_db() -> None:
    path = db_path()
    if os.environ.get("REQUIRE_WRITABLE_DB") == "1":
        probe = path.parent / ".write_probe"
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except OSError as exc:
            raise RuntimeError(f"Database directory is not writable: {path.parent}") from exc
    conn = connect()
    try:
        conn.execute("PRAGMA journal_mode = WAL").fetchone()
        conn.executescript(SCHEMA)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "agent_id" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN agent_id TEXT")
    finally:
        conn.close()
