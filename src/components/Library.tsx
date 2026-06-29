import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Flag, X } from "lucide-react";
import {
  fileUrl,
  useClips,
  useFlagClip,
  useFlagSnapshot,
  useFlagTrack,
  useSnapshots,
  useTrack,
  useTracks,
} from "../lib/api";
import type { Clip, Snapshot, Track } from "../lib/api";
import { useApp } from "../state";
import { Select } from "./Select";

const SORTS = [
  { value: "id_desc", label: "Newest" },
  { value: "area_desc", label: "Largest" },
  { value: "duration_desc", label: "Longest" },
] as const;

type Tab = "clips" | "tracks" | "snapshots";

export function Library() {
  const { selectedTrackId, selectTrack } = useApp();
  const [tab, setTab] = useState<Tab>("clips");
  const [flagged, setFlagged] = useState<boolean | undefined>();
  const [sort, setSort] = useState<(typeof SORTS)[number]["value"]>("id_desc");

  return (
    <div className="flex-1 flex min-h-0">
      <div className="flex-1 flex flex-col min-h-0">
        <div className="px-3 h-9 border-b border-rule flex items-center justify-between">
          <div className="flex items-center gap-0.5 bg-paper-2 rounded p-0.5 border border-rule">
            <TabButton active={tab === "clips"} onClick={() => setTab("clips")}>
              Clips
            </TabButton>
            <TabButton active={tab === "tracks"} onClick={() => setTab("tracks")}>
              Tracks
            </TabButton>
            <TabButton active={tab === "snapshots"} onClick={() => setTab("snapshots")}>
              Snapshots
            </TabButton>
          </div>
          <div className="flex gap-1">
            <Toggle
              active={flagged === true}
              onClick={() => setFlagged(flagged === true ? undefined : true)}
            >
              <Flag size={11} fill={flagged === true ? "currentColor" : "none"} strokeWidth={2} />
              Flagged
            </Toggle>
            {tab === "tracks" && (
              <Select value={sort} onChange={setSort} options={SORTS} />
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-3">
          {tab === "clips" && <ClipsList flagged={flagged} />}
          {tab === "tracks" && (
            <TracksGrid
              flagged={flagged}
              sort={sort}
              selectedId={selectedTrackId}
              onSelect={selectTrack}
            />
          )}
          {tab === "snapshots" && <SnapshotsGrid flagged={flagged} />}
        </div>
      </div>

      <AnimatePresence>
        {tab === "tracks" && selectedTrackId !== null && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 320, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ type: "spring", stiffness: 400, damping: 36 }}
            className="border-l border-rule bg-paper overflow-hidden"
          >
            <TrackDetail trackId={selectedTrackId} onClose={() => selectTrack(null)} />
          </motion.aside>
        )}
      </AnimatePresence>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={
        "px-2 h-6 rounded text-[11px] transition-colors " +
        (active ? "bg-paper-3 text-ink border border-rule" : "text-ink-2 hover:text-ink")
      }
    >
      {children}
    </button>
  );
}

function Toggle({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={
        "flex items-center gap-1.5 px-2 h-7 rounded text-[11px] border transition-colors " +
        (active
          ? "bg-accent text-paper border-accent"
          : "bg-paper-2 text-ink border-rule hover:bg-paper-3")
      }
    >
      {children}
    </button>
  );
}

function TracksGrid({
  flagged,
  sort,
  selectedId,
  onSelect,
}: {
  flagged?: boolean;
  sort: string;
  selectedId: number | null;
  onSelect: (id: number | null) => void;
}) {
  const tracks = useTracks({ flagged, sort });
  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
      {tracks.data?.map((t) => (
        <TrackCard
          key={t.id}
          track={t}
          active={selectedId === t.id}
          onSelect={() => onSelect(t.id)}
        />
      ))}
    </div>
  );
}

