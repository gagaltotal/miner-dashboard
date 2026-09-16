import { useEffect, useRef, useState } from "react";
import { useMarkNotificationsRead, useNotifications } from "../hooks/useDevices";
import { formatRelativeTime } from "../lib/format";

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const { data: notifications = [] } = useNotifications();
  const markRead = useMarkNotificationsRead();
  const ref = useRef<HTMLDivElement>(null);
  const unreadCount = notifications.filter((n) => !n.read).length;

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const handleOpen = () => {
    setOpen((v) => !v);
    const unreadIds = notifications.filter((n) => !n.read).map((n) => n.id);
    if (unreadIds.length > 0) markRead.mutate(unreadIds);
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={handleOpen}
        className="relative rounded p-2 text-ink-muted transition-colors hover:bg-base-raised hover:text-ink"
        aria-label="Notifikasi"
      >
        <BellIcon />
        {unreadCount > 0 && (
          <span className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-amber text-[10px] font-semibold text-base-bg">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-40 mt-2 w-80 max-w-[90vw] rounded-lg border border-base-border bg-base-surface shadow-xl">
          <div className="border-b border-base-border px-4 py-2 text-sm font-medium text-ink">Notifikasi</div>
          <div className="max-h-96 overflow-y-auto">
            {notifications.length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-ink-faint">Belum ada notifikasi.</p>
            ) : (
              notifications.map((n) => (
                <div key={n.id} className="border-b border-base-border px-4 py-3 last:border-0">
                  <p className="text-sm text-ink">{n.message}</p>
                  <p className="mt-1 text-xs text-ink-faint">{formatRelativeTime(n.ts)}</p>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function BellIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
