from app.auth import hash_password, utc_now
from app.db import init_db, transaction, workbook_path
from app.logic import quantize
from app.xlsx_reader import read_source

DEMO_PASSWORD = "demo123"
USERS = [
    ("wfm", "wfm", None),
    ("tl1", "team_lead", "Team Lead 1"),
    ("tl2", "team_lead", "Team Lead 2"),
    ("tl3", "team_lead", "Team Lead 3"),
    ("tl4", "team_lead", "Team Lead 4"),
]


def split_status(attendance_status: str) -> tuple[str, str, float]:
    if attendance_status == "WO":
        return "Weekly Off", "WO", 0.0
    if attendance_status == "Present":
        return "Working", "Present", 0.0
    return "Working", attendance_status, 1.0


def seed_if_needed() -> None:
    init_db()
    with transaction() as conn:
        existing = conn.execute("SELECT id FROM seed_meta WHERE id = 1").fetchone()
        if existing:
            return
        source_path = workbook_path()
        if not source_path.exists():
            raise RuntimeError(
                f"Workbook not found at {source_path}. Copy the assessment file to data/roster.xlsx."
            )
        source = read_source(source_path)
        password_hash = hash_password(DEMO_PASSWORD)
        for username, role, team_lead in USERS:
            conn.execute(
                "INSERT INTO users (username, password_hash, role, team_lead, agent_id) VALUES (?, ?, ?, ?, NULL)",
                (username, password_hash, role, team_lead),
            )
        for agent in source["agents"]:
            conn.execute(
                """
                INSERT INTO agents (
                    agent_id, agent_name, team, team_lead, default_shift, employment_status, productive_hours
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent["agent_id"],
                    agent["agent_name"],
                    agent["team"],
                    agent["team_lead"],
                    agent["default_shift"],
                    agent["employment_status"],
                    agent["productive_hours"],
                ),
            )
        for row in source["roster"]:
            scheduled, attendance, fraction = split_status(row["attendance_status"])
            conn.execute(
                """
                INSERT INTO roster (
                    roster_date, agent_id, shift, scheduled_status, attendance_status,
                    absence_fraction, version
                ) VALUES (?, ?, ?, ?, ?, ?, 1)
                """,
                (row["roster_date"], row["agent_id"], row["shift"], scheduled, attendance, fraction),
            )
        for row in source["forecast"]:
            conn.execute(
                """
                INSERT INTO forecast (
                    roster_date, forecast_volume, aht_seconds, shrinkage, occupancy, required_agents
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row["roster_date"],
                    row["forecast_volume"],
                    row["aht_seconds"],
                    float(quantize(row["shrinkage"], "0.01")),
                    float(quantize(row["occupancy"], "0.01")),
                    float(quantize(row["required_agents"], "0.1")),
                ),
            )
        for agent in source["agents"]:
            conn.execute(
                "INSERT INTO users (username, password_hash, role, team_lead, agent_id) VALUES (?, ?, 'agent', NULL, ?)",
                (agent["agent_id"], password_hash, agent["agent_id"]),
            )
        conn.execute("INSERT INTO seed_meta (id, seeded_at) VALUES (1, ?)", (utc_now(),))


def ensure_agent_accounts() -> None:
    """Add one login per agent without reloading the workbook over saved edits."""
    with transaction() as conn:
        missing: list[str] = []
        agents = conn.execute("SELECT agent_id FROM agents ORDER BY agent_id").fetchall()
        for agent in agents:
            existing = conn.execute(
                "SELECT username, role, agent_id FROM users WHERE username = ?",
                (agent["agent_id"],),
            ).fetchone()
            if existing is None:
                missing.append(agent["agent_id"])
            elif existing["role"] == "agent" and not existing["agent_id"]:
                conn.execute(
                    "UPDATE users SET agent_id = ? WHERE username = ?",
                    (agent["agent_id"], agent["agent_id"]),
                )
        if not missing:
            return
        password_hash = hash_password(DEMO_PASSWORD)
        for agent_id in missing:
            conn.execute(
                "INSERT INTO users (username, password_hash, role, team_lead, agent_id) VALUES (?, ?, 'agent', NULL, ?)",
                (agent_id, password_hash, agent_id),
            )
