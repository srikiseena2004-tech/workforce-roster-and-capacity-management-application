import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed import seed_if_needed


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "roster.db"))
    monkeypatch.delenv("REQUIRE_WRITABLE_DB", raising=False)
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, username: str) -> str:
    response = client.post("/api/login", json={"username": username, "password": "demo123"})
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def dashboard(client: TestClient, date: str, **params):
    response = client.get("/api/dashboard", params={"date": date, **params})
    assert response.status_code == 200, response.text
    return response.json()


def cell(client: TestClient, agent_id: str, date: str):
    response = client.get("/api/roster", params={"agent_id": agent_id})
    assert response.status_code == 200, response.text
    return response.json()["cells"][f"{agent_id}|{date}"]


def test_nov2_uses_roster_not_forecast_sheet(client):
    login(client, "wfm")
    center = dashboard(client, "2026-11-02")["center"]
    assert center["forecast_volume"] == 890
    assert center["required_agents"] == 26.4
    assert center["scheduled_headcount"] == 40
    assert center["present_fte"] == 37
    assert center["absent_fte"] == 3
    assert center["capacity_hours"] == 267.33
    assert center["surplus"] == 10.6


def test_team_filter_does_not_change_center_surplus(client):
    login(client, "wfm")
    body = dashboard(client, "2026-11-02", team="Alpha")
    assert body["center"]["surplus"] == 10.6
    assert body["center"]["present_fte"] == 37
    assert body["selected"]["scheduled_headcount"] == 10
    assert "surplus" not in body["selected"]


def test_team_lead_sick_leave_persists_and_blocks_conflicts(client):
    token = login(client, "tl1")
    current = cell(client, "AGT001", "2026-11-02")
    assert current["attendance_status"] == "Present"
    saved = client.post(
        "/api/attendance",
        headers={"X-CSRF-Token": token},
        json={
            "roster_date": "2026-11-02",
            "agent_id": "AGT001",
            "attendance_status": "Sick Leave",
            "day_part": "Full Day",
            "comment": "Fever",
            "version": current["version"],
        },
    )
    assert saved.status_code == 200, saved.text
    center = dashboard(client, "2026-11-02")["center"]
    assert center["scheduled_headcount"] == 40
    assert center["present_fte"] == 36
    assert center["surplus"] == 9.6

    stale = client.post(
        "/api/attendance",
        headers={"X-CSRF-Token": token},
        json={
            "roster_date": "2026-11-02",
            "agent_id": "AGT001",
            "attendance_status": "PL",
            "day_part": "Full Day",
            "comment": "Later request",
            "version": current["version"],
        },
    )
    assert stale.status_code == 409

    seed_if_needed()
    assert dashboard(client, "2026-11-02")["center"]["surplus"] == 9.6
    audit = client.get("/api/audit")
    assert audit.status_code == 200
    entry = audit.json()["entries"][0]
    assert entry["agent_id"] == "AGT001"
    assert entry["previous_attendance"] == "Present"
    assert entry["new_attendance"] == "Sick Leave"
    assert entry["updated_by"] == "tl1"


def test_other_team_lead_and_weekly_off_are_rejected(client):
    token = login(client, "tl2")
    current = cell(client, "AGT001", "2026-11-02")
    denied = client.post(
        "/api/attendance",
        headers={"X-CSRF-Token": token},
        json={
            "roster_date": "2026-11-02",
            "agent_id": "AGT001",
            "attendance_status": "Sick Leave",
            "day_part": "Full Day",
            "comment": "No",
            "version": current["version"],
        },
    )
    assert denied.status_code == 403

    client.post("/api/logout", headers={"X-CSRF-Token": token})
    token = login(client, "tl1")
    weekend = cell(client, "AGT001", "2026-11-01")
    blocked = client.post(
        "/api/attendance",
        headers={"X-CSRF-Token": token},
        json={
            "roster_date": "2026-11-01",
            "agent_id": "AGT001",
            "attendance_status": "Sick Leave",
            "day_part": "Full Day",
            "comment": "Weekend",
            "version": weekend["version"],
        },
    )
    assert blocked.status_code == 400
    weekend_center = dashboard(client, "2026-11-01")["center"]
    assert weekend_center["scheduled_headcount"] == 0
    assert weekend_center["present_fte"] == 0
    assert weekend_center["surplus"] == -12.6


