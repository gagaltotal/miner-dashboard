import type { Device } from "../api/types";
import { DeviceCard } from "./DeviceCard";

export function DeviceGrid({ devices, onAddClick }: { devices: Device[]; onAddClick: () => void }) {
  if (devices.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-base-border py-20 text-center">
        <p className="text-ink-muted">Belum ada perangkat penambang yang ditambahkan.</p>
        <button
          onClick={onAddClick}
          className="mt-4 rounded bg-amber px-4 py-2 text-sm font-medium text-base-bg transition-opacity hover:opacity-90"
        >
          Cari & tambah perangkat
        </button>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {devices.map((d) => (
        <DeviceCard key={d.id} device={d} />
      ))}
    </div>
  );
}
