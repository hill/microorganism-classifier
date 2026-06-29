import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, FlaskConical, Plus } from "lucide-react";
import { useApp } from "../state";

export function SessionMenu() {
  const { sessionId, startNewSession, clipping } = useApp();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const handleNew = async () => {
    setBusy(true);
    try {
      await startNewSession();
    } finally {
      setBusy(false);
      setOpen(false);
    }
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        title="Session"
        className="flex items-center gap-1.5 h-6 px-2 rounded text-[11px] text-ink-2 hover:text-ink hover:bg-paper-2"
      >
        <FlaskConical size={12} strokeWidth={2} />
        <span className="tabular-nums">{sessionId ? `Session ${sessionId}` : "No session"}</span>
        <ChevronDown size={11} className="text-ink-3" />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.1 }}
            className="absolute left-0 top-full mt-1 min-w-[180px] bg-paper border border-rule rounded-md shadow-lg z-50 py-1"
          >
            <button
              onClick={handleNew}
              disabled={clipping || busy}
              className="w-full flex items-center gap-1.5 px-2.5 py-1.5 text-[12px] text-ink hover:bg-paper-2 text-left disabled:opacity-40 disabled:hover:bg-transparent"
            >
              <Plus size={12} strokeWidth={2} className="text-ink-2" />
              {busy ? "Starting" : "New session"}
            </button>
            <p className="px-2.5 pt-1 text-[10px] text-ink-3 leading-snug">
              {clipping
                ? "Stop recording before starting a new session."
                : "Ends the current session. Captures will start a fresh one."}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
