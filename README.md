# Workforce roster and capacity

A small multi-user site for the November 2026 dummy roster. Team Leads update attendance. RTA changes who is scheduled. The daily surplus is calculated from the roster, not from the mismatched summary columns in the workbook.

## Run locally

From this folder:

```powershell
py -3 -m pip install -r requirements.txt
py -3 -m uvicorn app.main:app --port 8000
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

Demo password for every account: `demo123`

| User | Role |
| --- | --- |
| tl1, tl2, tl3, tl4 | Team Lead. Can update attendance for their own 10 agents on working days. |
| wfm | RTA. Can change Working / Weekly Off. Does not submit leave. |
| AGT001–AGT040 | Agent. Can open only their own November roster and their own updates. |

The database file is `data/roster.db`. It is created and seeded from `data/roster.xlsx` once. Restarting the server does not reload the workbook over saved edits. Delete `data/roster.db` if you want a fresh import.

## Checks

```powershell
py -3 -m pytest
```

2 November 2026, before any edit:

- Forecast volume 890
- Required agents 26.4
- Scheduled headcount 40
- Present FTE 37
- Absent FTE 3
- Capacity 267.33 hours
- Surplus +10.6

The forecast sheet says 36 present. The app follows the roster, which has 37.

After tl1 marks AGT001 full-day Sick Leave, scheduled headcount stays 40 and the surplus becomes +9.6.

1 November is weekly off for all 40 agents, so the surplus is -12.6. A Team Lead cannot mark attendance that day. RTA can schedule someone as Working.

## Business rules

- Scheduled headcount counts agents whose schedule is Working. Leave does not remove them from the schedule.
- Present FTE is the sum of `1 - absence fraction` for working agents. A half day is 0.5 present and 0.5 absent, and the leave reason is kept.
- Weekly off is neither present nor absent.
- Available capacity hours = Present FTE × 8.5 × occupancy.
- Center surplus = Present FTE − forecast required agents, always for all agents.
- Team, Team Lead, agent, and status filters change the roster and the selected-group counts only.

## Demo path

1. Sign in as `tl1` and open 2 November. Point out +10.6 and Present FTE 37.
2. Open the monthly roster, filter to AGT001, and mark 2 November as full-day Sick Leave.
3. Return to the dashboard. Surplus is +9.6 and scheduled headcount is still 40. Refresh the page; the change is still there.
4. Open Charts for requirement versus present, volume, the leave mix, and surplus.
5. Open Audit and show the AGT001 row.
6. Sign in as `tl2` and show that AGT001 cannot be edited.
7. Download the daily staffing report.

## Deploy

The container serves the built site and stores SQLite on a volume:

```powershell
docker compose up --build
```

Open http://localhost:8000

On Render or Railway, mount a persistent disk at `/data` and set `DATABASE_PATH=/data/roster.db` and `REQUIRE_WRITABLE_DB=1`. Do not use a host whose disk is wiped on restart. If a persistent disk is not available, use hosted Postgres instead of SQLite on a temporary filesystem.
