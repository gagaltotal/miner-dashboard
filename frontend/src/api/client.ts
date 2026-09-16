import type {
  Device,
  DiscoveredDevice,
  GlobalSettings,
  HistoryPoint,
  HistoryRange,
  NotificationItem,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

/**
 * Every mutating request must echo the CSRF cookie's value back in a
 * header (see backend/app/security/middleware.py). We read it fresh on
 * every call rather than caching it, since it rotates on every login.
 */
function csrfHeaders(): Record<string, string> {
  const token = readCookie("miner_dash_csrf");
  return token ? { "X-CSRF-Token": token } : {};
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const isMutating = method !== "GET";
  const res = await fetch(path, {
    method,
    credentials: "include",
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(isMutating ? csrfHeaders() : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) {
    return undefined as T;
  }

  const text = await res.text();
  const data = text ? safeJsonParse(text) : undefined;

  if (!res.ok) {
    const message = extractErrorMessage(data, res.status);
    throw new ApiError(res.status, message);
  }
  return data as T;
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

function extractErrorMessage(data: unknown, status: number): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      // Pydantic validation error array
      return detail
        .map((d) => (typeof d === "object" && d && "msg" in d ? String((d as any).msg) : JSON.stringify(d)))
        .join("; ");
    }
  }
  if (status === 429) return "Terlalu banyak permintaan. Coba lagi sebentar lagi.";
  return `Permintaan gagal (HTTP ${status})`;
}

export const api = {
  auth: {
    status: () => request<{ setup_complete: boolean }>("GET", "/api/auth/status"),
    setup: (username: string, password: string) =>
      request<{ username: string }>("POST", "/api/auth/setup", { username, password }),
    login: (username: string, password: string) =>
      request<{ username: string }>("POST", "/api/auth/login", { username, password }),
    logout: () => request<{ ok: boolean }>("POST", "/api/auth/logout"),
    me: () => request<{ username: string }>("GET", "/api/auth/me"),
    changePassword: (current_password: string, new_password: string) =>
      request<{ ok: boolean }>("PUT", "/api/auth/password", { current_password, new_password }),
  },
  devices: {
    list: () => request<Device[]>("GET", "/api/devices"),
    get: (id: string) => request<Device>("GET", `/api/devices/${id}`),
    create: (body: {
      kind: string;
      name: string;
      host: string;
      port?: number;
      username?: string;
      password?: string;
    }) => request<Device>("POST", "/api/devices", body),
    rename: (id: string, name: string) => request<Device>("PATCH", `/api/devices/${id}`, { name }),
    remove: (id: string) => request<void>("DELETE", `/api/devices/${id}`),
    history: (id: string, range: HistoryRange) =>
      request<{ range: HistoryRange; points: HistoryPoint[] }>("GET", `/api/devices/${id}/history?range=${range}`),
    discover: () => request<DiscoveredDevice[]>("GET", "/api/devices/discovery/scan"),
    setFan: (id: string, mode: "auto" | "manual", manual_percent?: number) =>
      request<{ ok: boolean }>("POST", `/api/devices/${id}/fan`, { mode, manual_percent }),
    setAutotune: (id: string, enabled: boolean, target_temp_c?: number) =>
      request<{ ok: boolean }>("POST", `/api/devices/${id}/autotune`, { enabled, target_temp_c }),
    action: (id: string, action: "restart" | "pause" | "resume" | "identify") =>
      request<{ ok: boolean }>("POST", `/api/devices/${id}/action`, { action }),
  },
  notifications: {
    list: () => request<NotificationItem[]>("GET", "/api/notifications"),
    markRead: (ids: number[]) => request<{ ok: boolean }>("POST", "/api/notifications/mark-read", { ids }),
  },
  settings: {
    get: () => request<GlobalSettings>("GET", "/api/settings"),
    update: (body: Partial<Pick<GlobalSettings, "poll_interval_seconds" | "history_retention_days">>) =>
      request<GlobalSettings>("PATCH", "/api/settings", body),
  },
};
