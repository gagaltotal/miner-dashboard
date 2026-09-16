import { useState } from "react";
import type { DeviceKind, DiscoveredDevice } from "../api/types";
import { DEVICE_DEFAULT_PORT, DEVICE_KIND_LABELS } from "../api/types";
import { useCreateDevice, useDiscoverDevices } from "../hooks/useDevices";
import { ApiError } from "../api/client";

const KIND_OPTIONS: DeviceKind[] = ["bitaxe", "nerdqaxe", "avalon_nano", "braiins", "luxos"];

export function AddDeviceModal({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<"scan" | "manual">("scan");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-lg border border-base-border-strong bg-base-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-base-border px-5 py-3">
          <h2 className="font-medium text-ink">Tambah perangkat</h2>
          <button onClick={onClose} className="text-ink-faint hover:text-ink" aria-label="Tutup">
            ✕
          </button>
        </div>

        <div className="flex border-b border-base-border px-5">
          <TabButton active={tab === "scan"} onClick={() => setTab("scan")}>
            Pindai jaringan
          </TabButton>
          <TabButton active={tab === "manual"} onClick={() => setTab("manual")}>
            Tambah manual
          </TabButton>
        </div>

        <div className="p-5">{tab === "scan" ? <ScanTab onClose={onClose} /> : <ManualTab onClose={onClose} />}</div>
      </div>
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`border-b-2 px-3 py-2 text-sm transition-colors ${
        active ? "border-amber text-ink" : "border-transparent text-ink-muted hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

function ScanTab({ onClose }: { onClose: () => void }) {
  const discover = useDiscoverDevices();
  const create = useCreateDevice();
  const [selected, setSelected] = useState<DiscoveredDevice | null>(null);

  if (selected) {
    return <ConfirmDiscovered device={selected} onBack={() => setSelected(null)} onClose={onClose} />;
  }

  return (
    <div>
      <p className="mb-3 text-sm text-ink-muted">
        Memindai jaringan lokal Anda untuk mencari perangkat Bitaxe, NerdQaxe, Avalon Nano, Braiins, atau LuxOS.
        Proses ini hanya menjangkau alamat IP privat di jaringan Anda sendiri.
      </p>
      <button
        onClick={() => discover.mutate()}
        disabled={discover.isPending}
        className="w-full rounded bg-amber py-2 text-sm font-medium text-base-bg transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {discover.isPending ? "Memindai jaringan… (bisa 10–30 detik)" : "Mulai pindai"}
      </button>

      {discover.isError && (
        <p className="mt-3 text-sm text-critical">
          {discover.error instanceof ApiError ? discover.error.message : "Pemindaian gagal"}
        </p>
      )}

      {discover.isSuccess && (
        <div className="mt-4 space-y-2">
          {discover.data.length === 0 ? (
            <p className="text-sm text-ink-faint">
              Tidak ada perangkat ditemukan. Pastikan perangkat menyala dan berada di jaringan yang sama, atau
              tambahkan secara manual.
            </p>
          ) : (
            discover.data.map((d, i) => (
              <button
                key={`${d.host}:${d.port}-${i}`}
                onClick={() => setSelected(d)}
                className="flex w-full items-center justify-between rounded border border-base-border px-3 py-2 text-left text-sm hover:border-base-border-strong hover:bg-base-raised"
              >
                <span>
                  <span className="text-ink">{d.suggested_name}</span>
                  <span className="ml-2 text-xs text-ink-faint">
                    {DEVICE_KIND_LABELS[d.kind]} · {d.host}:{d.port}
                  </span>
                </span>
                <span className="text-ink-faint">+</span>
              </button>
            ))
          )}
        </div>
      )}
      {create.isError && (
        <p className="mt-3 text-sm text-critical">
          {create.error instanceof ApiError ? create.error.message : "Gagal menambahkan perangkat"}
        </p>
      )}
    </div>
  );
}

function ConfirmDiscovered({
  device,
  onBack,
  onClose,
}: {
  device: DiscoveredDevice;
  onBack: () => void;
  onClose: () => void;
}) {
  const create = useCreateDevice();
  const [kind, setKind] = useState<DeviceKind>(device.kind);
  const [name, setName] = useState(device.suggested_name);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const submit = async () => {
    await create.mutateAsync({
      kind,
      name,
      host: device.host,
      port: device.port,
      username: username || undefined,
      password: password || undefined,
    });
    onClose();
  };

  return (
    <div className="space-y-3">
      <button onClick={onBack} className="text-xs text-ink-muted hover:text-ink">
        ← Kembali ke hasil pindai
      </button>
      <p className="text-xs text-ink-faint">
        Ditemukan di {device.host}:{device.port}. Jenis perangkat terdeteksi otomatis — sesuaikan jika kurang tepat.
      </p>
      <Field label="Jenis perangkat">
        <select value={kind} onChange={(e) => setKind(e.target.value as DeviceKind)} className={inputClass}>
          {KIND_OPTIONS.map((k) => (
            <option key={k} value={k}>
              {DEVICE_KIND_LABELS[k]}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Nama">
        <input value={name} onChange={(e) => setName(e.target.value)} className={inputClass} />
      </Field>
      {kind === "braiins" && (
        <>
          <Field label="Username Braiins OS+">
            <input value={username} onChange={(e) => setUsername(e.target.value)} className={inputClass} />
          </Field>
          <Field label="Password Braiins OS+">
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className={inputClass} />
          </Field>
        </>
      )}
      {create.isError && (
        <p className="text-sm text-critical">{create.error instanceof ApiError ? create.error.message : "Gagal"}</p>
      )}
      <button
        onClick={submit}
        disabled={create.isPending}
        className="w-full rounded bg-amber py-2 text-sm font-medium text-base-bg hover:opacity-90 disabled:opacity-50"
      >
        {create.isPending ? "Menambahkan…" : "Tambahkan perangkat"}
      </button>
    </div>
  );
}

function ManualTab({ onClose }: { onClose: () => void }) {
  const create = useCreateDevice();
  const [kind, setKind] = useState<DeviceKind>("bitaxe");
  const [name, setName] = useState("");
  const [host, setHost] = useState("");
  const [port, setPort] = useState<string>("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    await create.mutateAsync({
      kind,
      name: name || `${DEVICE_KIND_LABELS[kind]} baru`,
      host,
      port: port ? Number(port) : undefined,
      username: username || undefined,
      password: password || undefined,
    });
    onClose();
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <Field label="Jenis perangkat">
        <select value={kind} onChange={(e) => setKind(e.target.value as DeviceKind)} className={inputClass}>
          {KIND_OPTIONS.map((k) => (
            <option key={k} value={k}>
              {DEVICE_KIND_LABELS[k]}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Nama perangkat">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="mis. Bitaxe Ruang Server" className={inputClass} />
      </Field>
      <Field label="Alamat IP / hostname">
        <input value={host} onChange={(e) => setHost(e.target.value)} placeholder="192.168.1.50" required className={inputClass} />
      </Field>
      <Field label={`Port (kosongkan untuk default: ${DEVICE_DEFAULT_PORT[kind]})`}>
        <input
          value={port}
          onChange={(e) => setPort(e.target.value)}
          placeholder={String(DEVICE_DEFAULT_PORT[kind])}
          className={inputClass}
        />
      </Field>
      {kind === "braiins" && (
        <>
          <Field label="Username Braiins OS+">
            <input value={username} onChange={(e) => setUsername(e.target.value)} className={inputClass} />
          </Field>
          <Field label="Password Braiins OS+">
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className={inputClass} />
          </Field>
        </>
      )}
      {kind === "luxos" && (
        <p className="rounded border border-base-border bg-base-raised px-3 py-2 text-xs text-ink-muted">
          Perangkat LuxOS selalu ditambahkan dalam mode pemantauan saja (read-only) — dasbor tidak akan pernah
          mengirim perintah pengaturan ke rig ini.
        </p>
      )}
      {create.isError && (
        <p className="text-sm text-critical">{create.error instanceof ApiError ? create.error.message : "Gagal menambahkan perangkat"}</p>
      )}
      <button
        type="submit"
        disabled={create.isPending || !host}
        className="w-full rounded bg-amber py-2 text-sm font-medium text-base-bg hover:opacity-90 disabled:opacity-50"
      >
        {create.isPending ? "Menambahkan…" : "Tambahkan perangkat"}
      </button>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-ink-muted">{label}</span>
      {children}
    </label>
  );
}

const inputClass =
  "w-full rounded border border-base-border bg-base-bg px-3 py-1.5 text-sm text-ink outline-none focus:border-amber";
