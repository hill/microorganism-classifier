import { useEffect, useRef, useState } from "react";
import { API_BASE } from "./api";

export interface PreviewTrack {
  id: number;
  x: number;
  y: number;
  w: number;
  h: number;
  label: string | null;
  n_frames: number;
}

export interface PreviewState {
  frameIndex: number;
  savedTracks: number;
  tracks: PreviewTrack[];
  frame?: Blob;
}

export function usePreviewSocket(enabled: boolean) {
  const [state, setState] = useState<PreviewState>({ frameIndex: 0, savedTracks: 0, tracks: [] });
  const [connected, setConnected] = useState(false);
  const frameRef = useRef<Blob | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const wsUrl = API_BASE.replace("http", "ws") + "/ws/preview";
    let ws: WebSocket | null = null;
    let retryTimer: number | null = null;
    let retryDelayMs = 250;
    let stopped = false;

    const connect = () => {
      if (stopped) return;
      const socket = new WebSocket(wsUrl);
      ws = socket;
      socket.binaryType = "blob";

      socket.onopen = () => {
        if (socket !== ws) return;
        retryDelayMs = 250;
        setConnected(true);
      };
      socket.onclose = () => {
        if (socket !== ws || stopped) return;
        setConnected(false);
        retryTimer = window.setTimeout(connect, retryDelayMs);
        retryDelayMs = Math.min(retryDelayMs * 2, 2000);
      };
      socket.onerror = () => {
        if (socket === ws) socket.close();
      };
      socket.onmessage = (event) => {
        if (socket !== ws) return;
        if (typeof event.data === "string") {
          const message = JSON.parse(event.data);
          setState({
            frameIndex: message.frame_index,
            savedTracks: message.saved_tracks,
            tracks: message.tracks,
            frame: frameRef.current || undefined,
          });
        } else {
          frameRef.current = new Blob([event.data as Blob], { type: "image/jpeg" });
        }
      };
    };

    connect();
    return () => {
      stopped = true;
      if (retryTimer !== null) window.clearTimeout(retryTimer);
      ws?.close();
    };
  }, [enabled]);

  return { state, connected };
}