function TrackCard({
  track,
  active,
  onSelect,
}: {
  track: Track;
  active: boolean;
  onSelect: () => void;
}) {
  const detail = useTrack(track.id);
  const thumb = detail.data?.frames?.[0]?.path;
  const duration = ((track.end_video_ms - track.start_video_ms) / 1000).toFixed(1);

  return (
    <motion.button
      whileTap={{ scale: 0.985 }}
      onClick={onSelect}
      className={
        "text-left bg-paper-2 border rounded overflow-hidden transition-colors " +
        (active ? "border-accent" : "border-rule hover:border-rule-2")
      }
    >
      <div className="aspect-square bg-paper-3 relative">
        {thumb ? <img src={fileUrl(thumb)} className="w-full h-full object-cover" /> : null}
        {track.flagged ? (
          <div className="absolute top-1 right-1 w-5 h-5 rounded bg-accent text-paper flex items-center justify-center">
            <Flag size={10} fill="currentColor" strokeWidth={2} />
          </div>
        ) : null}
      </div>
      <div className="px-1.5 py-1">
        <div className="text-[12px] truncate text-ink">
          {track.label || <span className="text-ink-3">—</span>}
        </div>
        <div className="text-[10px] text-ink-2">
          {duration}s · {Math.round(track.mean_area_px || 0)} px²
        </div>
      </div>
    </motion.button>
  );
}

function SnapshotsGrid({ flagged }: { flagged?: boolean }) {
  const snaps = useSnapshots({ flagged });
  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
      {snaps.data?.map((s) => <SnapshotCard key={s.id} snapshot={s} />)}
    </div>
  );
}

function ClipsList({ flagged }: { flagged?: boolean }) {
  const clips = useClips({ flagged });
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
      {clips.data?.map((c) => <ClipCard key={c.id} clip={c} />)}
    </div>
  );
}

function ClipCard({ clip }: { clip: Clip }) {
  const flag = useFlagClip();
  const duration = clip.duration_ms != null ? (clip.duration_ms / 1000).toFixed(1) : "…";
  const ts = new Date(clip.started_at).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  return (
    <div className="bg-paper-2 border border-rule rounded overflow-hidden">
      <div className="aspect-video bg-black relative">
        <video src={fileUrl(clip.path)} controls preload="metadata" className="w-full h-full" />
        <motion.button
          whileTap={{ scale: 0.85 }}
          onClick={() => flag.mutate({ clipId: clip.id, flagged: !clip.flagged })}
          className={
            "absolute top-1 right-1 w-5 h-5 rounded flex items-center justify-center transition-colors " +
            (clip.flagged ? "bg-accent text-paper" : "bg-paper/80 text-ink-3 hover:text-ink")
          }
        >
          <Flag size={10} fill={clip.flagged ? "currentColor" : "none"} strokeWidth={2} />
        </motion.button>
      </div>
      <div className="px-2 py-1.5 flex items-baseline justify-between">
        <div className="min-w-0">
          <div className="text-[12px] truncate text-ink">
            {clip.label || <span className="text-ink-3">—</span>}
          </div>
          <div className="text-[10px] text-ink-2">
            {ts} · {duration}s
          </div>
        </div>
      </div>
    </div>
  );
}

