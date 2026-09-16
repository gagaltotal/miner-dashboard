import type { Device } from "../api/types";

export type HealthState = "offline" | "critical" | "warning" | "healthy" | "unknown";

const WARNING_TEMP_C = 68;
const CRITICAL_TEMP_C = 80;

export function deviceHealth(device: Device): HealthState {
  if (!device.online) return "offline";
  const temp = device.metrics.temp_c;
  if (temp === null || temp === undefined) return "unknown";
  if (temp >= CRITICAL_TEMP_C) return "critical";
  if (temp >= WARNING_TEMP_C) return "warning";
  return "healthy";
}

export const HEALTH_COLORS: Record<HealthState, { bar: string; text: string; dot: string }> = {
  healthy: { bar: "bg-teal", text: "text-teal", dot: "bg-teal" },
  warning: { bar: "bg-amber", text: "text-amber", dot: "bg-amber" },
  critical: { bar: "bg-critical", text: "text-critical", dot: "bg-critical" },
  offline: { bar: "bg-base-border-strong", text: "text-ink-faint", dot: "bg-ink-faint" },
  unknown: { bar: "bg-steel", text: "text-steel", dot: "bg-steel" },
};

export const HEALTH_LABELS: Record<HealthState, string> = {
  healthy: "Sehat",
  warning: "Panas",
  critical: "Kritis",
  offline: "Offline",
  unknown: "Tidak diketahui",
};
