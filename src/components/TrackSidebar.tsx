import { motion } from "framer-motion";
import { Flag } from "lucide-react";
import { fileUrl, useFlagTrack, useTrack, useTracks } from "../lib/api";
import type { Track } from "../lib/api";
import type { PreviewTrack } from "../lib/ws";
import { useApp } from "../state";

interface Props {
  liveTracks: PreviewTrack[];
}

export function TrackSidebar({ liveTracks }: Props) {
  const { clipping, sessionId } = useApp();
  const saved = useTracks(
    { session_id: sessionId ?? undefined, sort: "id_desc" },
    { enabled: sessionId !== null },
  );
  const tracks = sessionId !== null ? saved.data : undefined;

  return (
    <aside className="w-56 shrink-0 border-l border-rule bg-paper flex flex-col min-h-0">
      <div className="px-3 h-8 border-b border-rule flex items-center justify-between">
        <h2 className="text-[12px] text-ink-2">Session</h2>
        {clipping && liveTracks.length > 0 && (
          <span className="text-[11px] text-ink-2">{liveTracks.length} active</span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-1">
        {tracks && tracks.length > 0 ? (
          <div className="space-y-0.5">
            {tracks.map((t) => <Row key={t.id} track={t} />)}
          </div>
        ) : (
          <p className="px-2 py-3 text-[11px] text-ink-3">
            {sessionId === null ? "No active session." : "No captures yet this session."}
          </p>
        )}
      </div>
    </aside>
  );
}

function Row({ track }: { track: Track }) {
  const detail = useTrack(track.id);
  const flag = useFlagTrack();
  const thumb = detail.data?.frames?.[0]?.path;
  const duration = ((track.end_video_ms - track.start_video_ms) / 1000).toFixed(1);

  return (
    <motion.div
      layout
      className="flex items-center gap-2 px-1.5 py-1 rounded hover:bg-paper-2 cursor-default"
    >
      <div className="w-8 h-8 rounded bg-paper-3 border border-rule overflow-hidden shrink-0">
        {thumb && <img src={fileUrl(thumb)} className="w-full h-full object-cover" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[12px] truncate text-ink">{track.label || "—"}</div>
        <div className="text-[10px] text-ink-2">
          {duration}s · {Math.round(track.mean_area_px || 0)} px²
        </div>
      </div>
      <motion.button
        whileTap={{ scale: 0.85 }}
        onClick={() => flag.mutate({ trackId: track.id, flagged: !track.flagged })}
        className={
          "shrink-0 w-5 h-5 rounded flex items-center justify-center transition-colors " +
          (track.flagged ? "text-accent" : "text-ink-3 hover:text-ink-2")
        }
        aria-label="flag"
      >
        <Flag size={11} fill={track.flagged ? "currentColor" : "none"} strokeWidth={2} />
      </motion.button>
    </motion.div>
  );
}