function SnapshotCard({ snapshot }: { snapshot: Snapshot }) {
  const flag = useFlagSnapshot();
  return (
    <div className="bg-paper-2 border border-rule rounded overflow-hidden">
      <div className="aspect-square bg-paper-3 relative">
        <img src={fileUrl(snapshot.path)} className="w-full h-full object-cover" />
        <motion.button
          whileTap={{ scale: 0.85 }}
          onClick={() => flag.mutate({ snapId: snapshot.id, flagged: !snapshot.flagged })}
          className={
            "absolute top-1 right-1 w-5 h-5 rounded flex items-center justify-center transition-colors " +
            (snapshot.flagged
              ? "bg-accent text-paper"
              : "bg-paper/80 text-ink-3 hover:text-ink")
          }
        >
          <Flag size={10} fill={snapshot.flagged ? "currentColor" : "none"} strokeWidth={2} />
        </motion.button>
      </div>
      <div className="px-1.5 py-1">
        <div className="text-[12px] truncate text-ink">
          {snapshot.label || <span className="text-ink-3">—</span>}
        </div>
        <div className="text-[10px] text-ink-2 truncate">
          {new Date(snapshot.ts).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}

function TrackDetail({ trackId, onClose }: { trackId: number; onClose: () => void }) {
  const detail = useTrack(trackId);
  const flag = useFlagTrack();

  if (detail.isLoading) {
    return <div className="p-3 text-[12px] text-ink-2 w-80">Loading</div>;
  }
  if (!detail.data) {
    return <div className="p-3 text-[12px] text-ink-2 w-80">Not found</div>;
  }

  const t = detail.data;
  const duration = ((t.end_video_ms - t.start_video_ms) / 1000).toFixed(1);
  const recordingUrl = t.recording ? fileUrl(t.recording.path) : null;
  const startSeconds = t.start_video_ms / 1000;

  return (
    <div className="h-full flex flex-col w-80">
      <div className="flex items-center justify-between h-9 px-3 border-b border-rule">
        <div className="text-[12px] truncate">{t.label || "Untitled"}</div>
        <button onClick={onClose} className="text-ink-2 hover:text-ink p-1 rounded">
          <X size={14} strokeWidth={2} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        <div className="text-[11px] text-ink-2">
          Run {t.run_id} · {duration}s · {t.n_frames} frames
        </div>

        <motion.button
          whileTap={{ scale: 0.98 }}
          onClick={() => flag.mutate({ trackId: t.id, flagged: !t.flagged })}
          className={
            "w-full flex items-center justify-center gap-1.5 h-7 rounded text-[12px] transition-colors " +
            (t.flagged
              ? "bg-accent text-paper"
              : "bg-paper-2 border border-rule hover:bg-paper-3")
          }
        >
          <Flag size={11} fill={t.flagged ? "currentColor" : "none"} strokeWidth={2} />
          {t.flagged ? "Flagged" : "Flag"}
        </motion.button>

        {recordingUrl && (
          <Section title="Clip">
            <video
              src={recordingUrl}
              controls
              className="w-full rounded border border-rule bg-paper-3"
              onLoadedMetadata={(e) => {
                (e.currentTarget as HTMLVideoElement).currentTime = startSeconds;
              }}
            />
          </Section>
        )}

        <Section title="Frames">
          <div className="grid grid-cols-3 gap-1">
            {t.frames.map((f) => (
              <img
                key={f.id}
                src={fileUrl(f.path)}
                className="w-full aspect-square object-cover rounded border border-rule"
              />
            ))}
          </div>
        </Section>

        {t.mask_path && (
          <Section title="Mask">
            <img
              src={fileUrl(t.mask_path)}
              className="w-full max-w-32 rounded border border-rule"
            />
          </Section>
        )}

        <Section title="Morphometry">
          <dl className="grid grid-cols-2 gap-1 text-[11px]">
            <Metric label="Area" value={`${Math.round(t.mean_area_px || 0)} px²`} />
            <Metric
              label="Bbox"
              value={`${Math.round(t.bbox_w_px || 0)}×${Math.round(t.bbox_h_px || 0)}`}
            />
            <Metric label="Speed" value={`${Math.round(t.mean_speed_px_s || 0)} px/s`} />
            <Metric label="Frames" value={String(t.n_frames)} />
          </dl>
        </Section>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-[11px] text-ink-2 mb-1.5">{title}</h3>
      {children}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-paper-2 border border-rule rounded px-2 py-1">
      <div className="text-[10px] text-ink-3">{label}</div>
      <div className="text-ink mt-0.5">{value}</div>
    </div>
  );
}
