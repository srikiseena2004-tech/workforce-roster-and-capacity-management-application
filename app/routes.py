import csv
import io
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.auth import expiry, new_token, utc_now, verify_password
from app.db import get_conn, transaction
from app.logic import (
    ATTENDANCE_CHOICES,
    COMMENT_REQUIRED,
    DATE_MAX,
    DATE_MIN,
    FILTER_STATUSES,
    fraction_for,
    metrics,
    quantize,
)

router = APIRouter()


class LoginIn(BaseModel):
    username: str
    password: str


class AttendanceIn(BaseModel):
    roster_date: str
    agent_id: str
    attendance_status: str
    day_part: Literal["Full Day", "Half Day"]
    comment: str = ""
    version: int = Field(ge=1)


class ScheduleIn(BaseModel):
    roster_date: str
    agent_id: str
    scheduled_status: Literal["Working", "Weekly Off"]
    version: int = Field(ge=1)


def _user_from_request(conn, request: Request):
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Sign in required")
    row = conn.execute(
        """
        SELECT s.token, s.csrf_token, s.expires_at, u.username, u.role, u.team_lead, u.agent_id,
               a.agent_name
        FROM sessions s
        JOIN users u ON u.username = s.username
        LEFT JOIN agents a ON a.agent_id = u.agent_id
        WHERE s.token = ?
        """,
        (token,),
    ).fetchone()
    if row is None or row["expires_at"] < utc_now():
        raise HTTPException(status_code=401, detail="Sign in required")
    return row


def require_user(request: Request):
    with get_conn() as conn:
        return dict(_user_from_request(conn, request))


def require_csrf(request: Request, user: dict) -> None:
    sent = request.headers.get("x-csrf-token", "")
    if not sent or sent != user["csrf_token"]:
        raise HTTPException(status_code=403, detail="Missing or invalid CSRF token")


def _public_user(user) -> dict:
    agent_name = user["agent_name"] if "agent_name" in user.keys() else None
    return {
        "username": user["username"],
        "role": user["role"],
        "team_lead": user["team_lead"],
        "agent_id": user["agent_id"],
        "agent_name": agent_name,
        "csrf_token": user["csrf_token"],
    }


def _reject_agent_desk(user) -> None:
    if user["role"] == "agent":
        raise HTTPException(status_code=403, detail="Agents can view only their own roster")


def _check_date(value: str) -> None:
    if value < DATE_MIN or value > DATE_MAX:
        raise HTTPException(status_code=400, detail="Date must be between 1 and 30 November 2026")


