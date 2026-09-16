import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Device, HistoryRange } from "../api/types";

export function useDevices() {
  return useQuery({
    queryKey: ["devices"],
    queryFn: api.devices.list,
    refetchInterval: 30_000, // WebSocket carries most live updates; this is just a safety-net refresh
  });
}

export function useDevice(id: string | undefined) {
  return useQuery({
    queryKey: ["device", id],
    queryFn: () => api.devices.get(id as string),
    enabled: !!id,
    refetchInterval: 30_000,
  });
}

export function useDeviceHistory(id: string | undefined, range: HistoryRange) {
  return useQuery({
    queryKey: ["device-history", id, range],
    queryFn: () => api.devices.history(id as string, range),
    enabled: !!id,
    refetchInterval: 30_000,
  });
}

export function useDiscoverDevices() {
  return useMutation({ mutationFn: api.devices.discover });
}

export function useCreateDevice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.devices.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["devices"] }),
  });
}

export function useRenameDevice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => api.devices.rename(id, name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["devices"] }),
  });
}

export function useDeleteDevice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.devices.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["devices"] }),
  });
}

export function useSetFan(deviceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ mode, manual_percent }: { mode: "auto" | "manual"; manual_percent?: number }) =>
      api.devices.setFan(deviceId, mode, manual_percent),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["device", deviceId] });
      qc.invalidateQueries({ queryKey: ["devices"] });
    },
  });
}

export function useSetAutotune(deviceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ enabled, target_temp_c }: { enabled: boolean; target_temp_c?: number }) =>
      api.devices.setAutotune(deviceId, enabled, target_temp_c),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["device", deviceId] });
      qc.invalidateQueries({ queryKey: ["devices"] });
    },
  });
}

export function useDeviceAction(deviceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (action: "restart" | "pause" | "resume" | "identify") => api.devices.action(deviceId, action),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["device", deviceId] });
      qc.invalidateQueries({ queryKey: ["devices"] });
    },
  });
}

export function useNotifications() {
  return useQuery({ queryKey: ["notifications"], queryFn: api.notifications.list, refetchInterval: 60_000 });
}

export function useMarkNotificationsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.notifications.markRead,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
}

export function useGlobalSettings() {
  return useQuery({ queryKey: ["settings"], queryFn: api.settings.get });
}

export function useUpdateGlobalSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.settings.update,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });
}

/** Merge a partial device-update payload from the WebSocket into cached device data. */
export function mergeDeviceUpdate(devices: Device[] | undefined, update: any): Device[] | undefined {
  if (!devices) return devices;
  return devices.map((d) => (d.id === update.id ? applyUpdate(d, update) : d));
}

export function applyUpdate(device: Device, update: any): Device {
  const { id, online, last_error, ...metricFields } = update;
  const hasMetrics = Object.keys(metricFields).length > 0;
  return {
    ...device,
    online: online ?? device.online,
    last_error: last_error ?? null,
    metrics: hasMetrics ? { ...device.metrics, ...metricFields } : device.metrics,
    best_diff: typeof metricFields.best_diff === "number" ? Math.max(device.best_diff, metricFields.best_diff) : device.best_diff,
  };
}
