import { useEffect, useState } from "react";
import { api, downloadCsv } from "../api";
import { fte, hours, longDate, signed } from "../format";
import type { Center, Filters, Selected } from "../types";

export function Dashboard({ filters, refreshKey }: { filters: Filters; refreshKey: number }) {
  const [center, setCenter] = useState<Center | null>(null);
  const [selected, setSelected] = useState<Selected | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const params = new URLSearchParams({ date: filters.date });
    if (filters.team) params.set("team", filters.team);
    if (filters.teamLead) params.set("team_lead", filters.teamLead);
    if (filters.agentId) params.set("agent_id", filters.agentId);
    if (filters.status) params.set("status", filters.status);
    api.dashboard(params)
      .then((body) => {
        setCenter(body.center);
        setSelected(body.selected);
        setError("");
      })
      .catch((reason: Error) => setError(reason.message));
  }, [filters, refreshKey]);

  if (error) return <p className="error">{error}</p>;
  if (!center) return <p className="muted">Loading the day...</p>;
  const surplusClass = center.surplus < 0 ? "shortfall" : "surplus";

  return (
    <section>
      <p className="section-label">Center-wide · {longDate(center.date)}</p>
      <div className="kpis">
        <article className="kpi"><span>Forecast volume</span><strong>{center.forecast_volume}</strong><em>contacts</em></article>
        <article className="kpi"><span>Forecast staffing requirement</span><strong>{center.required_agents.toFixed(1)}</strong><em>agents</em></article>
        <article className="kpi"><span>Scheduled headcount</span><strong>{center.scheduled_headcount}</strong><em>working days, not attendance</em></article>
        <article className="kpi"><span>Present FTE</span><strong>{fte(center.present_fte)}</strong><em>{center.present_headcount} with a present portion</em></article>
        <article className="kpi"><span>Leave / absence</span><strong>{fte(center.absent_fte)}</strong><em>{center.absent_headcount} agents with leave</em></article>
        <article className="kpi"><span>Available capacity</span><strong>{hours(center.capacity_hours)}</strong><em>hours</em></article>
        <article className={`kpi ${surplusClass}`}><span>Staffing surplus / shortfall</span><strong>{signed(center.surplus)}</strong><em>Present FTE minus requirement</em></article>
        <article className="kpi"><span>AHT / shrinkage / occupancy</span><strong>{center.aht_seconds}s</strong><em>{Math.round(center.shrinkage * 100)}% shrinkage · {Math.round(center.occupancy * 100)}% occupancy</em></article>
      </div>
      <p className="note">Forecast and surplus stay center-wide. A team filter does not subtract that team from the center requirement.</p>
      <div className="actions">
        <button className="primary" onClick={() => downloadCsv(`/api/export/daily.csv?date=${filters.date}`, `daily-staffing-${filters.date}.csv`)}>
          Download daily staffing report
        </button>
      </div>
      {selected && (
        <div className="card">
          <h2>Selected group</h2>
          <p className="muted">These counts follow the filters. They are not a team-level forecast.</p>
          <div className="kpis" style={{ marginTop: 12 }}>
            <article className="kpi"><span>Scheduled</span><strong>{selected.scheduled_headcount}</strong></article>
            <article className="kpi"><span>Present FTE</span><strong>{fte(selected.present_fte)}</strong><em>{selected.present_headcount} with a present portion</em></article>
            <article className="kpi"><span>Leave / absence FTE</span><strong>{fte(selected.absent_fte)}</strong><em>{selected.absent_headcount} agents</em></article>
            <article className="kpi"><span>Group capacity</span><strong>{hours(selected.capacity_hours)}</strong><em>hours</em></article>
          </div>
        </div>
      )}
    </section>
  );
}
