import { useState } from "react";
import { motion } from "framer-motion";
import { Aperture, Camera, Circle, Settings2, Square } from "lucide-react";
import { useApp } from "../state";

export function BottomBar() {
  const {
    clipping,
    clipId,
    startClip,
    stopClip,
    takeSnapshot,
    openSetup,
    toggleProcessing,
  } = useApp();
  const [snapping, setSnapping] = useState(false);

  const handleSnap = async () => {
    setSnapping(true);
    try {
      await takeSnapshot();
    } finally {
      setSnapping(false);
    }
  };

  return (
    <footer className="h-11 border-t border-rule bg-paper flex items-center px-2 gap-1">
      <ToolButton onClick={openSetup} icon={<Settings2 size={12} strokeWidth={2} />}>
        Sample
      </ToolButton>
      <div className="flex-1 flex justify-center gap-1">
        <ClipButton clipping={clipping} onStart={() => startClip()} onStop={stopClip} />
        <SnapButton busy={snapping} onClick={handleSnap} />
      </div>

      <div className="flex items-center gap-2 justify-end">
        <div className="text-[11px] text-ink-2 flex items-center gap-2">
          {clipping && clipId ? <span>Clip {clipId}</span> : null}
          {clipping && <span className="text-record">Recording</span>}
        </div>
        <ToolButton
          onClick={toggleProcessing}
          icon={<Aperture size={13} strokeWidth={2} />}
        >
          Filters
        </ToolButton>
      </div>
    </footer>
  );
}

function ToolButton({
  onClick,
  icon,
  children,
}: {
  onClick: () => void;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <motion.button
      whileTap={{ scale: 0.95 }}
      onClick={onClick}
      className="flex items-center gap-1.5 px-2 h-7 rounded border border-rule bg-paper-2 text-ink hover:bg-paper-3 text-[12px]"
    >
      <span className="text-ink-2">{icon}</span>
      {children}
    </motion.button>
  );
}

function ClipButton({
  clipping,
  onStart,
  onStop,
}: {
  clipping: boolean;
  onStart: () => void;
  onStop: () => void;
}) {
  return (
    <motion.button
      whileTap={{ scale: 0.96 }}
      onClick={clipping ? onStop : onStart}
      title={clipping ? "Stop the active clip" : "Save the last 30s and keep recording until stopped"}
      className={
        "flex items-center gap-1.5 h-7 px-3 rounded text-[12px] font-medium transition-colors " +
        (clipping
          ? "bg-paper-3 text-ink border border-rule hover:bg-rule"
          : "bg-record text-paper hover:bg-record-2")
      }
    >
      {clipping ? (
        <Square size={10} fill="currentColor" strokeWidth={0} />
      ) : (
        <Circle size={10} fill="currentColor" strokeWidth={0} />
      )}
      {clipping ? "Stop" : "Clip"}
    </motion.button>
  );
}

function SnapButton({ busy, onClick }: { busy: boolean; onClick: () => void }) {
  return (
    <motion.button
      whileTap={{ scale: 0.96 }}
      onClick={onClick}
      disabled={busy}
      title="Save the current frame as a snapshot"
      className="flex items-center gap-1.5 h-7 px-3 rounded text-[12px] font-medium transition-colors border bg-paper-2 text-ink border-rule hover:bg-paper-3"
    >
      <Camera size={11} strokeWidth={2} />
      {busy ? "Saving" : "Snap"}
    </motion.button>
  );
}
