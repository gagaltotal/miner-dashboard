export function formatHashrate(ghs: number | null | undefined): string {
  if (ghs === null || ghs === undefined || Number.isNaN(ghs)) return "—";
  if (ghs >= 1_000_000) return `${(ghs / 1_000_000).toFixed(2)} PH/s`;
  if (ghs >= 1_000) return `${(ghs / 1_000).toFixed(2)} TH/s`;
  if (ghs >= 1) return `${ghs.toFixed(1)} GH/s`;
  return `${(ghs * 1000).toFixed(0)} MH/s`;
}

export function formatTemp(c: number | null | undefined): string {
  if (c === null || c === undefined || Number.isNaN(c)) return "—";
  return `${c.toFixed(1)}°C`;
}

export function formatPercent(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${Math.round(v)}%`;
}

export function formatPower(w: number | null | undefined): string {
  if (w === null || w === undefined || Number.isNaN(w)) return "—";
  return `${w.toFixed(1)} W`;
}

export function formatEfficiency(jth: number | null | undefined): string {
  if (jth === null || jth === undefined || Number.isNaN(jth)) return "—";
  return `${jth.toFixed(1)} J/TH`;
}

export function formatDiff(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  for (const [suffix, threshold] of [
    ["T", 1e12],
    ["G", 1e9],
    ["M", 1e6],
    ["K", 1e3],
  ] as const) {
    if (v >= threshold) return `${(v / threshold).toFixed(2)}${suffix}`;
  }
  return v.toFixed(0);
}

export function formatUptime(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "—";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}h ${hours}j`;
  if (hours > 0) return `${hours}j ${minutes}m`;
  return `${minutes}m`;
}

export function formatRelativeTime(ts: number | null | undefined): string {
  if (!ts) return "belum pernah";
  const diff = Date.now() / 1000 - ts;
  if (diff < 5) return "baru saja";
  if (diff < 60) return `${Math.floor(diff)} detik lalu`;
  if (diff < 3600) return `${Math.floor(diff / 60)} menit lalu`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} jam lalu`;
  return `${Math.floor(diff / 86400)} hari lalu`;
}

export function formatShares(accepted: number | null | undefined, rejected: number | null | undefined): string {
  const a = accepted ?? 0;
  const r = rejected ?? 0;
  if (!accepted && !rejected) return "—";
  const rate = a + r > 0 ? ((r / (a + r)) * 100).toFixed(1) : "0.0";
  return `${a.toLocaleString("id-ID")} (${rate}% ditolak)`;
}
