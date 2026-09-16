import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Device, NotificationItem } from "../api/types";
import { applyUpdate } from "./useDevices";

type WsMessage =
  | { type: "device_update"; device: any }
  | { type: "notification"; notification: NotificationItem };

/**
 * Opens the dashboard's live-update WebSocket and folds every message
 * straight into the React Query cache, so device cards and the detail page
 * update in place without polling. Falls back gracefully (the 30s
 * `refetchInterval` on each query in useDevices.ts) if the socket drops and
 * takes a moment to reconnect.
 */
export function useLiveUpdates(onNotification: (n: NotificationItem) => void) {
  const qc = useQueryClient();
  const onNotificationRef = useRef(onNotification);
  onNotificationRef.current = onNotification;

  useEffect(() => {
    let socket: WebSocket | null = null;
    let closedByUs = false;
    let retryDelay = 1000;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(`${protocol}//${window.location.host}/ws`);

      socket.onopen = () => {
        retryDelay = 1000;
      };

      socket.onmessage = (event) => {
        let msg: WsMessage;
        try {
          msg = JSON.parse(event.data);
        } catch {
          return;
        }

        if (msg.type === "device_update") {
          qc.setQueryData<Device[]>(["devices"], (old) =>
            old ? old.map((d) => (d.id === msg.device.id ? applyUpdate(d, msg.device) : d)) : old
          );
          qc.setQueryData<Device>(["device", msg.device.id], (old) => (old ? applyUpdate(old, msg.device) : old));
        } else if (msg.type === "notification") {
          qc.setQueryData<NotificationItem[]>(["notifications"], (old) =>
            old ? [msg.notification, ...old] : [msg.notification]
          );
          onNotificationRef.current(msg.notification);
        }
      };

      socket.onclose = () => {
        if (closedByUs) return;
        retryTimer = setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 1.7, 20_000);
      };

      socket.onerror = () => {
        socket?.close();
      };
    };

    connect();

    return () => {
      closedByUs = true;
      if (retryTimer) clearTimeout(retryTimer);
      socket?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qc]);
}
