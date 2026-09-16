import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../api/client";

export function Login() {
  const { state, setup, login } = useAuth();
  const isSetup = state.status === "needs_setup";
  const [username, setUsername] = useState(isSetup ? "admin" : "");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (isSetup && password !== confirmPassword) {
      setError("Konfirmasi password tidak cocok");
      return;
    }
    if (isSetup && password.length < 8) {
      setError("Password minimal 8 karakter");
      return;
    }

    setBusy(true);
    try {
      if (isSetup) {
        await setup(username, password);
      } else {
        await login(username, password);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Terjadi kesalahan tak terduga");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2">
          <svg width="40" height="40" viewBox="0 0 64 64" fill="none">
            <rect width="64" height="64" rx="12" fill="#1E1B16" />
            <rect x="17" y="34" width="6" height="13" rx="1.5" fill="#3FCDB0" />
            <rect x="27" y="26" width="6" height="21" rx="1.5" fill="#E3953C" />
            <rect x="37" y="18" width="6" height="29" rx="1.5" fill="#E3953C" />
            <circle cx="47" cy="17" r="3" fill="#E5555A" />
          </svg>
          <h1 className="font-medium text-ink">Dasbor Penambang</h1>
          <p className="text-center text-xs text-ink-faint">Pemantauan lokal — tanpa cloud, tanpa telemetri</p>
        </div>

        <form onSubmit={submit} className="space-y-3 rounded-lg border border-base-border bg-base-surface p-5">
          <h2 className="text-sm font-medium text-ink">
            {isSetup ? "Buat akun operator (satu kali)" : "Masuk"}
          </h2>

          <label className="block">
            <span className="mb-1 block text-xs text-ink-muted">Username</span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
              className={inputClass}
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-ink-muted">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={isSetup ? 8 : undefined}
              className={inputClass}
            />
          </label>
          {isSetup && (
            <label className="block">
              <span className="mb-1 block text-xs text-ink-muted">Konfirmasi password</span>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className={inputClass}
              />
            </label>
          )}

          {error && <p className="text-sm text-critical">{error}</p>}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded bg-amber py-2 text-sm font-medium text-base-bg transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Memproses…" : isSetup ? "Buat akun & masuk" : "Masuk"}
          </button>

          {isSetup && (
            <p className="text-[11px] text-ink-faint">
              Akun ini hanya tersimpan secara lokal di perangkat ini dan dipakai untuk mengamankan akses ke dasbor
              dari perangkat lain di jaringan Anda.
            </p>
          )}
        </form>
      </div>
    </div>
  );
}

const inputClass =
  "w-full rounded border border-base-border bg-base-bg px-3 py-1.5 text-sm text-ink outline-none focus:border-amber";
