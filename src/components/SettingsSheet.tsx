import { AnimatePresence, motion } from "framer-motion";
import { Folder, X } from "lucide-react";
import { open } from "@tauri-apps/plugin-dialog";
import { useSettings, useUpdateSettings } from "../lib/api";
import { useApp } from "../state";

export function SettingsSheet() {
  const { settingsOpen, closeSettings } = useApp();
  const { data } = useSettings();
  const update = useUpdateSettings();

  if (!settingsOpen) return null;
  if (!data) {
    return (
      <Backdrop onClose={closeSettings}>
        <div className="p-6 text-[12px] text-ink-2">Loading</div>
      </Backdrop>
    );
  }

  const chooseDir = async () => {
    const picked = await open({
      directory: true,
      multiple: false,
      defaultPath: data.data_dir || undefined,
      title: "Choose save location",
    });
    if (typeof picked === "string" && picked !== data.data_dir) {
      update.mutate({ data_dir: picked });
    }
  };

  return (
    <AnimatePresence>
      <Backdrop onClose={closeSettings}>
        <div className="flex items-center justify-between h-9 px-3 border-b border-rule">
          <h2 className="text-[12px] text-ink">Settings</h2>
          <button onClick={closeSettings} className="text-ink-2 hover:text-ink p-1 rounded">
            <X size={14} strokeWidth={2} />
          </button>
        </div>

        <div className="p-3 space-y-4">
          <section>
            <h3 className="text-[11px] text-ink-2 mb-2">Save location</h3>
            <button
              onClick={chooseDir}
              className="w-full flex items-center gap-2 bg-paper-2 border border-rule rounded px-2.5 py-2 text-[12px] text-ink hover:bg-paper-3 transition-colors"
            >
              <Folder size={13} strokeWidth={2} className="text-ink-2 shrink-0" />
              <span className="flex-1 truncate text-left" title={data.data_dir}>
                {data.data_dir || "Choose a folder"}
              </span>
              <span className="text-[11px] text-ink-2 shrink-0">Change</span>
            </button>
            <p className="text-[10px] text-ink-3 mt-1">
              New clips and snapshots will be written here. Previous files stay where they were.
            </p>
          </section>
        </div>
      </Backdrop>
    </AnimatePresence>
  );
}

function Backdrop({ onClose, children }: { onClose: () => void; children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.12 }}
      onClick={onClose}
      className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center"
    >
      <motion.div
        initial={{ y: 10, scale: 0.98, opacity: 0 }}
        animate={{ y: 0, scale: 1, opacity: 1 }}
        exit={{ y: 6, scale: 0.98, opacity: 0 }}
        transition={{ type: "spring", stiffness: 500, damping: 36 }}
        onClick={(e) => e.stopPropagation()}
        className="bg-paper border border-rule rounded-lg w-full max-w-md shadow-xl max-h-[80vh] overflow-y-auto"
      >
        {children}
      </motion.div>
    </motion.div>
  );
}
