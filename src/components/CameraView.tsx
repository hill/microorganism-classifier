import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { usePreviewSocket } from "../lib/ws";
import type { PreviewState, PreviewTrack } from "../lib/ws";
import { useApp } from "../state";
import { TrackSidebar } from "./TrackSidebar";

interface Dims {
  naturalW: number;
  naturalH: number;
  renderedW: number;
  renderedH: number;
  offsetX: number;
  offsetY: number;
}

function Stage({
  state,
  onSave,
}: {
  state: PreviewState;
  onSave: (id: number, label?: string) => Promise<void>;
}) {
  const imgRef = useRef<HTMLImageElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [dims, setDims] = useState<Dims | null>(null);
  const [selected, setSelected] = useState<PreviewTrack | null>(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (!state.frame) return;
    const url = URL.createObjectURL(state.frame);
    if (imgRef.current) imgRef.current.src = url;
    // WebKit can still be decoding a large lossless frame when the next one arrives.
    // Keep the old URL alive briefly so cleanup cannot cancel an in-flight decode.
    return () => {
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    };
  }, [state.frame]);

  const recalc = () => {
    const img = imgRef.current;
    const c = containerRef.current;
    if (!img || !c || img.naturalWidth === 0) return;
    const cw = c.clientWidth;
    const ch = c.clientHeight;
    const ratio = Math.min(cw / img.naturalWidth, ch / img.naturalHeight);
    const rw = img.naturalWidth * ratio;
    const rh = img.naturalHeight * ratio;
    setDims({
      naturalW: img.naturalWidth,
      naturalH: img.naturalHeight,
      renderedW: rw,
      renderedH: rh,
      offsetX: (cw - rw) / 2,
      offsetY: (ch - rh) / 2,
    });
  };

  useEffect(() => {
    const ro = new ResizeObserver(recalc);
    if (containerRef.current) ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const closeSaveDialog = () => {
    if (saving) return;
    setSelected(null);
    setDraft("");
    setSaveError(null);
  };

  const submit = async () => {
    if (!selected || saving) return;
    setSaving(true);
    setSaveError(null);
    try {
      await onSave(selected.id, draft.trim() || undefined);
      setSelected(null);
      setDraft("");
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "Could not save cutout");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex-1 relative bg-paper-3 m-2 rounded-md border border-rule overflow-hidden">
      <div ref={containerRef} className="absolute inset-0">
        <img
          ref={imgRef}
          onLoad={recalc}
          alt=""
          className={"absolute transition-opacity " + (state.frame ? "opacity-100" : "opacity-0")}
          style={
            dims
              ? {
                  left: dims.offsetX,
                  top: dims.offsetY,
                  width: dims.renderedW,
                  height: dims.renderedH,
                }
              : { left: 0, top: 0 }
          }
        />
        {dims &&
          state.tracks.map((t) => {
            const sx = dims.renderedW / dims.naturalW;
            const sy = dims.renderedH / dims.naturalH;
            return (
              <button
                key={t.id}
                onClick={(e) => {
                  e.stopPropagation();
                  setSelected(t);
                  setDraft("");
                  setSaveError(null);
                }}
                className="absolute rounded-[3px] transition-colors hover:bg-accent/10"
                style={{
                  left: dims.offsetX + t.x * sx,
                  top: dims.offsetY + t.y * sy,
                  width: t.w * sx,
                  height: t.h * sy,
                  border: "1.5px solid rgba(60,56,54,0.65)",
                }}
              >
                <span
                  className="absolute -top-4.5 left-0 text-[10px] whitespace-nowrap px-1.5 h-4 inline-flex items-center rounded-sm"
                  style={{
                    background: "var(--color-paper)",
                    color: "var(--color-ink-2)",
                    border: "1px solid var(--color-rule)",
                  }}
                >
                  #{t.id}
                </span>
              </button>
            );
          })}
      </div>

      <AnimatePresence>
        {selected && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.1 }}
            className="absolute inset-0 flex items-center justify-center bg-ink/10"
            onClick={closeSaveDialog}
          >
            <motion.div
              initial={{ scale: 0.97, y: 4 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.98, y: 2 }}
              transition={{ type: "spring", stiffness: 500, damping: 36 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-paper border border-rule rounded-md p-3 w-72 shadow-xl"
            >
              <div className="text-[11px] text-ink-2 mb-1.5">Detection #{selected.id}</div>
              <input
                autoFocus
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void submit();
                  if (e.key === "Escape") closeSaveDialog();
                }}
                placeholder="Optional label, for example Paramecium"
                className="w-full bg-paper-2 border border-rule rounded px-2.5 py-1.5 text-[13px]"
              />
              {saveError && <p className="mt-1.5 text-[11px] text-record">{saveError}</p>}
              <div className="flex justify-end gap-1 mt-2">
                <button
                  onClick={closeSaveDialog}
                  disabled={saving}
                  className="text-[12px] text-ink-2 hover:text-ink px-2.5 py-1 rounded"
                >
                  Cancel
                </button>
                <motion.button
                  whileTap={{ scale: 0.96 }}
                  onClick={() => void submit()}
                  disabled={saving}
                  className="bg-accent text-paper px-2.5 py-1 rounded text-[12px] font-medium disabled:opacity-60"
                >
                  {saving ? "Saving" : "Save cutout"}
                </motion.button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function CameraView() {
  const { state } = usePreviewSocket(true);
  const { saveDetection } = useApp();
  return (
    <div className="flex-1 flex min-h-0">
      <Stage state={state} onSave={saveDetection} />
      <TrackSidebar liveTracks={state.tracks} />
    </div>
  );
}
