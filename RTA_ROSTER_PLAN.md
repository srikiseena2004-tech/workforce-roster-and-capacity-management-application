# Workforce roster web app

Keep the same architecture. The corrections are about workforce rules and saved data, not a new stack. FastAPI + React + TypeScript + Recharts + SQLite + one Docker process is the right size for this assessment.

The demo that matters is 2 Nov 2026: the app shows the live roster, not the Excel summary, and a Team Lead absence changes the surplus from **+10.6 to +9.6**.

## What stays

- FastAPI API, Vite React TypeScript UI, Recharts, SQLite, one process that serves the built UI.
- Workbook: `Candidate_Workforce_Roster_Assessment_Dummy_Data.xlsx`, copied to `data/roster.xlsx`. Do not read Downloads at runtime.
- 40 agents, teams Alpha, Bravo, Charlie, and Delta. Team Leads 1–4. Each Team Lead owns 10 agents across all four teams.
- November 2026 only. Forecast is one center-level row per day. Shrinkage 30%, occupancy 85%. Required agents match `(Volume × AHT / 3600) / (8.5 × (1 − shrinkage) × occupancy)`.
- Leave Entry sheet stays unused as seed data. It is blank. Real leave is already on the roster.
- No chat, payroll, notifications, shift optimizer, auth provider, or paid API.

## Schedule and attendance

The workbook has one status column. The app stores three fields so a later edit does not destroy the schedule:

- `scheduled_status`: `Working` or `Weekly Off`
- `attendance_status`: `Present`, `WO`, or a leave/exception
- `absence_fraction`: `0`, `0.5`, or `1`

Seed rule, inferred because the file has no second column:

- `WO` becomes Weekly Off, attendance `WO`, absence fraction 0.
- `Present` becomes Working, Present, fraction 0.
- Any leave becomes Working, that leave type, fraction 1.

Those people were scheduled. The leave is attendance, not a removal from the roster.

## Counts

- Scheduled headcount = agents with `scheduled_status = Working`. It does not change when a Team Lead marks Sick Leave.
- Present FTE = for Working agents, sum of `1 − absence_fraction`. Weekly Off contributes nothing.
- Absent FTE = for Working agents, sum of `absence_fraction`.
- Also show a headcount of agents who still have a present portion (`absence_fraction < 1`), so 36.5 is labeled Present FTE and not “36.5 people.”
- Available capacity hours = Present FTE × 8.5 × occupancy, shown to two decimals. This is 7.225 hours per present FTE, not the sum of each agent’s productive hours.
- Center surplus/shortfall = Present FTE − forecast required agents. Always calculated from all 40 agents.

Filters for team, Team Lead, agent, and status change the roster grid and the selected group’s scheduled, present, and absent figures only. Forecast volume, required agents, and center surplus stay center-wide and are labeled that way. Never show `team present − 26.4` as that team’s shortfall.

Half day keeps the leave reason. A half-day Sick Leave on a Present agent is attendance `Sick Leave`, absence fraction `0.5`. On 2 Nov that moves Present FTE from 37 to 36.5, absent FTE from 3 to 3.5, capacity from 267.33 to 263.71 hours, and surplus from +10.6 to +10.1. Full-day Sick Leave for the demo moves 37 to 36 and surplus from +10.6 to +9.6.

## Roles

- `tl1`–`tl4` update attendance and absence fraction only for their own agents, and only on Working days. They cannot turn a Weekly Off into a working day.
- `wfm` is the RTA user. They can change `Working` / `Weekly Off`. They do not use the Team Lead leave form to overwrite attendance.
- Seeded password for every user is `demo123`, stored with PBKDF2.

## Saves and database

Each attendance save is one database transaction: update the roster row, insert the leave entry, insert the audit row. The roster row has a version. The client sends the version it displayed. If another user saved first, return a conflict and do not overwrite.

Audit fields: date, agent id, previous attendance, new attendance, previous fraction, new fraction, updated by, timestamp, comment.

SQLite:

- Path from `DATABASE_PATH`. Local default is `data/roster.db`. Production uses a mounted writable directory such as `/data/roster.db`.
- Seed only when the database has no seed marker. A restart must not reload Excel over Team Lead edits.
- Signed HTTP-only session cookie, plus a CSRF token required on every write. Every protected route checks the logged-in user and, for Team Lead writes, ownership of that agent.
- WAL mode and a busy timeout. On startup, if the production path is not writable, fail with a clear error.
- Docker volume for `/data`. Do not put the live database inside the image. Hosted Postgres is only the fallback if the host cannot keep a disk.

## Screens

- Login.
- Daily dashboard for a selected date: forecast volume, forecast staffing requirement, scheduled headcount, Present FTE, absent FTE, available capacity hours, center surplus/shortfall. Selected-group counts stay separate when a filter is on.
- Monthly roster matrix for November 2026, color by attendance. Filters: date, team, Team Lead, agent, attendance status. Click a cell to edit. Show last updated by and at when an edit exists.
- Team Lead form: Sick Leave, BL, PL, Unplanned Leave, Comp Off, Floating Holiday, Special Leave, NCNS, and Present. Full day or half day, comment, entered-by from the logged-in user. Comment required for NCNS and Unplanned Leave. RTA schedule control is a separate Working / Weekly Off action.
- Charts from the center-wide daily series: forecast requirement vs Present FTE, forecast volume trend, attendance/leave distribution, capacity surplus/shortfall.
- Audit list, filtered roster CSV, and a Daily Staffing Report CSV for the selected date.

## Demo numbers to hit

2 Nov 2026, before any edit, from the roster rather than the forecast sheet’s 36 present:

