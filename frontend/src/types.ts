export type Role = "wfm" | "team_lead" | "agent";

export type User = {
  username: string;
  role: Role;
  team_lead: string | null;
  agent_id: string | null;
  agent_name: string | null;
  csrf_token: string;
  authenticated?: boolean;
};

export type Center = {
  date: string;
  forecast_volume: number;
  aht_seconds: number;
  shrinkage: number;
  occupancy: number;
  required_agents: number;
  scheduled_headcount: number;
  present_fte: number;
  present_headcount: number;
  absent_fte: number;
  absent_headcount: number;
  capacity_hours: number;
  surplus: number;
};

export type Selected = {
  scheduled_headcount: number;
  present_fte: number;
  present_headcount: number;
  absent_fte: number;
  absent_headcount: number;
  capacity_hours: number;
};

export type Agent = {
  agent_id: string;
  agent_name: string;
  team: string;
  team_lead: string;
  default_shift: string;
};

export type Cell = {
  roster_date: string;
  agent_id: string;
  agent_name: string;
  team: string;
  team_lead: string;
  shift: string;
  scheduled_status: string;
  attendance_status: string;
  absence_fraction: number;
  version: number;
  updated_by: string | null;
  updated_at: string | null;
};

export type Meta = {
  teams: string[];
  team_leads: string[];
  agents: Agent[];
  statuses: string[];
  attendance_choices: string[];
  dates: string[];
};

export type Filters = {
  date: string;
  team: string;
  teamLead: string;
  agentId: string;
  status: string;
};

export type AuditEntry = {
  id: number;
  roster_date: string;
  agent_id: string;
  agent_name: string;
  team: string;
  team_lead: string;
  previous_attendance: string | null;
  new_attendance: string | null;
  previous_fraction: number | null;
  new_fraction: number | null;
  previous_scheduled: string | null;
  new_scheduled: string | null;
  updated_by: string;
  updated_at: string;
  comment: string;
};

export type ChartDay = {
  date: string;
  forecast_volume: number;
  required_agents: number;
  present_fte: number;
  surplus: number;
  scheduled_headcount: number;
};

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}