def test_rta_can_schedule_a_weekly_off_day(client):
    token = login(client, "wfm")
    current = cell(client, "AGT001", "2026-11-01")
    saved = client.post(
        "/api/schedule",
        headers={"X-CSRF-Token": token},
        json={
            "roster_date": "2026-11-01",
            "agent_id": "AGT001",
            "scheduled_status": "Working",
            "version": current["version"],
        },
    )
    assert saved.status_code == 200, saved.text
    center = dashboard(client, "2026-11-01")["center"]
    assert center["scheduled_headcount"] == 1
    assert center["present_fte"] == 1
    assert center["surplus"] == -11.6


def test_half_day_and_missing_csrf(client):
    token = login(client, "tl1")
    current = cell(client, "AGT001", "2026-11-02")
    missing = client.post(
        "/api/attendance",
        json={
            "roster_date": "2026-11-02",
            "agent_id": "AGT001",
            "attendance_status": "Sick Leave",
            "day_part": "Half Day",
            "comment": "Left after lunch",
            "version": current["version"],
        },
    )
    assert missing.status_code == 403
    saved = client.post(
        "/api/attendance",
        headers={"X-CSRF-Token": token},
        json={
            "roster_date": "2026-11-02",
            "agent_id": "AGT001",
            "attendance_status": "Sick Leave",
            "day_part": "Half Day",
            "comment": "Left after lunch",
            "version": current["version"],
        },
    )
    assert saved.status_code == 200, saved.text
    center = dashboard(client, "2026-11-02")["center"]
    assert center["present_fte"] == 36.5
    assert center["absent_fte"] == 3.5
    assert center["capacity_hours"] == 263.71
    assert center["surplus"] == 10.1
    assert center["scheduled_headcount"] == 40


def test_agent_sees_only_their_own_record(client):
    login(client, "AGT001")
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["role"] == "agent"
    assert me.json()["agent_id"] == "AGT001"
    assert me.json()["agent_name"] == "Agent 1"

    roster = client.get("/api/roster", params={"agent_id": "AGT040", "team": "Delta"})
    assert roster.status_code == 200, roster.text
    body = roster.json()
    assert [agent["agent_id"] for agent in body["agents"]] == ["AGT001"]
    assert set(cell["agent_id"] for cell in body["cells"].values()) == {"AGT001"}
    assert "AGT001|2026-11-02" in body["cells"]

    meta = client.get("/api/meta")
    assert [agent["agent_id"] for agent in meta.json()["agents"]] == ["AGT001"]
    assert client.get("/api/dashboard", params={"date": "2026-11-02"}).status_code == 403
    assert client.get("/api/charts").status_code == 403
    assert client.get("/api/export/daily.csv", params={"date": "2026-11-02"}).status_code == 403

    exported = client.get("/api/export/roster.csv", params={"agent_id": "AGT040"})
    assert exported.status_code == 200
    lines = [line for line in exported.text.splitlines() if line.startswith("2026-")]
    assert lines
    assert all(",AGT001," in line for line in lines)

    csrf = me.json()["csrf_token"]
    denied = client.post(
        "/api/attendance",
        headers={"X-CSRF-Token": csrf},
        json={
            "roster_date": "2026-11-02",
            "agent_id": "AGT001",
            "attendance_status": "Sick Leave",
            "day_part": "Full Day",
            "comment": "I cannot edit",
            "version": body["cells"]["AGT001|2026-11-02"]["version"],
        },
    )
    assert denied.status_code == 403
