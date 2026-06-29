import { motion } from "framer-motion";
import { Camera, LayoutGrid, SlidersHorizontal } from "lucide-react";
import { useApp } from "../state";
import { CameraSelect } from "./CameraSelect";
import { SessionMenu } from "./SessionMenu";

function ModePill({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={
        "relative flex items-center gap-1 px-2 h-6 rounded text-[11px] transition-colors " +
        (active ? "text-ink" : "text-ink-2 hover:text-ink")
      }
    >
      {active && (
        <motion.span
          layoutId="mode-pill"
          className="absolute inset-0 bg-paper-3 border border-rule rounded"
          transition={{ type: "spring", stiffness: 500, damping: 40 }}
        />
      )}
      <span className="relative">{icon}</span>
      <span className="relative">{label}</span>
    </button>
  );
}

export function TitleBar() {
  const { mode, setMode, openSettings } = useApp();
  return (
    <header
      data-tauri-drag-region
      className="flex items-center h-10 border-b border-rule bg-paper shrink-0"
    >
      {/* Reserve space for the macOS traffic lights */}
      <div data-tauri-drag-region className="w-22 h-full shrink-0" />
      <h1
        data-tauri-drag-region
        className="text-[12px] font-medium text-ink"
      >
        Microorganism Classifier
      </h1>
      <div className="ml-3">
        <SessionMenu />
      </div>
      <div data-tauri-drag-region className="flex-1 h-full" />
      {mode === "camera" && (
        <div className="mr-1.5">
          <CameraSelect />
        </div>
      )}
      <button
        onClick={openSettings}
        title="Settings"
        className="w-7 h-7 flex items-center justify-center rounded text-ink-2 hover:text-ink hover:bg-paper-2 mr-1"
      >
        <SlidersHorizontal size={13} strokeWidth={2} />
      </button>
      <div
        data-tauri-drag-region
        className="flex items-center gap-0.5 bg-paper-2 rounded p-0.5 border border-rule mr-2"
      >
        <ModePill
          active={mode === "camera"}
          onClick={() => setMode("camera")}
          icon={<Camera size={12} strokeWidth={2} />}
          label="Camera"
        />
        <ModePill
          active={mode === "library"}
          onClick={() => setMode("library")}
          icon={<LayoutGrid size={12} strokeWidth={2} />}
          label="Library"
        />
      </div>
    </header>
  );
}