- Volume 890, required 26.4, scheduled 40, Present FTE 37, absent FTE 3, capacity 267.33 hours, surplus **+10.6**.

After `tl1` sets `AGT001` to full-day Sick Leave: scheduled stays 40, Present FTE 36, surplus **+9.6**. Refresh and restart still show +9.6.

1 Nov 2026: 40 Weekly Off, scheduled 0, Present FTE 0, surplus **−12.6**. `tl1` cannot mark attendance on that Weekly Off. `wfm` can change one agent to Working, and scheduled headcount becomes 1.

`tl2` cannot edit `AGT001`. A second save with a stale version returns 409.

## Build order

1. Copy the workbook into `data/roster.xlsx` and seed SQLite once, splitting each roster row into scheduled status, attendance status, and absence fraction.
2. Implement hashed logins, center-wide capacity rules, transactional Team Lead attendance updates with version checks, and RTA schedule edits.
3. Build login, daily dashboard, November roster matrix, attendance form, center-wide charts, audit, and daily staffing CSV.
4. Verify 2 Nov moves from +10.6 to +9.6, weekend shortfall, and that a restart keeps the edit. Then add Docker with a persistent database path.

## Prompt to paste

```text
Build a simple multi-user workforce roster and capacity web app in this empty project. Use data/roster.xlsx (copy of Candidate_Workforce_Roster_Assessment_Dummy_Data.xlsx). Do not invent agents, dates, teams, or volumes.

Stack: FastAPI + SQLite + Vite React TypeScript + Recharts. FastAPI serves the built frontend. Add Dockerfile, requirements.txt, package.json, and a README with setup, demo logins, business rules, and Render/Railway steps using a persistent disk.

Seed once from the workbook into SQLite at DATABASE_PATH (default data/roster.db). If a seed marker already exists, do not import again. Never reset the database on restart. Use WAL and a busy timeout. In production, refuse to start if DATABASE_PATH is not writable. Store the live database on a mounted volume, not in the image.

Data:
- 40 agents. Teams Alpha, Bravo, Charlie, Delta. Team Leads 1–4, 10 agents each, spread across all teams.
- Roster dates 1–30 November 2026. The Excel status column is split on import:
  - WO -> scheduled_status Weekly Off, attendance_status WO, absence_fraction 0
  - Present -> scheduled_status Working, attendance_status Present, absence_fraction 0
  - any other status -> scheduled_status Working, attendance_status that status, absence_fraction 1
- Forecast: import date, volume, AHT seconds, shrinkage, occupancy, and required agents. Ignore the sheet’s present count and capacity hours. They disagree with the roster.
- Do not seed the blank Leave Entry rows.

Rules:
- Required agents stay the imported center values. Formula for reference: (volume * AHT / 3600) / (8.5 * (1 - shrinkage) * occupancy).
- Scheduled headcount = count of scheduled_status Working. Attendance edits must not change it.
- Present FTE = sum of (1 - absence_fraction) for Working agents. Absent FTE = sum of absence_fraction for Working agents. Weekly Off is neither present nor absent.
- Also show how many Working agents have absence_fraction < 1, labeled separately from Present FTE.
- Available capacity hours = Present FTE * 8.5 * occupancy, two decimals.
- Center surplus = Present FTE - required agents, always from all agents. Filters never change this number.
- Team, Team Lead, agent, and status filters only narrow the roster and the selected group’s scheduled, present, and absent figures. Label forecast and center surplus as center-wide. Do not subtract a team’s present count from the center requirement.
- Half day stores the leave reason and absence_fraction 0.5.

Users, password demo123, stored with PBKDF2:
- tl1–tl4 can change attendance_status and absence_fraction only for their own agents, only when scheduled_status is Working. Comment required for NCNS and Unplanned Leave. They cannot change Weekly Off.
- wfm can change scheduled_status between Working and Weekly Off. wfm does not submit the leave form.

Attendance save is one transaction: roster update, leave entry, audit row. Roster has a version; the update must match the version sent by the client or return 409. Audit stores date, agent id, previous and new attendance, previous and new fraction, user, timestamp, and comment. Show last updated by and at on edited cells.

Auth: signed HTTP-only session cookie, CSRF token on every write, authorization checked inside every protected route.

Screens:
1. Login.
2. Daily dashboard: volume, required agents, scheduled headcount, Present FTE, absent FTE, capacity hours, center surplus. Selected-group counts stay separate when a filter is on.
3. November roster matrix, color by attendance. Filters: date, team, Team Lead, agent, attendance. Click a cell to edit. Show last editor and time.
4. Team Lead form: the eight exception types plus Present, full or half day, comment. RTA schedule control is a separate Working / Weekly Off action.
5. Charts from center-wide daily series: required vs Present FTE, volume trend, attendance/leave mix, surplus/shortfall.
6. Audit list, filtered roster CSV, and a Daily Staffing Report CSV for the selected date.

Verify before finishing:
- 2 Nov 2026 before edits: volume 890, required 26.4, scheduled 40, Present FTE 37, absent FTE 3, capacity 267.33, surplus +10.6. Not the sheet’s 36 present.
- tl1 full-day Sick Leave on AGT001: scheduled stays 40, Present FTE 36, surplus +9.6. Refresh and process restart keep +9.6.
- Same agent as half-day Sick Leave would be Present FTE 36.5, absent FTE 3.5, capacity 263.71, surplus +10.1. Use the full-day case for the main demo.
- 1 Nov 2026: 40 Weekly Off, surplus -12.6. tl1 cannot edit that day. wfm can set one agent to Working.
- tl2 cannot edit AGT001.
- A second save with a stale version returns 409.
```
