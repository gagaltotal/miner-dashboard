import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api, ApiError } from "../api/client";
import { useDeleteDevice, useDevices, useGlobalSettings, useRenameDevice, useUpdateGlobalSettings } from "../hooks/useDevices";
import { DEVICE_KIND_LABELS } from "../api/types";

export function Settings() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <GeneralSettings />
      <DeviceManagement />
      <PasswordSettings />
      <AboutSection />
    </div>
  );
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-base-border bg-base-surface p-5">
      <h2 className="mb-4 text-sm font-medium text-ink">{title}</h2>
      {children}
    </div>
  );
}

function GeneralSettings() {
  const { data: settings, isLoading } = useGlobalSettings();
  const update = useUpdateGlobalSettings();
  const [pollInterval, setPollInterval] = useState<number | null>(null);
  const [retention, setRetention] = useState<number | null>(null);

  if (isLoading || !settings) return null;

  return (
    <SectionCard title="Umum">
      <div className="space-y-4">
        <label className="block">
          <span className="mb-1 block text-xs text-ink-muted">Interval polling (detik)</span>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={5}
              max={120}
              value={pollInterval ?? settings.poll_interval_seconds}
              onChange={(e) => setPollInterval(Number(e.target.value))}
              onMouseUp={() => pollInterval && update.mutate({ poll_interval_seconds: pollInterval })}
              onTouchEnd={() => pollInterval && update.mutate({ poll_interval_seconds: pollInterval })}
              className="h-1.5 flex-1 accent-amber"
            />
            <span className="w-14 font-mono text-sm text-ink">{pollInterval ?? settings.poll_interval_seconds}s</span>
          </div>
        </label>

        <label className="block">
          <span className="mb-1 block text-xs text-ink-muted">Retensi riwayat (hari)</span>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={1}
              max={90}
              value={retention ?? settings.history_retention_days}
              onChange={(e) => setRetention(Number(e.target.value))}
              onMouseUp={() => retention && update.mutate({ history_retention_days: retention })}
              onTouchEnd={() => retention && update.mutate({ history_retention_days: retention })}
              className="h-1.5 flex-1 accent-amber"
            />
            <span className="w-14 font-mono text-sm text-ink">{retention ?? settings.history_retention_days}h</span>
          </div>
        </label>

        <p className="text-[11px] text-ink-faint">
          Semua data (riwayat, notifikasi, kredensial perangkat) tersimpan lokal di berkas SQLite pada mesin yang
          menjalankan dasbor ini — tidak ada yang dikirim ke layanan luar.
        </p>
      </div>
    </SectionCard>
  );
}

function DeviceManagement() {
  const { data: devices = [] } = useDevices();
  const rename = useRenameDevice();
  const remove = useDeleteDevice();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  return (
    <SectionCard title="Kelola perangkat">
      {devices.length === 0 ? (
        <p className="text-sm text-ink-faint">Belum ada perangkat.</p>
      ) : (
        <div className="divide-y divide-base-border">
          {devices.map((d) => (
            <div key={d.id} className="flex items-center justify-between gap-3 py-2.5">
              {editingId === d.id ? (
                <form
                  className="flex-1"
                  onSubmit={async (e) => {
                    e.preventDefault();
                    if (draft.trim()) await rename.mutateAsync({ id: d.id, name: draft.trim() });
                    setEditingId(null);
                  }}
                >
                  <input
                    autoFocus
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onBlur={() => setEditingId(null)}
                    className="w-full rounded border border-base-border bg-base-bg px-2 py-1 text-sm text-ink outline-none focus:border-amber"
                  />
                </form>
              ) : (
                <div className="min-w-0">
                  <p className="truncate text-sm text-ink">{d.name}</p>
                  <p className="text-xs text-ink-faint">
                    {DEVICE_KIND_LABELS[d.kind]} · {d.host}:{d.port}
                  </p>
                </div>
              )}
              <div className="flex shrink-0 gap-2 text-xs">
                <button
                  onClick={() => {
                    setDraft(d.name);
                    setEditingId(d.id);
                  }}
                  className="text-ink-faint hover:text-ink"
                >
                  Ganti nama
                </button>
                <button
                  onClick={() => confirm(`Hapus "${d.name}"?`) && remove.mutate(d.id)}
                  className="text-ink-faint hover:text-critical"
                >
                  Hapus
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  );
}

function PasswordSettings() {
  const { logout } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirmNext, setConfirmNext] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    if (next !== confirmNext) {
      setError("Konfirmasi password baru tidak cocok");
      return;
    }
    if (next.length < 8) {
      setError("Password baru minimal 8 karakter");
      return;
    }
    setBusy(true);
    try {
      await api.auth.changePassword(current, next);
      setSuccess(true);
      setCurrent("");
      setNext("");
      setConfirmNext("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal mengganti password");
    } finally {
      setBusy(false);
    }
  };

  return (
    <SectionCard title="Keamanan akun">
      <form onSubmit={submit} className="space-y-3">
        <label className="block">
          <span className="mb-1 block text-xs text-ink-muted">Password saat ini</span>
          <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required className={inputClass} />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-ink-muted">Password baru</span>
          <input type="password" value={next} onChange={(e) => setNext(e.target.value)} required minLength={8} className={inputClass} />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-ink-muted">Konfirmasi password baru</span>
          <input type="password" value={confirmNext} onChange={(e) => setConfirmNext(e.target.value)} required className={inputClass} />
        </label>
        {error && <p className="text-sm text-critical">{error}</p>}
        {success && <p className="text-sm text-teal">Password berhasil diganti.</p>}
        <button
          type="submit"
          disabled={busy}
          className="rounded bg-amber px-4 py-1.5 text-sm font-medium text-base-bg hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Menyimpan…" : "Ganti password"}
        </button>
      </form>
      <button onClick={() => logout()} className="mt-4 text-xs text-ink-faint hover:text-ink">
        Keluar dari sesi ini
      </button>
    </SectionCard>
  );
}

function AboutSection() {
  return (
    <SectionCard title="Tentang">
      <ul className="space-y-1.5 text-xs text-ink-muted">
        <li>• Tidak ada koneksi ke layanan cloud atau telemetri pihak ketiga.</li>
        <li>• Semua polling perangkat hanya menjangkau alamat IP privat di jaringan lokal Anda.</li>
        <li>• Perangkat LuxOS selalu diperlakukan sebagai read-only — tidak pernah menerima perintah pengaturan.</li>
        <li>• Data (riwayat, notifikasi) tersimpan dalam berkas SQLite lokal di folder data dasbor.</li>
      </ul>
    </SectionCard>
  );
}

const inputClass =
  "w-full rounded border border-base-border bg-base-bg px-3 py-1.5 text-sm text-ink outline-none focus:border-amber";
