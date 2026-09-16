import { useToasts } from "../context/ToastContext";

const KIND_STYLES: Record<string, string> = {
  block_found: "border-amber bg-amber-dim/30",
  best_share: "border-teal bg-teal-dim/20",
  overheat_pause: "border-critical bg-critical-dim/30",
  overheat_warning: "border-critical bg-critical-dim/20",
};

export function ToastStack() {
  const { toasts, dismiss } = useToasts();

  if (toasts.length === 0) return null;

  return (
    <div className="pointer-events-none fixed inset-x-0 top-4 z-50 flex flex-col items-center gap-2 px-4 sm:items-end sm:right-4 sm:left-auto">
      {toasts.map((t) => (
        <div
          key={t.toastId}
          role="alert"
          className={`pointer-events-auto w-full max-w-sm rounded-lg border px-4 py-3 shadow-lg backdrop-blur-sm ${
            KIND_STYLES[t.kind] ?? "border-base-border-strong bg-base-raised"
          }`}
        >
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm text-ink">{t.message}</p>
            <button
              onClick={() => dismiss(t.toastId)}
              className="shrink-0 text-ink-faint hover:text-ink"
              aria-label="Tutup"
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
