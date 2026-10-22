export function fte(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export function signed(value: number) {
  const text = value.toFixed(1);
  return value > 0 ? `+${text}` : text;
}

export function hours(value: number) {
  return value.toFixed(2);
}

export function dayStamp(iso: string) {
  const date = new Date(`${iso}T00:00:00`);
  return {
    weekday: date.toLocaleDateString("en-GB", { weekday: "short" }),
    day: date.getDate(),
  };
}

export function longDate(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function when(iso: string | null) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export const STATUS_SHORT: Record<string, string> = {
  Present: "P",
  WO: "WO",
  "Sick Leave": "SL",
  BL: "BL",
  PL: "PL",
  "Unplanned Leave": "UL",
  "Comp Off": "CO",
  "Floating Holiday": "FH",
  "Special Leave": "SP",
  NCNS: "NC",
};

export function statusClass(status: string) {
  return `st-${status.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}
