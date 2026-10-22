import { ApiError, type Agent, type AuditEntry, type Cell, type Center, type ChartDay, type Meta, type Selected, type User } from "./types";

let csrf = "";

export function setCsrf(token: string) {
  csrf = token;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  if (csrf && options.method && options.method !== "GET") headers.set("X-CSRF-Token", csrf);
  const response = await fetch(path, { ...options, headers, credentials: "include" });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      detail = response.statusText;
    }
    throw new ApiError(detail || "Request failed", response.status);
  }
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json() as Promise<T>;
  return response as unknown as T;
}

export const api = {
  me: () => request<User | { authenticated: false }>("/api/me"),
  login: (username: string, password: string) =>
    request<User>("/api/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  logout: () => request<{ ok: boolean }>("/api/logout", { method: "POST" }),
  meta: () => request<Meta>("/api/meta"),
  dashboard: (params: URLSearchParams) => request<{ center: Center; selected: Selected | null }>(`/api/dashboard?${params}`),
  roster: (params: URLSearchParams) =>
    request<{ dates: string[]; agents: Agent[]; cells: Record<string, Cell> }>(`/api/roster?${params}`),
  charts: () => request<{ days: ChartDay[]; mix: { status: string; agent_days: number }[] }>("/api/charts"),
  audit: () => request<{ entries: AuditEntry[] }>("/api/audit"),
  attendance: (body: {
    roster_date: string;
    agent_id: string;
    attendance_status: string;
    day_part: "Full Day" | "Half Day";
    comment: string;
    version: number;
  }) => request<{ ok: boolean; cell: Cell }>("/api/attendance", { method: "POST", body: JSON.stringify(body) }),
  schedule: (body: { roster_date: string; agent_id: string; scheduled_status: "Working" | "Weekly Off"; version: number }) =>
    request<{ ok: boolean; cell: Cell }>("/api/schedule", { method: "POST", body: JSON.stringify(body) }),
};

export async function downloadCsv(path: string, filename: string) {
  const response = await fetch(path, { credentials: "include" });
  if (!response.ok) throw new ApiError("Download failed", response.status);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