def _forecast(conn, roster_date: str):
    row = conn.execute("SELECT * FROM forecast WHERE roster_date = ?", (roster_date,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="No forecast for that date")
    return row


def _roster_rows(conn, roster_date: str, team="", team_lead="", agent_id="", status=""):
    sql = """
        SELECT r.scheduled_status, r.attendance_status, r.absence_fraction
        FROM roster r
        JOIN agents a ON a.agent_id = r.agent_id
        WHERE r.roster_date = ?
    """
    params: list = [roster_date]
    if team:
        sql += " AND a.team = ?"
        params.append(team)
    if team_lead:
        sql += " AND a.team_lead = ?"
        params.append(team_lead)
    if agent_id:
        sql += " AND r.agent_id = ?"
        params.append(agent_id)
    if status:
        sql += " AND r.attendance_status = ?"
        params.append(status)
    return conn.execute(sql, params).fetchall()


def _center_block(conn, roster_date: str) -> dict:
    forecast = _forecast(conn, roster_date)
    rows = _roster_rows(conn, roster_date)
    counted = metrics(rows, forecast["required_agents"], forecast["occupancy"])
    return {
        "date": roster_date,
        "forecast_volume": forecast["forecast_volume"],
        "aht_seconds": forecast["aht_seconds"],
        "shrinkage": forecast["shrinkage"],
        "occupancy": forecast["occupancy"],
        "required_agents": float(quantize(forecast["required_agents"], "0.1")),
        **counted,
    }


def _cell_dict(row) -> dict:
    return {
        "roster_date": row["roster_date"],
        "agent_id": row["agent_id"],
        "agent_name": row["agent_name"],
        "team": row["team"],
        "team_lead": row["team_lead"],
        "shift": row["shift"],
        "scheduled_status": row["scheduled_status"],
        "attendance_status": row["attendance_status"],
        "absence_fraction": row["absence_fraction"],
        "version": row["version"],
        "updated_by": row["updated_by"],
        "updated_at": row["updated_at"],
    }


def _load_cell(conn, roster_date: str, agent_id: str):
    row = conn.execute(
        """
        SELECT r.*, a.agent_name, a.team, a.team_lead
        FROM roster r
        JOIN agents a ON a.agent_id = r.agent_id
        WHERE r.roster_date = ? AND r.agent_id = ?
        """,
        (roster_date, agent_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Roster cell not found")
    return row


@router.post("/login")
def login(body: LoginIn, response: Response):
    with transaction() as conn:
        user = conn.execute(
            """
            SELECT u.*, a.agent_name
            FROM users u
            LEFT JOIN agents a ON a.agent_id = u.agent_id
            WHERE u.username = ?
            """,
            (body.username.strip(),),
        ).fetchone()
        if user is None or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        token = new_token()
        csrf = new_token()
        username = user["username"]
        role = user["role"]
        team_lead = user["team_lead"]
        agent_id = user["agent_id"]
        agent_name = user["agent_name"]
        conn.execute("DELETE FROM sessions WHERE username = ?", (username,))
        conn.execute(
            "INSERT INTO sessions (token, username, csrf_token, expires_at) VALUES (?, ?, ?, ?)",
            (token, username, csrf, expiry()),
        )
    response.set_cookie(
        "session",
        token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
        max_age=60 * 60 * 12,
    )
    return {
        "username": username,
        "role": role,
        "team_lead": team_lead,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "csrf_token": csrf,
    }


@router.post("/logout")
def logout(request: Request, response: Response):
    user = require_user(request)
    require_csrf(request, user)
    with transaction() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (request.cookies.get("session"),))
    response.delete_cookie("session", path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    token = request.cookies.get("session")
    if not token:
        return {"authenticated": False}
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT s.token, s.csrf_token, s.expires_at, u.username, u.role, u.team_lead, u.agent_id,
                   a.agent_name
            FROM sessions s
            JOIN users u ON u.username = s.username
            LEFT JOIN agents a ON a.agent_id = u.agent_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
        if row is None or row["expires_at"] < utc_now():
            return {"authenticated": False}
        user = dict(row)
    return {**_public_user(user), "authenticated": True}


@router.get("/meta")
def meta(request: Request):
    user = require_user(request)
    with get_conn() as conn:
        sql = "SELECT agent_id, agent_name, team, team_lead, default_shift FROM agents"
        params: list = []
        if user["role"] == "agent":
            sql += " WHERE agent_id = ?"
            params.append(user["agent_id"])
        sql += " ORDER BY agent_id"
        agents = conn.execute(sql, params).fetchall()
        dates = [row["roster_date"] for row in conn.execute("SELECT roster_date FROM forecast ORDER BY roster_date")]
    return {
        "teams": ["Alpha", "Bravo", "Charlie", "Delta"],
        "team_leads": ["Team Lead 1", "Team Lead 2", "Team Lead 3", "Team Lead 4"],
        "agents": [dict(row) for row in agents],
        "statuses": FILTER_STATUSES,
        "attendance_choices": ATTENDANCE_CHOICES,
        "dates": dates,
    }


@router.get("/dashboard")
def dashboard(
    request: Request,
    date: str,
    team: str = "",
    team_lead: str = "",
    agent_id: str = "",
    status: str = "",
):
    user = require_user(request)
    _reject_agent_desk(user)
    _check_date(date)
    with get_conn() as conn:
        center = _center_block(conn, date)
        selected = None
        if team or team_lead or agent_id or status:
            forecast = _forecast(conn, date)
            rows = _roster_rows(conn, date, team, team_lead, agent_id, status)
            counted = metrics(rows, forecast["required_agents"], forecast["occupancy"])
            selected = {
                "scheduled_headcount": counted["scheduled_headcount"],
                "present_fte": counted["present_fte"],
                "present_headcount": counted["present_headcount"],
                "absent_fte": counted["absent_fte"],
                "absent_headcount": counted["absent_headcount"],
                "capacity_hours": counted["capacity_hours"],
            }
    return {"center": center, "selected": selected}


@router.get("/roster")
def roster(
    request: Request,
    team: str = "",
    team_lead: str = "",
    agent_id: str = "",
    status: str = "",
):
    user = require_user(request)
    if user["role"] == "agent":
        team = ""
        team_lead = ""
        agent_id = user["agent_id"]
    with get_conn() as conn:
        agent_sql = "SELECT agent_id, agent_name, team, team_lead, default_shift FROM agents WHERE 1 = 1"
        params: list = []
        if team:
            agent_sql += " AND team = ?"
            params.append(team)
        if team_lead:
            agent_sql += " AND team_lead = ?"
            params.append(team_lead)
        if agent_id:
            agent_sql += " AND agent_id = ?"
            params.append(agent_id)
        agent_sql += " ORDER BY agent_id"
        agents = [dict(row) for row in conn.execute(agent_sql, params)]
        allowed = {agent["agent_id"] for agent in agents}
        dates = [row["roster_date"] for row in conn.execute("SELECT roster_date FROM forecast ORDER BY roster_date")]
        cells = {}
        if allowed:
            placeholders = ",".join("?" for _ in allowed)
            rows = conn.execute(
                f"""
                SELECT r.*, a.agent_name, a.team, a.team_lead
                FROM roster r
                JOIN agents a ON a.agent_id = r.agent_id
                WHERE r.agent_id IN ({placeholders})
                ORDER BY r.roster_date, r.agent_id
                """,
                tuple(sorted(allowed)),
            ).fetchall()
            matched_agents = set()
            for row in rows:
                if status and row["attendance_status"] != status:
                    continue
                matched_agents.add(row["agent_id"])
                cells[f"{row['agent_id']}|{row['roster_date']}"] = _cell_dict(row)
            if status:
                agents = [agent for agent in agents if agent["agent_id"] in matched_agents]
                cells = {key: value for key, value in cells.items() if value["agent_id"] in matched_agents}
    return {"dates": dates, "agents": agents, "cells": cells}


@router.post("/attendance")
def update_attendance(body: AttendanceIn, request: Request):
    user = require_user(request)
    require_csrf(request, user)
    if user["role"] != "team_lead":
        raise HTTPException(status_code=403, detail="Only a Team Lead can update attendance")
    if body.attendance_status not in ATTENDANCE_CHOICES:
        raise HTTPException(status_code=400, detail="Choose a valid attendance status")
    _check_date(body.roster_date)
    comment = body.comment.strip()
    if body.attendance_status in COMMENT_REQUIRED and not comment:
        raise HTTPException(status_code=400, detail="A comment is required for NCNS and Unplanned Leave")
    try:
        fraction = fraction_for(body.attendance_status, body.day_part)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    with transaction() as conn:
        row = _load_cell(conn, body.roster_date, body.agent_id)
        if row["team_lead"] != user["team_lead"]:
            raise HTTPException(status_code=403, detail="You can update only your own agents")
        if row["scheduled_status"] != "Working":
            raise HTTPException(
                status_code=400,
                detail="This agent is on weekly off. Ask RTA to schedule a working day first.",
            )
        updated = conn.execute(
            """
            UPDATE roster
            SET attendance_status = ?, absence_fraction = ?, version = version + 1,
                updated_by = ?, updated_at = ?
            WHERE id = ? AND version = ?
            """,
            (body.attendance_status, fraction, user["username"], utc_now(), row["id"], body.version),
        )
        if updated.rowcount != 1:
            raise HTTPException(
                status_code=409,
                detail="This record was updated by someone else. Reload it and try again.",
            )
        conn.execute(
            """
            INSERT INTO leave_entries (
                roster_date, agent_id, leave_type, day_part, comments, entered_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (body.roster_date, body.agent_id, body.attendance_status, body.day_part, comment, user["username"], utc_now()),
        )
        conn.execute(
            """
            INSERT INTO audit_log (
                roster_date, agent_id, previous_attendance, new_attendance, previous_fraction, new_fraction,
                previous_scheduled, new_scheduled, updated_by, updated_at, comment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.roster_date,
                body.agent_id,
                row["attendance_status"],
                body.attendance_status,
                row["absence_fraction"],
                fraction,
                row["scheduled_status"],
                row["scheduled_status"],
                user["username"],
                utc_now(),
                comment,
            ),
        )
        saved = _load_cell(conn, body.roster_date, body.agent_id)
    return {"ok": True, "cell": _cell_dict(saved)}


@router.post("/schedule")
def update_schedule(body: ScheduleIn, request: Request):
    user = require_user(request)
    require_csrf(request, user)
    if user["role"] != "wfm":
        raise HTTPException(status_code=403, detail="Only RTA can change Working or Weekly Off")
    _check_date(body.roster_date)
    with transaction() as conn:
        row = _load_cell(conn, body.roster_date, body.agent_id)
        if row["scheduled_status"] == body.scheduled_status:
            raise HTTPException(status_code=400, detail="The schedule is already set to that value")
        if body.scheduled_status == "Weekly Off":
            attendance, fraction = "WO", 0.0
        else:
            attendance, fraction = "Present", 0.0
        updated = conn.execute(
            """
            UPDATE roster
            SET scheduled_status = ?, attendance_status = ?, absence_fraction = ?,
                version = version + 1, updated_by = ?, updated_at = ?
            WHERE id = ? AND version = ?
            """,
            (body.scheduled_status, attendance, fraction, user["username"], utc_now(), row["id"], body.version),
        )
        if updated.rowcount != 1:
            raise HTTPException(
                status_code=409,
                detail="This record was updated by someone else. Reload it and try again.",
            )
        conn.execute(
            """
            INSERT INTO audit_log (
                roster_date, agent_id, previous_attendance, new_attendance, previous_fraction, new_fraction,
                previous_scheduled, new_scheduled, updated_by, updated_at, comment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.roster_date,
                body.agent_id,
                row["attendance_status"],
                attendance,
                row["absence_fraction"],
                fraction,
                row["scheduled_status"],
                body.scheduled_status,
                user["username"],
                utc_now(),
                "Schedule change",
            ),
        )
        saved = _load_cell(conn, body.roster_date, body.agent_id)
    return {"ok": True, "cell": _cell_dict(saved)}


@router.get("/charts")
def charts(request: Request):
    user = require_user(request)
    _reject_agent_desk(user)
    days = []
    mix: dict[str, int] = {}
    with get_conn() as conn:
        forecasts = conn.execute("SELECT * FROM forecast ORDER BY roster_date").fetchall()
        for forecast in forecasts:
            rows = _roster_rows(conn, forecast["roster_date"])
            counted = metrics(rows, forecast["required_agents"], forecast["occupancy"])
            days.append(
                {
                    "date": forecast["roster_date"],
                    "forecast_volume": forecast["forecast_volume"],
                    "required_agents": float(quantize(forecast["required_agents"], "0.1")),
                    "present_fte": counted["present_fte"],
                    "surplus": counted["surplus"],
                    "scheduled_headcount": counted["scheduled_headcount"],
                }
            )
        for row in conn.execute("SELECT attendance_status, COUNT(*) AS n FROM roster GROUP BY attendance_status"):
            mix[row["attendance_status"]] = row["n"]
    return {"days": days, "mix": [{"status": key, "agent_days": value} for key, value in mix.items()]}


@router.get("/audit")
def audit(request: Request, limit: int = 200):
    user = require_user(request)
    limit = min(max(limit, 1), 500)
    sql = """
        SELECT l.*, a.agent_name, a.team, a.team_lead
        FROM audit_log l
        JOIN agents a ON a.agent_id = l.agent_id
    """
    params: list = []
    if user["role"] == "agent":
        sql += " WHERE l.agent_id = ?"
        params.append(user["agent_id"])
    sql += " ORDER BY l.id DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"entries": [dict(row) for row in rows]}


def _roster_export_rows(conn, team="", team_lead="", agent_id="", status=""):
    sql = """
        SELECT r.roster_date, r.agent_id, a.agent_name, a.team, a.team_lead, r.shift,
               r.scheduled_status, r.attendance_status, r.absence_fraction,
               r.updated_by, r.updated_at
        FROM roster r
        JOIN agents a ON a.agent_id = r.agent_id
        WHERE 1 = 1
    """
    params: list = []
    if team:
        sql += " AND a.team = ?"
        params.append(team)
    if team_lead:
        sql += " AND a.team_lead = ?"
        params.append(team_lead)
    if agent_id:
        sql += " AND r.agent_id = ?"
        params.append(agent_id)
    if status:
        sql += " AND r.attendance_status = ?"
        params.append(status)
    sql += " ORDER BY r.roster_date, r.agent_id"
    return conn.execute(sql, params).fetchall()


@router.get("/export/roster.csv")
def export_roster(
    request: Request,
    team: str = "",
    team_lead: str = "",
    agent_id: str = "",
    status: str = "",
):
    user = require_user(request)
    if user["role"] == "agent":
        team = ""
        team_lead = ""
        status = ""
        agent_id = user["agent_id"]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Date",
            "Agent ID",
            "Agent Name",
            "Team",
            "Team Lead",
            "Shift",
            "Scheduled Status",
            "Attendance Status",
            "Absence Fraction",
            "Updated By",
            "Updated At",
        ]
    )
    with get_conn() as conn:
        for row in _roster_export_rows(conn, team, team_lead, agent_id, status):
            writer.writerow(
                [
                    row["roster_date"],
                    row["agent_id"],
                    row["agent_name"],
                    row["team"],
                    row["team_lead"],
                    row["shift"],
                    row["scheduled_status"],
                    row["attendance_status"],
                    row["absence_fraction"],
                    row["updated_by"] or "",
                    row["updated_at"] or "",
                ]
            )
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=roster.csv"},
    )


@router.get("/export/daily.csv")
def export_daily(request: Request, date: str):
    user = require_user(request)
    _reject_agent_desk(user)
    _check_date(date)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    with get_conn() as conn:
        center = _center_block(conn, date)
        writer.writerow(["Daily Staffing Report"])
        for label, key in [
            ("Date", "date"),
            ("Forecast Volume", "forecast_volume"),
            ("AHT Seconds", "aht_seconds"),
            ("Shrinkage", "shrinkage"),
            ("Occupancy", "occupancy"),
            ("Forecast Required Agents", "required_agents"),
            ("Scheduled Headcount", "scheduled_headcount"),
            ("Present FTE", "present_fte"),
            ("Absent FTE", "absent_fte"),
            ("Agents With A Present Portion", "present_headcount"),
            ("Available Capacity Hours", "capacity_hours"),
            ("Staffing Surplus", "surplus"),
        ]:
            writer.writerow([label, center[key]])
        writer.writerow([])
        writer.writerow(
            ["Agent ID", "Agent Name", "Team", "Team Lead", "Attendance", "Absence Fraction", "Shift", "Updated By", "Updated At"]
        )
        rows = conn.execute(
            """
            SELECT r.*, a.agent_name, a.team, a.team_lead
            FROM roster r
            JOIN agents a ON a.agent_id = r.agent_id
            WHERE r.roster_date = ? AND r.scheduled_status = 'Working' AND r.absence_fraction > 0
            ORDER BY r.agent_id
            """,
            (date,),
        ).fetchall()
        for row in rows:
            writer.writerow(
                [
                    row["agent_id"],
                    row["agent_name"],
                    row["team"],
                    row["team_lead"],
                    row["attendance_status"],
                    row["absence_fraction"],
                    row["shift"],
                    row["updated_by"] or "",
                    row["updated_at"] or "",
                ]
            )
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=daily-staffing-{date}.csv"},
    )
