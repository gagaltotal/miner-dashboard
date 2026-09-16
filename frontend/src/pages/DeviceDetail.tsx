import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useDevice, useDeleteDevice, useRenameDevice } from "../hooks/useDevices";
import { DEVICE_KIND_LABELS } from "../api/types";
import {
  formatDiff,
  formatEfficiency,
  formatHashrate,
  formatPercent,
  formatPower,
  formatRelativeTime,
  formatShares,
  formatTemp,
  formatUptime,
} from "../lib/format";
import { deviceHealth, HEALTH_COLORS } from "../lib/status";
import { StatusBadge } from "../components/StatusBadge";
import { HistoryChart } from "../components/HistoryChart";
import { FanControl } from "../components/FanControl";

export function DeviceDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: device, isLoading } = useDevice(id);
  const rename = useRenameDevice();
  const remove = useDeleteDevice();
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [showRaw, setShowRaw] = useState(false);

  if (isLoading) return <div className="py-20 text-center text-sm text-ink-faint">Memuat…</div>;
  if (!device) return <div className="py-20 text-center text-sm text-ink-faint">Perangkat tidak ditemukan.</div>;

  const health = deviceHealth(device);
  const colors = HEALTH_COLORS[health];
  const m = device.metrics;

  const handleDelete = async () => {
    if (confirm(`Hapus "${device.name}" dari dasbor? Riwayat datanya juga akan dihapus.`)) {
      await remove.mutateAsync(device.id);
      navigate("/");
    }
  };

  return (
    <div>
      <Link to="/" className="mb-4 inline-flex items-center gap-1 text-sm text-ink-muted hover:text-ink">
        ← Kembali ke dasbor
      </Link>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          {editingName ? (
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (nameDraft.trim()) await rename.mutateAsync({ id: device.id, name: nameDraft.trim() });
                setEditingName(false);
              }}
              className="flex items-center gap-2"
            >
              <input
                autoFocus
                value={nameDraft}
                onChange={(e) => setNameDraft(e.target.value)}
                onBlur={() => setEditingName(false)}
                className="rounded border border-base-border bg-base-bg px-2 py-1 text-xl font-semibold text-ink outline-none focus:border-amber"
              />
            </form>
          ) : (
            <h1
              className="cursor-pointer text-xl font-semibold text-ink hover:text-amber"
              onClick={() => {
                setNameDraft(device.name);
                setEditingName(true);
              }}
              title="Klik untuk ganti nama"
            >
              {device.name}
            </h1>
          )}
          <p className="mt-1 text-sm text-ink-muted">
            {DEVICE_KIND_LABELS[device.kind]} · {device.host}:{device.port}
            {device.metrics.firmware_version && ` · fw ${device.metrics.firmware_version}`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge state={health} />
          <button onClick={handleDelete} className="text-xs text-ink-faint hover:text-critical">
            Hapus perangkat
          </button>
        </div>
      </div>

      {!device.online && (
        <div className="mb-6 rounded-lg border border-critical/30 bg-critical-dim/10 px-4 py-3 text-sm text-critical">
          Perangkat tidak dapat dijangkau{device.last_error ? `: ${device.last_error}` : "."} Terakhir terlihat{" "}
          {formatRelativeTime(device.last_seen)}.
        </div>
      )}

      <div className="mb-6 overflow-hidden rounded-lg border border-base-border bg-base-surface">
        <div className={`h-1 ${colors.bar}`} />
        <div className="p-5">
          <div className="text-xs uppercase tracking-wide text-ink-faint">Hash rate</div>
          <div className="font-mono text-4xl font-semibold text-ink">{formatHashrate(m.hashrate_ghs)}</div>

          <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <DetailStat label="Suhu" value={formatTemp(m.temp_c)} accent={health === "warning" || health === "critical"} />
            <DetailStat label="Kipas" value={formatPercent(m.fan_percent)} sub={m.fan_rpm ? `${Math.round(m.fan_rpm)} RPM` : undefined} />
            <DetailStat label="Daya" value={formatPower(m.power_w)} />
            <DetailStat label="Efisiensi" value={formatEfficiency(m.efficiency_j_th)} />
            <DetailStat label="Shares diterima" value={formatShares(m.shares_accepted, m.shares_rejected)} />
            <DetailStat label="Rekor best share" value={formatDiff(device.best_diff)} />
            <DetailStat label="Uptime" value={formatUptime(m.uptime_s)} />
            <DetailStat label="Blok ditemukan" value={String(device.blocks_found)} accent={device.blocks_found > 0} />
          </div>

          {m.pool_url && (
            <p className="mt-4 truncate border-t border-base-border pt-3 text-xs text-ink-faint">
              Pool: <span className="text-ink-muted">{m.pool_url}</span>
            </p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <HistoryChart deviceId={device.id} />
        </div>
        <FanControl device={device} />
      </div>

      <div className="mt-6">
        <button onClick={() => setShowRaw((v) => !v)} className="text-xs text-ink-faint hover:text-ink-muted">
          {showRaw ? "Sembunyikan" : "Tampilkan"} data mentah dari perangkat (untuk pemeriksaan/debug)
        </button>
        {showRaw && (
          <pre className="mt-2 max-h-80 overflow-auto rounded-lg border border-base-border bg-base-bg p-3 text-[11px] text-ink-muted">
            {JSON.stringify(m.raw ?? {}, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}

function DetailStat({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: boolean }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-ink-faint">{label}</div>
      <div className={`font-mono text-lg ${accent ? "text-amber" : "text-ink"}`}>{value}</div>
      {sub && <div className="text-[11px] text-ink-faint">{sub}</div>}
    </div>
  );
}
