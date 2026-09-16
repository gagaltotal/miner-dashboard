import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { NotificationBell } from "./NotificationBell";

export function Layout() {
  const { state, logout } = useAuth();

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-base-border bg-base-bg/90 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <Link to="/" className="flex items-center gap-2">
            <LogoMark />
            <span className="font-medium text-ink">Dasbor Penambang</span>
          </Link>

          <nav className="flex items-center gap-1">
            <NavItem to="/">Dasbor</NavItem>
            <NavItem to="/settings">Pengaturan</NavItem>
            <NotificationBell />
            {state.status === "logged_in" && (
              <button
                onClick={() => logout()}
                className="ml-1 rounded px-2 py-1.5 text-sm text-ink-muted transition-colors hover:bg-base-raised hover:text-ink"
                title={`Keluar (${state.username})`}
              >
                Keluar
              </button>
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}

function NavItem({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        `rounded px-3 py-1.5 text-sm transition-colors ${
          isActive ? "bg-base-raised text-ink" : "text-ink-muted hover:bg-base-raised hover:text-ink"
        }`
      }
    >
      {children}
    </NavLink>
  );
}

function LogoMark() {
  return (
    <svg width="22" height="22" viewBox="0 0 64 64" fill="none">
      <rect width="64" height="64" rx="12" fill="#1E1B16" />
      <rect x="17" y="34" width="6" height="13" rx="1.5" fill="#3FCDB0" />
      <rect x="27" y="26" width="6" height="21" rx="1.5" fill="#E3953C" />
      <rect x="37" y="18" width="6" height="29" rx="1.5" fill="#E3953C" />
      <circle cx="47" cy="17" r="3" fill="#E5555A" />
    </svg>
  );
}
