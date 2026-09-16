import { useMemo, useState } from "react";
import { useDevices } from "../hooks/useDevices";
import { DeviceGrid } from "../components/DeviceGrid";
import { AddDeviceModal } from "../components/AddDeviceModal";
import { formatHashrate, formatPower } from "../lib/format";

export function Dashboard() {
  const { data: devices = [], isLoading } = useDevices();
  const [showAdd, setShowAdd] = useState(false);

  const totals = useMemo(() => {
    const online = devices.filter((d) => d.online);
    const hashrate = online.reduce((sum, d) => sum + (d.metrics.hashrate_ghs ?? 0), 0);
    const power = online.reduce((sum, d) => sum + (d.metrics.power_w ?? 0), 0);
    return { onlineCount: online.length, total: devices.length, hashrate, power };
  }, [devices]);

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="grid grid-cols-3 gap-6">
          <SummaryStat label="Perangkat online" value={`${totals.onlineCount} / ${totals.total}`} />
          <SummaryStat label="Total hash rate" value={formatHashrate(totals.hashrate)} accent />
          <SummaryStat label="Total daya" value={formatPower(totals.power)} />
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="rounded bg-amber px-4 py-2 text-sm font-medium text-base-bg transition-opacity hover:opacity-90"
        >
          + Tambah perangkat
        </button>
      </div>

      {isLoading ? (
        <div className="py-20 text-center text-sm text-ink-faint">Memuat perangkat…</div>
      ) : (
        <DeviceGrid devices={devices} onAddClick={() => setShowAdd(true)} />
      )}

      {showAdd && <AddDeviceModal onClose={() => setShowAdd(false)} />}
    </div>
  );
}

function SummaryStat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-ink-faint">{label}</div>
      <div className={`font-mono text-xl font-semibold ${accent ? "text-amber" : "text-ink"}`}>{value}</div>
    </div>
  );
}
