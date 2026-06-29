import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { API_BASE } from "./lib/api";

type Mode = "camera" | "library";

interface AppState {
  mode: Mode;
  setMode: (m: Mode) => void;

  sessionId: number | null;
  sampleId: number | null;
  clipId: number | null;
  clipping: boolean;

  setupOpen: boolean;
  openSetup: () => void;
  closeSetup: () => void;

  settingsOpen: boolean;
  openSettings: () => void;
  closeSettings: () => void;

  processingOpen: boolean;
  openProcessing: () => void;
  closeProcessing: () => void;
  toggleProcessing: () => void;

  selectedTrackId: number | null;
  selectTrack: (id: number | null) => void;

  startNewSession: () => Promise<void>;

  startClip: (secondsBefore?: number) => Promise<void>;
  stopClip: () => Promise<void>;
  takeSnapshot: () => Promise<void>;
  saveDetection: (trackId: number, label?: string) => Promise<void>;
}

const Ctx = createContext<AppState | null>(null);

async function jsonPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

const LS = {
  session: "mc.session_id",
  sample: "mc.sample_id",
};

const DEFAULT_SECONDS_BEFORE = 30;

export function AppProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<Mode>("camera");
  const [sessionId, setSessionId] = useState<number | null>(() => {
    const v = localStorage.getItem(LS.session);
    return v ? Number(v) : null;
  });
  const [sampleId, setSampleId] = useState<number | null>(() => {
    const v = localStorage.getItem(LS.sample);
    return v ? Number(v) : null;
  });
  const [clipId, setClipId] = useState<number | null>(null);
  const [clipping, setClipping] = useState(false);
  const [setupOpen, setSetupOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [processingOpen, setProcessingOpen] = useState(false);
  const [selectedTrackId, setSelectedTrackId] = useState<number | null>(null);

  useEffect(() => {
    if (sessionId) localStorage.setItem(LS.session, String(sessionId));
    else localStorage.removeItem(LS.session);
  }, [sessionId]);
  useEffect(() => {
    if (sampleId) localStorage.setItem(LS.sample, String(sampleId));
    else localStorage.removeItem(LS.sample);
  }, [sampleId]);

  const ensureSample = async (): Promise<number> => {
    let sid = sessionId;
    if (!sid) {
      const s = await jsonPost<{ id: number }>("/sessions", {});
      sid = s.id;
      setSessionId(sid);
    }
    let smid = sampleId;
    if (!smid) {
      const sample = await jsonPost<{ id: number }>("/samples", {
        session_id: sid,
        site: "unspecified",
        container: "wet mount",
        preparation: "no stain",
      });
      smid = sample.id;
      setSampleId(smid);
    }
    return smid;
  };

  const start = useMutation({
    mutationFn: async (secondsBefore: number = DEFAULT_SECONDS_BEFORE) => {
      const smid = await ensureSample();
      const clip = await jsonPost<{ id: number }>("/clips/start", {
        sample_id: smid,
        seconds_before: secondsBefore,
      });
      return clip.id;
    },
    onSuccess: (id) => {
      setClipId(id);
      setClipping(true);
    },
  });

  const stop = useMutation({
    mutationFn: async () => {
      await jsonPost("/clips/stop", {});
    },
    onSuccess: () => {
      setClipping(false);
      setClipId(null);
      qc.invalidateQueries({ queryKey: ["clips"] });
      qc.invalidateQueries({ queryKey: ["tracks"] });
    },
  });

  const snap = useMutation({
    mutationFn: async () => {
      const smid = await ensureSample();
      await jsonPost("/snapshots", { sample_id: smid });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["snapshots"] });
    },
  });

  const saveDetection = useMutation({
    mutationFn: async ({ trackId, label }: { trackId: number; label?: string }) => {
      const smid = await ensureSample();
      await jsonPost(`/detections/${trackId}/save`, {
        sample_id: smid,
        label: label || null,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tracks"] });
    },
  });

  const startNewSession = async () => {
    const s = await jsonPost<{ id: number }>("/sessions", {});
    setSessionId(s.id);
    setSampleId(null);
    setClipId(null);
    setClipping(false);
    qc.invalidateQueries({ queryKey: ["sessions"] });
  };

  const value: AppState = {
    mode,
    setMode,
    sessionId,
    sampleId,
    clipId,
    clipping,
    setupOpen,
    openSetup: () => setSetupOpen(true),
    closeSetup: () => setSetupOpen(false),
    settingsOpen,
    openSettings: () => {
      setProcessingOpen(false);
      setSettingsOpen(true);
    },
    closeSettings: () => setSettingsOpen(false),
    processingOpen,
    openProcessing: () => {
      setSettingsOpen(false);
      setProcessingOpen(true);
    },
    closeProcessing: () => setProcessingOpen(false),
    toggleProcessing: () => {
      setSettingsOpen(false);
      setProcessingOpen((open) => !open);
    },
    selectedTrackId,
    selectTrack: setSelectedTrackId,
    startNewSession,
    startClip: async (secondsBefore?: number) => {
      await start.mutateAsync(secondsBefore ?? DEFAULT_SECONDS_BEFORE);
    },
    stopClip: async () => {
      await stop.mutateAsync();
    },
    takeSnapshot: async () => {
      await snap.mutateAsync();
    },
    saveDetection: async (trackId: number, label?: string) => {
      await saveDetection.mutateAsync({ trackId, label });
    },
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp must be inside AppProvider");
  return v;
}
