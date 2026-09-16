import { useState } from "react";
import type { Device } from "../api/types";
import { useDeviceAction, useSetAutotune, useSetFan } from "../hooks/useDevices";
import { ApiError } from "../api/client";

export function FanControl({ device }: { device: Device }) {
  const setFan = useSetFan(device.id);
  const setAutotune = useSetAutotune(device.id);
  const action = useDeviceAction(device.id);
  const [manualPercent, setManualPercent] = useState(device.manual_fan_percent ?? 60);
  const [targetTemp, setTargetTemp] = useState(device.target_temp_c ?? 60);
  const [error, setError] = useState<string | null>(null);

  const caps = device.capabilities;
  const hasAnyControl = caps.fan_control || caps.autotune || caps.restart || caps.pause_resume || caps.identify;

  if (device.read_only) {
    return (
      <div className="rounded-lg border border-base-border bg-base-surface p-4 text-sm text-ink-muted">
        Perangkat ini dipantau dalam mode <span className="text-ink">read-only</span> — dasbor tidak akan pernah
        mengirim perintah pengaturan apa pun ke perangkat ini.
      </div>
    );
  }

  if (!hasAnyControl) {
    return (
      <div className="rounded-lg border border-base-border bg-base-surface p-4 text-sm text-ink-muted">
        Perangkat ini tidak mengekspos kontrol apa pun melalui API-nya — hanya pemantauan yang tersedia.
      </div>
    );
  }

  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Terjadi kesalahan tak terduga");
    }
  };

  const isAuto = device.metrics.autofan_enabled ?? false;

  return (
    <div className="space-y-4 rounded-lg border border-base-border bg-base-surface p-4">
      <h3 className="text-sm font-medium text-ink">Kontrol</h3>
      {error && <p className="rounded border border-critical/40 bg-critical-dim/20 px-3 py-2 text-xs text-critical">{error}</p>}

      {caps.fan_control && (
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs text-ink-muted">Mode kipas</span>
            <div className="flex overflow-hidden rounded border border-base-border">
              <button
                onClick={() => run(() => setFan.mutateAsync({ mode: "auto" }))}
                className={`px-3 py-1 text-xs ${isAuto ? "bg-amber text-base-bg" : "text-ink-muted hover:bg-base-raised"}`}
              >
                Otomatis
              </button>
              <button
                onClick={() => run(() => setFan.mutateAsync({ mode: "manual", manual_percent: manualPercent }))}
                className={`px-3 py-1 text-xs ${!isAuto ? "bg-amber text-base-bg" : "text-ink-muted hover:bg-base-raised"}`}
              >
                Manual
              </button>
            </div>
          </div>
          {!isAuto && (
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={0}
                max={100}
                value={manualPercent}
                onChange={(e) => setManualPercent(Number(e.target.value))}
                onMouseUp={() => run(() => setFan.mutateAsync({ mode: "manual", manual_percent: manualPercent }))}
                onTouchEnd={() => run(() => setFan.mutateAsync({ mode: "manual", manual_percent: manualPercent }))}
                className="h-1.5 flex-1 accent-amber"
              />
              <span className="w-10 shrink-0 font-mono text-sm text-ink">{manualPercent}%</span>
            </div>
          )}
        </div>
      )}

      {caps.autotune && (
        <div className="border-t border-base-border pt-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs text-ink-muted">Kontrol suhu otomatis (target)</span>
            <label className="inline-flex cursor-pointer items-center gap-2 text-xs text-ink-muted">
              <input
                type="checkbox"
                checked={device.autotune_enabled}
                onChange={(e) => run(() => setAutotune.mutateAsync({ enabled: e.target.checked, target_temp_c: targetTemp }))}
                className="accent-amber"
              />
              Aktif
            </label>
          </div>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={45}
              max={75}
              value={targetTemp}
              onChange={(e) => setTargetTemp(Number(e.target.value))}
              onMouseUp={() => run(() => setAutotune.mutateAsync({ enabled: true, target_temp_c: targetTemp }))}
              onTouchEnd={() => run(() => setAutotune.mutateAsync({ enabled: true, target_temp_c: targetTemp }))}
              className="h-1.5 flex-1 accent-teal"
            />
            <span className="w-14 shrink-0 font-mono text-sm text-ink">{targetTemp}°C</span>
          </div>
          <p className="mt-1 text-[11px] text-ink-faint">
            Perangkat menjalankan pengaturannya sendiri menuju suhu target ini. Dasbor juga menjaga batas aman
            independen di baliknya.
          </p>
        </div>
      )}

      {(caps.restart || caps.pause_resume || caps.identify) && (
        <div className="flex flex-wrap gap-2 border-t border-base-border pt-3">
          {caps.pause_resume && device.metrics.mining_paused && (
            <ActionButton onClick={() => run(() => action.mutateAsync("resume"))}>Lanjutkan penambangan</ActionButton>
          )}
          {caps.pause_resume && !device.metrics.mining_paused && (
            <ActionButton onClick={() => run(() => action.mutateAsync("pause"))}>Jeda penambangan</ActionButton>
          )}
          {caps.identify && <ActionButton onClick={() => run(() => action.mutateAsync("identify"))}>Kedipkan LED</ActionButton>}
          {caps.restart && (
            <ActionButton
              danger
              onClick={() => {
                if (confirm(`Restart ${device.name} sekarang?`)) run(() => action.mutateAsync("restart"));
              }}
            >
              Restart perangkat
            </ActionButton>
          )}
        </div>
      )}
    </div>
  );
}

function ActionButton({ children, onClick, danger }: { children: React.ReactNode; onClick: () => void; danger?: boolean }) {
  return (
    <button
      onClick={onClick}
      className={`rounded border px-3 py-1.5 text-xs transition-colors ${
        danger
          ? "border-critical/40 text-critical hover:bg-critical-dim/20"
          : "border-base-border-strong text-ink-muted hover:bg-base-raised hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}
