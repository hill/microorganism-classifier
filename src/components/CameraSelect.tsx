import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronDown, RefreshCw, Webcam } from "lucide-react";
import { useCameras, useSettings, useUpdateSettings } from "../lib/api";

export function CameraSelect() {
  const { data: settings } = useSettings();
  const cameras = useCameras();
  const update = useUpdateSettings();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  if (!settings) return null;
  const current = settings.device_index;

  const options =
    cameras.data?.map((c) => ({
      index: c.index,
      name: c.name,
      detail: `${c.width}×${c.height}`,
    })) ?? [];
  const currentCamera = options.find((camera) => camera.index === current);
  // Keep the active device visible even if a rescan hasn't listed it.
  if (!options.find((o) => o.index === current)) {
    options.unshift({ index: current, name: `Camera ${current}`, detail: "" });
  }

  const select = (idx: number) => {
    if (idx !== current) update.mutate({ device_index: idx });
    setOpen(false);
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        title="Select camera"
        className="flex items-center gap-1.5 h-7 px-2 rounded border border-rule bg-paper-2 text-ink hover:bg-paper-3 text-[11px]"
      >
        <Webcam size={13} strokeWidth={2} className="text-ink-2" />
        <span className="max-w-44 truncate">
          {currentCamera?.name ?? `Camera ${current}`}
        </span>
        <ChevronDown size={12} className="text-ink-2" />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.1 }}
            className="absolute right-0 top-full mt-1 min-w-[260px] bg-paper border border-rule rounded-md shadow-lg z-50 py-1"
          >
            {options.map((opt) => (
              <button
                key={opt.index}
                onClick={() => select(opt.index)}
                className={
                  "w-full flex items-center justify-between gap-3 px-2.5 py-1.5 text-[12px] hover:bg-paper-2 text-left " +
                  (opt.index === current ? "text-ink" : "text-ink-2")
                }
              >
                <span className="flex items-center gap-1.5 min-w-0">
                  <span className="truncate">{opt.name}</span>
                  {opt.detail && (
                    <span className="text-[10px] text-ink-3 shrink-0">{opt.detail}</span>
                  )}
                </span>
                {opt.index === current && <Check size={12} className="text-accent" />}
              </button>
            ))}
            <div className="border-t border-rule mt-1 pt-1">
              <button
                onClick={() => cameras.refetch()}
                disabled={cameras.isFetching}
                className="w-full flex items-center gap-1.5 px-2.5 py-1.5 text-[11px] text-ink-2 hover:text-ink hover:bg-paper-2 text-left"
              >
                <RefreshCw
                  size={11}
                  strokeWidth={2}
                  className={cameras.isFetching ? "animate-spin" : ""}
                />
                {cameras.isFetching ? "Scanning" : "Rescan"}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
