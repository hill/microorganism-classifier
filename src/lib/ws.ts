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
    const ws = new WebSocket(wsUrl);
    ws.binaryType = "blob";

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (ev) => {
      if (typeof ev.data === "string") {
        const msg = JSON.parse(ev.data);
        setState({
          frameIndex: msg.frame_index,
          savedTracks: msg.saved_tracks,
          tracks: msg.tracks,
          frame: frameRef.current || undefined,
        });
      } else {
        frameRef.current = new Blob([ev.data as Blob], { type: "image/png" });
      }
    };

    return () => ws.close();
  }, [enabled]);

  return { state, connected };
}
