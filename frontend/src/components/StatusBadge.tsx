import { HEALTH_COLORS, HEALTH_LABELS, type HealthState } from "../lib/status";

export function StatusBadge({ state }: { state: HealthState }) {
  const colors = HEALTH_COLORS[state];
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${colors.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${colors.dot} ${state === "healthy" ? "animate-pulse" : ""}`} />
      {HEALTH_LABELS[state]}
    </span>
  );
}
