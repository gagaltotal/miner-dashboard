import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import type { NotificationItem } from "../api/types";

interface Toast extends NotificationItem {
  toastId: number;
}

interface ToastContextValue {
  toasts: Toast[];
  push: (n: NotificationItem) => void;
  dismiss: (toastId: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

/** Only pop a native OS notification when the tab is in the background —
 * the in-app toast already covers the foreground case, and duplicating both
 * would be noisy. Permission is requested lazily on the first notification
 * rather than on page load, so we don't nag the user with a permission
 * prompt before they've seen any value from the dashboard. */
function maybeShowBrowserNotification(n: NotificationItem) {
  if (typeof Notification === "undefined" || !document.hidden) return;
  if (Notification.permission === "granted") {
    new Notification("Dasbor Penambang", { body: n.message, tag: `note-${n.id}` });
  } else if (Notification.permission !== "denied") {
    Notification.requestPermission().then((perm) => {
      if (perm === "granted") new Notification("Dasbor Penambang", { body: n.message, tag: `note-${n.id}` });
    });
  }
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const counter = useRef(0);

  const dismiss = useCallback((toastId: number) => {
    setToasts((prev) => prev.filter((t) => t.toastId !== toastId));
  }, []);

  const push = useCallback(
    (n: NotificationItem) => {
      const toastId = ++counter.current;
      setToasts((prev) => [...prev, { ...n, toastId }]);
      maybeShowBrowserNotification(n);
      setTimeout(() => dismiss(toastId), n.kind === "block_found" ? 20_000 : 8_000);
    },
    [dismiss]
  );

  return <ToastContext.Provider value={{ toasts, push, dismiss }}>{children}</ToastContext.Provider>;
}

export function useToasts(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToasts must be used inside ToastProvider");
  return ctx;
}
