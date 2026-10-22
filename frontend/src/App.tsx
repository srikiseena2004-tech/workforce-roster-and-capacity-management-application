import { FormEvent, useEffect, useState } from "react";
import { api, setCsrf } from "./api";
import { Audit } from "./pages/Audit";
import { Charts } from "./pages/Charts";
import { Dashboard } from "./pages/Dashboard";
import { Roster } from "./pages/Roster";
import type { Filters, Meta, User } from "./types";

type View = "dashboard" | "roster" | "charts" | "audit";

const EMPTY_FILTERS: Filters = { date: "2026-11-02", team: "", teamLead: "", agentId: "", status: "" };

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [ready, setReady] = useState(false);
  const [view, setView] = useState<View>("dashboard");
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    api.me()
      .then(async (signedIn) => {
        if (!("username" in signedIn)) {
          setUser(null);
          return;
        }
        setCsrf(signedIn.csrf_token);
        setUser(signedIn);
        if (signedIn.role === "agent") setView("roster");
        setMeta(await api.meta());
      })
      .catch(() => setUser(null))
      .finally(() => setReady(true));
  }, []);

  async function onLogin(signedIn: User) {
    setCsrf(signedIn.csrf_token);
    setUser(signedIn);
    setMeta(await api.meta());
    setView(signedIn.role === "agent" ? "roster" : "dashboard");
  }

  async function onLogout() {
    await api.logout();
    setCsrf("");
    setUser(null);
    setMeta(null);
  }

  if (!ready) return <p className="login-screen">Loading...</p>;
  if (!user || !meta) return <Login onLogin={onLogin} />;

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <div className="mark">R</div>
          <div>
            <p className="eyebrow">November 2026</p>
            <strong>Workforce roster</strong>
          </div>
        </div>
        <div className="who">
          <span className="user-pill">{pill(user)}</span>
          <button className="ghost" onClick={onLogout}>Sign out</button>
        </div>
      </header>
      <nav className="nav">
        {(user.role === "agent" ? (["roster", "audit"] as View[]) : (["dashboard", "roster", "charts", "audit"] as View[])).map((item) => (
          <button key={item} className={view === item ? "active" : ""} onClick={() => setView(item)}>
            {navLabel(item, user.role)}
          </button>
        ))}
      </nav>
      {user.role === "agent" && meta.agents[0] && (
        <section className="card profile">
          <p className="eyebrow">{meta.agents[0].agent_id}</p>
          <h2>{meta.agents[0].agent_name}</h2>
          <p className="muted">{meta.agents[0].team} · {meta.agents[0].team_lead} · Shift {meta.agents[0].default_shift}</p>
          <p className="note">This is your November record. Your Team Lead updates attendance, and this page is for review.</p>
        </section>
      )}
      {user.role !== "agent" && (view === "dashboard" || view === "roster") && (
        <form className="filters card" onSubmit={(event) => event.preventDefault()}>
          <label>Date
            <input type="date" min="2026-11-01" max="2026-11-30" value={filters.date} aria-label="Date" onChange={(event) => setFilters({ ...filters, date: event.target.value })} />
          </label>
          <label>Team
            <select aria-label="Team" value={filters.team} onChange={(event) => setFilters({ ...filters, team: event.target.value })}>
              <option value="">All teams</option>
              {meta.teams.map((team) => <option key={team}>{team}</option>)}
            </select>
          </label>
          <label>Team Lead
            <select aria-label="Team Lead" value={filters.teamLead} onChange={(event) => setFilters({ ...filters, teamLead: event.target.value })}>
              <option value="">All Team Leads</option>
              {meta.team_leads.map((lead) => <option key={lead}>{lead}</option>)}
            </select>
          </label>
          <label>Agent
            <select aria-label="Agent" value={filters.agentId} onChange={(event) => setFilters({ ...filters, agentId: event.target.value })}>
              <option value="">All agents</option>
              {meta.agents.map((agent) => <option key={agent.agent_id} value={agent.agent_id}>{agent.agent_id} · {agent.agent_name}</option>)}
            </select>
          </label>
          <label>Attendance status
            <select aria-label="Attendance status" value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}>
              <option value="">All statuses</option>
              {meta.statuses.map((status) => <option key={status}>{status}</option>)}
            </select>
          </label>
        </form>
      )}
      <main className="content">
        {view === "dashboard" && user.role !== "agent" && <Dashboard filters={filters} refreshKey={refreshKey} />}
        {view === "roster" && (
          <Roster user={user} meta={meta} filters={filters} refreshKey={refreshKey} onChanged={() => setRefreshKey((value) => value + 1)} />
        )}
        {view === "charts" && user.role !== "agent" && <Charts />}
        {view === "audit" && <Audit refreshKey={refreshKey} mine={user.role === "agent"} />}
      </main>
    </div>
  );
}

function pill(user: User) {
  if (user.role === "wfm") return "RTA";
  if (user.role === "agent") return `${user.agent_id} · ${user.agent_name}`;
  return user.team_lead;
}

function navLabel(item: View, role: User["role"]) {
  if (role === "agent" && item === "roster") return "My month";
  if (role === "agent" && item === "audit") return "My updates";
  if (item === "dashboard") return "Daily dashboard";
  if (item === "roster") return "Monthly roster";
  if (item === "charts") return "Charts";
  return "Audit";
}

const AGENT_IDS = Array.from({ length: 40 }, (_, index) => `AGT${String(index + 1).padStart(3, "0")}`);

function Login({ onLogin }: { onLogin: (user: User) => Promise<void> }) {
  const [username, setUsername] = useState("tl1");
  const [password, setPassword] = useState("demo123");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const signedIn = await api.login(username.trim(), password);
      await onLogin(signedIn);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Sign in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={submit}>
        <p className="eyebrow">RTA assessment</p>
        <h1>Workforce roster</h1>
        <p className="lede">November 2026 capacity desk. Team Leads update attendance. Agents can open their own record. RTA changes the schedule.</p>
        <div className="stack">
          {error && <p className="error">{error}</p>}
          <label>Username
            <input aria-label="Username" value={username} onChange={(event) => setUsername(event.target.value)} />
          </label>
          <label>Password
            <input aria-label="Password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          <button className="primary" type="submit" disabled={busy}>Sign in</button>
          <div className="chips">
            {["wfm", "tl1", "tl2", "tl3", "tl4"].map((name) => (
              <button key={name} type="button" className="chip" onClick={() => { setUsername(name); setPassword("demo123"); }}>{name}</button>
            ))}
          </div>
          <label>Agent login
            <select
              aria-label="Agent login"
              value={AGENT_IDS.includes(username) ? username : ""}
              onChange={(event) => { setUsername(event.target.value); setPassword("demo123"); }}
            >
              <option value="">Choose your agent ID</option>
              {AGENT_IDS.map((agentId) => <option key={agentId} value={agentId}>{agentId}</option>)}
            </select>
          </label>
          <p className="muted">Password for every account, including each agent: demo123</p>
        </div>
      </form>
    </div>
  );
}
