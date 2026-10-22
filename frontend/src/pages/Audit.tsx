import { useEffect, useState } from "react";
import { api } from "../api";
import { longDate, when } from "../format";
import type { AuditEntry } from "../types";

export function Audit({ refreshKey, mine = false }: { refreshKey: number; mine?: boolean }) {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setLoaded(false);
    api.audit()
      .then((body) => {
        setEntries(body.entries);
        setError("");
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoaded(true));
  }, [refreshKey]);

  if (error) return <p className="error">{error}</p>;
  if (!loaded) return <p className="muted">Loading audit...</p>;

  return (
    <section className="card">
      <h2>{mine ? "Your attendance updates" : "Attendance audit"}</h2>
      <p className="muted">{mine ? "Changes your Team Lead or RTA saved on your roster." : "Each Team Lead or RTA save is stored with the previous value."}</p>
      {entries.length === 0 ? (
        <p className="note">No saved changes yet. This list records edits, so the imported roster does not appear here. To create the first row, sign in as tl1, open Monthly roster, and save AGT001 on 2 November as full-day Sick Leave. Scheduled headcount stays 40 and the surplus moves from +10.6 to +9.6.</p>
      ) : (
        <table className="plain">
          <thead>
            <tr>
              <th>When</th>
              <th>Agent</th>
              <th>Date</th>
              <th>Change</th>
              <th>By</th>
              <th>Comment</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.id}>
                <td>{when(entry.updated_at)}</td>
                <td>{entry.agent_id}<br /><span className="muted">{entry.agent_name}</span></td>
                <td>{longDate(entry.roster_date)}</td>
                <td>
                  {entry.previous_scheduled !== entry.new_scheduled && <div>{entry.previous_scheduled} → {entry.new_scheduled}</div>}
                  <div>{entry.previous_attendance} → {entry.new_attendance}</div>
                  <div className="muted">Fraction {entry.previous_fraction} → {entry.new_fraction}</div>
                </td>
                <td>{entry.updated_by}</td>
                <td>{entry.comment}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
