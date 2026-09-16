import { Link } from "react-router-dom";
import type { Device } from "../api/types";
import { DEVICE_KIND_LABELS } from "../api/types";
import { formatEfficiency, formatHashrate, formatPercent, formatPower, formatTemp, formatUptime } from "../lib/format";
import { deviceHealth, HEALTH_COLORS } from "../lib/status";
import { StatusBadge } from "./StatusBadge";

export function DeviceCard({ device }: { device: Device }) {
  const health = deviceHealth(device);
  const colors = HEALTH_COLORS[health];
  const m = device.metrics;

  return (
    <Link
      to={`/devices/${device.id}`}
      className="group relative flex overflow-hidden rounded-lg border border-base-border bg-base-surface transition-colors hover:border-base-border-strong"
    >
      <div className={`w-1 shrink-0 ${colors.bar}`} aria-hidden />
      <div className="flex-1 p-4">
        <div className="mb-3 flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="truncate font-medium text-ink">{device.name}</h3>
            <p className="text-xs text-ink-muted">
              {DEVICE_KIND_LABELS[device.kind]}
              {device.read_only && <span className="ml-1.5 text-ink-faint">· pantau saja</span>}
            </p>
          </div>
          <StatusBadge state={health} />
        </div>

        <div className="mb-3 font-mono text-2xl font-semibold text-ink">
          {device.online ? formatHashrate(m.hashrate_ghs) : <span className="text-ink-faint">— GH/s</span>}
        </div>

        <div className="grid grid-cols-4 gap-2 text-xs">
          <Stat label="Suhu" value={formatTemp(m.temp_c)} accent={health === "critical" || health === "warning"} />
          <Stat label="Kipas" value={formatPercent(m.fan_percent)} />
          <Stat label="Daya" value={formatPower(m.power_w)} />
          <Stat label="Efisiensi" value={formatEfficiency(m.efficiency_j_th)} />
        </div>

        {device.online && (
          <div className="mt-3 flex items-center justify-between border-t border-base-border pt-2 text-xs text-ink-muted">
            <span>Uptime {formatUptime(m.uptime_s)}</span>
            <span>
              {(m.shares_accepted ?? 0).toLocaleString("id-ID")} shares
            </span>
          </div>
        )}
        {!device.online && device.last_error && (
          <p className="mt-3 truncate border-t border-base-border pt-2 text-xs text-critical" title={device.last_error}>
            {device.last_error}
          </p>
        )}
      </div>
    </Link>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-ink-faint">{label}</div>
      <div className={`font-mono ${accent ? "text-amber" : "text-ink"}`}>{value}</div>
    </div>
  );
}
