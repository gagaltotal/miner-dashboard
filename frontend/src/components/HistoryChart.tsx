import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useDeviceHistory } from "../hooks/useDevices";
import type { HistoryPoint, HistoryRange } from "../api/types";

const RANGE_OPTIONS: { value: HistoryRange; label: string }[] = [
  { value: "1h", label: "1 jam" },
  { value: "24h", label: "24 jam" },
  { value: "7d", label: "7 hari" },
  { value: "30d", label: "30 hari" },
];

function formatTick(range: HistoryRange) {
  return (ts: number) => {
    const d = new Date(ts * 1000);
    if (range === "1h" || range === "24h") {
      return d.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
    }
    return d.toLocaleDateString("id-ID", { day: "2-digit", month: "short" });
  };
}

function ChartTooltip({ active, payload, label, unit }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded border border-base-border-strong bg-base-raised px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 text-ink-faint">{new Date(label * 1000).toLocaleString("id-ID")}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} style={{ color: p.color }}>
          {p.name}: {typeof p.value === "number" ? p.value.toFixed(1) : "—"}
          {unit}
        </p>
      ))}
    </div>
  );
}

export function HistoryChart({ deviceId }: { deviceId: string }) {
  const [range, setRange] = useState<HistoryRange>("24h");
  const { data, isLoading } = useDeviceHistory(deviceId, range);
  const points: HistoryPoint[] = data?.points ?? [];
  const tickFormatter = formatTick(range);

  return (
    <div className="rounded-lg border border-base-border bg-base-surface p-4">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-medium text-ink">Riwayat</h3>
        <div className="flex gap-1">
          {RANGE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setRange(opt.value)}
              className={`rounded px-2.5 py-1 text-xs transition-colors ${
                range === opt.value ? "bg-amber text-base-bg" : "text-ink-muted hover:bg-base-raised"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex h-64 items-center justify-center text-sm text-ink-faint">Memuat grafik…</div>
      ) : points.length === 0 ? (
        <div className="flex h-64 items-center justify-center text-sm text-ink-faint">
          Belum ada data riwayat untuk rentang ini.
        </div>
      ) : (
        <>
          <div className="mb-1 text-xs text-ink-muted">Hash rate (GH/s)</div>
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={points} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#362F24" vertical={false} />
              <XAxis dataKey="ts" tickFormatter={tickFormatter} stroke="#6B6154" fontSize={11} tickLine={false} />
              <YAxis stroke="#6B6154" fontSize={11} tickLine={false} width={44} />
              <Tooltip content={<ChartTooltip unit=" GH/s" />} />
              <Line type="monotone" dataKey="hashrate_ghs" name="Hash rate" stroke="#E3953C" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>

          <div className="mb-1 mt-4 text-xs text-ink-muted">Suhu (°C) &amp; Kipas (%)</div>
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={points} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#362F24" vertical={false} />
              <XAxis dataKey="ts" tickFormatter={tickFormatter} stroke="#6B6154" fontSize={11} tickLine={false} />
              <YAxis stroke="#6B6154" fontSize={11} tickLine={false} width={44} />
              <Tooltip content={<ChartTooltip unit="" />} />
              <Line type="monotone" dataKey="temp_c" name="Suhu" stroke="#E5555A" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="fan_percent" name="Kipas" stroke="#3FCDB0" dot={false} strokeWidth={1.5} strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
}
