import { useEffect, useMemo, useState } from "react";
import { api, downloadCsv } from "../api";
import { dayStamp, longDate, statusClass, STATUS_SHORT, when } from "../format";
import type { Cell, Filters, Meta, User } from "../types";

const LEGEND = ["Present", "WO", "Sick Leave", "BL", "PL", "Unplanned Leave", "Comp Off", "Floating Holiday", "Special Leave", "NCNS"];

export function Roster({
  user,
  meta,
  filters,
  refreshKey,
  onChanged,
}: {
  user: User;
  meta: Meta;
  filters: Filters;
  refreshKey: number;
  onChanged: () => void;
}) {
  const [dates, setDates] = useState<string[]>([]);
  const [agents, setAgents] = useState<Meta["agents"]>([]);
  const [cells, setCells] = useState<Record<string, Cell>>({});
  const [picked, setPicked] = useState<Cell | null>(null);
  const [error, setError] = useState("");
  const [week, setWeek] = useState(0);

  function load(keep?: { agentId: string; date: string }) {
    const params = new URLSearchParams();
    if (filters.team) params.set("team", filters.team);
    if (filters.teamLead) params.set("team_lead", filters.teamLead);
    if (filters.agentId) params.set("agent_id", filters.agentId);
    if (filters.status) params.set("status", filters.status);
    api.roster(params)
      .then((body) => {
        setDates(body.dates);
        setAgents(body.agents);
        setCells(body.cells);
        setError("");
        if (keep) setPicked(body.cells[`${keep.agentId}|${keep.date}`] ?? null);
      })
      .catch((reason: Error) => setError(reason.message));
  }

  useEffect(() => {
    load();
  }, [filters, refreshKey]);

  const weeks = useMemo(() => {
    const groups: string[][] = [];
    for (let index = 0; index < dates.length; index += 7) groups.push(dates.slice(index, index + 7));
    return groups;
  }, [dates]);

  useEffect(() => {
    const index = dates.indexOf(filters.date);
    if (index >= 0) setWeek(Math.floor(index / 7));
  }, [filters.date, dates]);

  const visibleDates = weeks[week] ?? [];
  const ownDays = user.role === "agent" ? Object.values(cells) : [];
  const presentDays = ownDays.filter((day) => day.scheduled_status === "Working" && day.attendance_status === "Present").length;
  const leaveDays = ownDays.filter((day) => day.scheduled_status === "Working" && day.attendance_status !== "Present").length;
  const weeklyOffDays = ownDays.filter((day) => day.scheduled_status === "Weekly Off").length;

  return (
    <section className="roster-page">
      {user.role === "agent" && (
        <div className="kpis">
          <article className="kpi"><span>Present days</span><strong>{presentDays}</strong></article>
          <article className="kpi"><span>Leave days</span><strong>{leaveDays}</strong></article>
          <article className="kpi"><span>Weekly off</span><strong>{weeklyOffDays}</strong></article>
          <article className="kpi"><span>Days in November</span><strong>{ownDays.length}</strong></article>
        </div>
      )}
      <div className="roster-toolbar">
        <div className="legend">
          {LEGEND.map((status) => (
            <span key={status}><i className={`swatch ${statusClass(status)}`} />{status}</span>
          ))}
        </div>
        <button
          className="ghost"
          onClick={() => {
            const params = new URLSearchParams();
            if (filters.team) params.set("team", filters.team);
            if (filters.teamLead) params.set("team_lead", filters.teamLead);
            if (filters.agentId) params.set("agent_id", filters.agentId);
            if (filters.status) params.set("status", filters.status);
            downloadCsv(`/api/export/roster.csv?${params}`, "roster.csv");
          }}
        >
          Download filtered roster
        </button>
      </div>
      <div className="week-switch" role="tablist" aria-label="Weeks in November">
        {weeks.map((group, index) => {
          const start = dayStamp(group[0]);
          const end = dayStamp(group[group.length - 1]);
          return (
            <button
              key={group[0]}
              className={index === week ? "active" : ""}
              onClick={() => setWeek(index)}
            >
              {start.day}–{end.day} Nov
            </button>
          );
        })}
      </div>
      <p className="note">Click a cell to update that agent. The highlighted column is the dashboard date.</p>
      {error && <p className="error">{error}</p>}
      {agents.length === 0 && <p className="note">No agents match these filters.</p>}
      <div className="roster-wrap">
        <table className="roster">
          <thead>
            <tr>
              <th className="agent-col">Agent</th>
              {visibleDates.map((date) => {
                const stamp = dayStamp(date);
                const weekend = stamp.weekday === "Sat" || stamp.weekday === "Sun";
                return (
                  <th key={date} className={`day-col${date === filters.date ? " selected-day" : ""}${weekend ? " weekend" : ""}`}>
                    {stamp.weekday}<br />{stamp.day}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {agents.map((agent) => (
              <tr key={agent.agent_id}>
                <th className="agent-col">
                  <strong>{agent.agent_name}</strong>
                  <small>{agent.agent_id} · {agent.team} · {agent.team_lead}</small>
                </th>
                {visibleDates.map((date) => {
                  const item = cells[`${agent.agent_id}|${date}`];
                  const stamp = dayStamp(date);
                  const weekend = stamp.weekday === "Sat" || stamp.weekday === "Sun";
                  if (!item) return <td key={date} className={weekend ? "weekend" : undefined} />;
                  const label = item.absence_fraction === 0.5 ? `${STATUS_SHORT[item.attendance_status] ?? "?"}½` : (STATUS_SHORT[item.attendance_status] ?? "?");
                  return (
                    <td key={date} className={`${date === filters.date ? "selected-day" : ""}${weekend ? " weekend" : ""}`}>
                      <button
                        className={`cell-btn ${statusClass(item.attendance_status)} ${picked?.agent_id === agent.agent_id && picked.roster_date === date ? "selected-cell" : ""}`}
                        aria-label={`${agent.agent_id} ${longDate(date)} ${item.attendance_status}`}
                        title={`${item.attendance_status}${item.absence_fraction === 0.5 ? ", half day" : ""}${item.updated_by ? `. Updated by ${item.updated_by}` : ""}`}
                        onClick={() => setPicked(item)}
                      >
                        {label}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {picked && (
        <div className="drawer-backdrop" onClick={() => setPicked(null)}>
          <aside className="drawer" onClick={(event) => event.stopPropagation()} aria-label="Update attendance">
            <div className="drawer-head">
              <div>
                <p className="eyebrow">{picked.agent_id}</p>
                <h2>{picked.agent_name}</h2>
              </div>
              <button className="ghost" onClick={() => setPicked(null)}>Close</button>
            </div>
            <p className="muted">{longDate(picked.roster_date)} · {picked.team} · {picked.team_lead} · {picked.shift}</p>
            <p className="note">Scheduled: {picked.scheduled_status}. Attendance: {picked.attendance_status}{picked.absence_fraction === 0.5 ? " (half day)" : ""}.</p>
            {picked.updated_by && <p className="note">Last updated by {picked.updated_by} at {when(picked.updated_at)}.</p>}
            <Editor
              key={`${picked.agent_id}-${picked.roster_date}-${picked.version}`}
              user={user}
              meta={meta}
              cell={picked}
              onSaved={() => {
                load({ agentId: picked.agent_id, date: picked.roster_date });
                onChanged();
              }}
            />
          </aside>
        </div>
      )}
    </section>
  );
}

function Editor({
  user,
  meta,
  cell,
  onSaved,
}: {
  user: User;
  meta: Meta;
  cell: Cell;
  onSaved: () => void;
}) {
  const owns = user.role === "team_lead" && user.team_lead === cell.team_lead;
  const [status, setStatus] = useState(cell.attendance_status === "WO" ? "Sick Leave" : cell.attendance_status);
  const [dayPart, setDayPart] = useState<"Full Day" | "Half Day">(cell.absence_fraction === 0.5 ? "Half Day" : "Full Day");
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function saveAttendance() {
    setBusy(true);
    setError("");
    try {
      await api.attendance({
        roster_date: cell.roster_date,
        agent_id: cell.agent_id,
        attendance_status: status,
        day_part: status === "Present" ? "Full Day" : dayPart,
        comment,
        version: cell.version,
      });
      onSaved();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveSchedule(scheduled_status: "Working" | "Weekly Off") {
    if (!window.confirm(scheduled_status === "Weekly Off" ? "Mark this scheduled day as weekly off?" : "Schedule this weekly off as a working day?")) return;
    setBusy(true);
    setError("");
    try {
      await api.schedule({
        roster_date: cell.roster_date,
        agent_id: cell.agent_id,
        scheduled_status,
        version: cell.version,
      });
      onSaved();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      {error && <p className="error">{error}</p>}
      {user.role === "wfm" && (
        <>
          <p className="muted">RTA can change the schedule. Attendance stays with the Team Lead.</p>
          {cell.scheduled_status === "Weekly Off" ? (
            <button className="primary" disabled={busy} onClick={() => saveSchedule("Working")}>Schedule as working day</button>
          ) : (
            <button className="ghost" disabled={busy} onClick={() => saveSchedule("Weekly Off")}>Change to weekly off</button>
          )}
        </>
      )}
      {owns && cell.scheduled_status !== "Working" && (
        <p className="error">This agent is on weekly off. Ask RTA to schedule a working day first.</p>
      )}
      {owns && cell.scheduled_status === "Working" && (
        <>
          <label>Attendance status
            <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Attendance status">
              {meta.attendance_choices.map((choice) => <option key={choice}>{choice}</option>)}
            </select>
          </label>
          {status !== "Present" && (
            <label>Day
              <select value={dayPart} onChange={(event) => setDayPart(event.target.value as "Full Day" | "Half Day")} aria-label="Full or half day">
                <option>Full Day</option>
                <option>Half Day</option>
              </select>
            </label>
          )}
          <label>Comment
            <textarea value={comment} onChange={(event) => setComment(event.target.value)} aria-label="Comment" />
          </label>
          <button className="primary" disabled={busy} onClick={saveAttendance}>Save attendance</button>
        </>
      )}
      {user.role === "team_lead" && !owns && <p className="muted">You can update only your own agents.</p>}
      {user.role === "agent" && <p className="muted">Your Team Lead records this day. You can review it here.</p>}
    </div>
  );
}
