import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export const API_BASE = "http://127.0.0.1:8765";

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export interface Session { id: number; started_at: string; ended_at: string | null; notes: string | null; }
export interface Sample { id: number; session_id: number; site: string | null; container: string | null; preparation: string | null; collected_at: string | null; }
export interface Run { id: number; sample_id: number; objective: string | null; illumination: string | null; started_at: string; ended_at: string | null; }
export interface Track {
  id: number;
  run_id: number;
  label: string | null;
  first_frame_ts: string;
  last_frame_ts: string;
  start_video_ms: number;
  end_video_ms: number;
  n_frames: number;
  mask_path: string | null;
  mean_area_px: number | null;
  bbox_w_px: number | null;
  bbox_h_px: number | null;
  mean_speed_px_s: number | null;
  flagged: boolean;
  notes: string | null;
}
export interface Frame { id: number; track_id: number; ts: string; path: string; sharpness: number; }
export interface Recording { id: number; run_id: number; path: string; fps: number; width: number; height: number; duration_ms: number | null; }
export interface Clip {
  id: number;
  run_id: number;
  started_at: string;
  ended_at: string | null;
  path: string;
  seconds_before: number;
  duration_ms: number | null;
  label: string | null;
  flagged: boolean;
  notes: string | null;
}
export interface TrackDetail extends Track {
  frames: Frame[];
  recording: Recording | null;
  clip: Clip | null;
}

export const useSessions = () =>
  useQuery({ queryKey: ["sessions"], queryFn: () => jsonFetch<Session[]>("/sessions") });

export const useTracks = (
  filters: { run_id?: number; session_id?: number; flagged?: boolean; label?: string; sort?: string } = {},
  options: { enabled?: boolean } = {},
) => {
  const params = new URLSearchParams();
  if (filters.run_id !== undefined) params.set("run_id", String(filters.run_id));
  if (filters.session_id !== undefined) params.set("session_id", String(filters.session_id));
  if (filters.flagged !== undefined) params.set("flagged", String(filters.flagged));
  if (filters.label) params.set("label", filters.label);
  if (filters.sort) params.set("sort", filters.sort);
  return useQuery({
    queryKey: ["tracks", filters],
    queryFn: () => jsonFetch<Track[]>(`/tracks?${params.toString()}`),
    enabled: options.enabled ?? true,
  });
};

export const useTrack = (id: number | null) =>
  useQuery({
    queryKey: ["track", id],
    queryFn: () => jsonFetch<TrackDetail>(`/tracks/${id}`),
    enabled: id !== null,
  });

export const useCreateSession = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (notes?: string) =>
      jsonFetch<{ id: number }>("/sessions", { method: "POST", body: JSON.stringify({ notes }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }),
  });
};

export const useCreateSample = () =>
  useMutation({
    mutationFn: (payload: Partial<Sample> & { session_id: number }) =>
      jsonFetch<{ id: number }>("/samples", { method: "POST", body: JSON.stringify(payload) }),
  });

export const useLabelTrack = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ trackId, label }: { trackId: number; label: string }) =>
      jsonFetch(`/tracks/${trackId}/label`, { method: "POST", body: JSON.stringify({ label }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tracks"] }),
  });
};

export const useFlagTrack = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ trackId, flagged }: { trackId: number; flagged: boolean }) =>
      jsonFetch(`/tracks/${trackId}/flag`, { method: "POST", body: JSON.stringify({ flagged }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tracks"] }),
  });
};

export interface Snapshot {
  id: number;
  run_id: number;
  ts: string;
  path: string;
  label: string | null;
  flagged: boolean;
  notes: string | null;
}

export const useSnapshots = (filters: { run_id?: number; flagged?: boolean; label?: string } = {}) => {
  const params = new URLSearchParams();
  if (filters.run_id !== undefined) params.set("run_id", String(filters.run_id));
  if (filters.flagged !== undefined) params.set("flagged", String(filters.flagged));
  if (filters.label) params.set("label", filters.label);
  return useQuery({
    queryKey: ["snapshots", filters],
    queryFn: () => jsonFetch<Snapshot[]>(`/snapshots?${params.toString()}`),
  });
};

export const useFlagSnapshot = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ snapId, flagged }: { snapId: number; flagged: boolean }) =>
      jsonFetch(`/snapshots/${snapId}/flag`, { method: "POST", body: JSON.stringify({ flagged }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["snapshots"] }),
  });
};

export const useLabelSnapshot = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ snapId, label }: { snapId: number; label: string }) =>
      jsonFetch(`/snapshots/${snapId}/label`, { method: "POST", body: JSON.stringify({ label }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["snapshots"] }),
  });
};

export const useClips = (filters: { run_id?: number; flagged?: boolean; label?: string } = {}) => {
  const params = new URLSearchParams();
  if (filters.run_id !== undefined) params.set("run_id", String(filters.run_id));
  if (filters.flagged !== undefined) params.set("flagged", String(filters.flagged));
  if (filters.label) params.set("label", filters.label);
  return useQuery({
    queryKey: ["clips", filters],
    queryFn: () => jsonFetch<Clip[]>(`/clips?${params.toString()}`),
  });
};

export const useFlagClip = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ clipId, flagged }: { clipId: number; flagged: boolean }) =>
      jsonFetch(`/clips/${clipId}/flag`, { method: "POST", body: JSON.stringify({ flagged }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["clips"] }),
  });
};

export const useLabelClip = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ clipId, label }: { clipId: number; label: string }) =>
      jsonFetch(`/clips/${clipId}/label`, { method: "POST", body: JSON.stringify({ label }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["clips"] }),
  });
};

export interface Settings {
  id: number;
  data_dir: string;
  device_index: number;
  brightness: number;
  contrast: number;
  gamma: number;
  wb_r: number;
  wb_g: number;
  wb_b: number;
  invert: boolean;
  local_contrast: number;
  sharpness: number;
  grayscale: boolean;
}

export interface CameraInfo {
  index: number;
  name: string;
  width: number;
  height: number;
}

export const useCameras = () =>
  useQuery({ queryKey: ["cameras"], queryFn: () => jsonFetch<CameraInfo[]>("/cameras") });

export type SettingsPatch = Partial<Omit<Settings, "id">>;

export const useSettings = () =>
  useQuery({ queryKey: ["settings"], queryFn: () => jsonFetch<Settings>("/settings") });

export const useUpdateSettings = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: SettingsPatch) =>
      jsonFetch<Settings>("/settings", { method: "PATCH", body: JSON.stringify(patch) }),
    onSuccess: (next) => qc.setQueryData(["settings"], next),
  });
};

export const fileUrl = (path: string) => `${API_BASE}/file?path=${encodeURIComponent(path)}`;
