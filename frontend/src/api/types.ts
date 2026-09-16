export type DeviceKind = "bitaxe" | "nerdqaxe" | "avalon_nano" | "braiins" | "luxos";

export const DEVICE_KIND_LABELS: Record<DeviceKind, string> = {
  bitaxe: "Bitaxe",
  nerdqaxe: "NerdQaxe",
  avalon_nano: "Avalon Nano",
  braiins: "Braiins OS+",
  luxos: "LuxOS",
};

export const DEVICE_DEFAULT_PORT: Record<DeviceKind, number> = {
  bitaxe: 80,
  nerdqaxe: 80,
  avalon_nano: 4028,
  braiins: 80,
  luxos: 4028,
};

export interface DeviceCapabilities {
  fan_control: boolean;
  autotune: boolean;
  restart: boolean;
  pause_resume: boolean;
  identify: boolean;
}

export interface DeviceMetricsSnapshot {
  hashrate_ghs?: number | null;
  temp_c?: number | null;
  temp_secondary_c?: number | null;
  fan_percent?: number | null;
  fan_rpm?: number | null;
  power_w?: number | null;
  efficiency_j_th?: number | null;
  shares_accepted?: number | null;
  shares_rejected?: number | null;
  best_diff?: number | null;
  uptime_s?: number | null;
  pool_url?: string | null;
  firmware_version?: string | null;
  model?: string | null;
  autofan_enabled?: boolean | null;
  target_temp_c?: number | null;
  mining_paused?: boolean | null;
  raw?: Record<string, unknown>;
}

export interface Device {
  id: string;
  kind: DeviceKind;
  name: string;
  host: string;
  port: number;
  read_only: boolean;
  online: boolean;
  last_seen: number | null;
  last_error: string | null;
  capabilities: DeviceCapabilities;
  metrics: DeviceMetricsSnapshot;
  autotune_enabled: boolean;
  target_temp_c: number | null;
  manual_fan_percent: number | null;
  best_diff: number;
  blocks_found: number;
}

export interface HistoryPoint {
  ts: number;
  hashrate_ghs: number | null;
  temp_c: number | null;
  fan_percent: number | null;
  fan_rpm: number | null;
  power_w: number | null;
  shares_accepted: number | null;
  shares_rejected: number | null;
  best_diff: number | null;
}

export type HistoryRange = "1h" | "24h" | "7d" | "30d";

export interface DiscoveredDevice {
  kind: DeviceKind;
  host: string;
  port: number;
  suggested_name: string;
  fingerprint: Record<string, unknown>;
}

export interface NotificationItem {
  id: number;
  device_id: string | null;
  kind: string;
  message: string;
  ts: number;
  read: boolean;
}

export interface GlobalSettings {
  poll_interval_seconds: number;
  history_retention_days: number;
  allow_public_targets: boolean;
}
