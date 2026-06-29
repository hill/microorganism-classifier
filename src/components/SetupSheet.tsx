import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { useCreateSample, useCreateSession } from "../lib/api";
import { useApp } from "../state";
import { Select } from "./Select";

const OBJECTIVES = [
  { value: "4x", label: "4x" },
  { value: "10x", label: "10x" },
  { value: "40x", label: "40x" },
  { value: "100x oil", label: "100x oil" },
] as const;

const ILLUMINATIONS = [
  { value: "brightfield", label: "Brightfield" },
  { value: "darkfield", label: "Darkfield" },
  { value: "phase", label: "Phase" },
  { value: "DIC", label: "DIC" },
] as const;

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-[11px] text-ink-2 mb-1">{label}</span>
      {children}
    </label>
  );
}

const inputCls =
  "w-full bg-paper-2 border border-rule rounded px-2 py-1.5 text-[12px] text-ink";

export function SetupSheet() {
  const { setupOpen, closeSetup, sessionId } = useApp();
  const createSession = useCreateSession();
  const createSample = useCreateSample();

  const [site, setSite] = useState("");
  const [container, setContainer] = useState("Jam jar");
  const [preparation, setPreparation] = useState("Wet mount");
  const [objective, setObjective] = useState<(typeof OBJECTIVES)[number]["value"]>("10x");
  const [illumination, setIllumination] = useState<(typeof ILLUMINATIONS)[number]["value"]>(
    "brightfield",
  );
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      let sid = sessionId;
      if (!sid) {
        const s = await createSession.mutateAsync(undefined);
        sid = s.id;
      }
      await createSample.mutateAsync({
        session_id: sid!,
        site,
        container,
        preparation,
      });
      void objective;
      void illumination;
      closeSetup();
    } finally {
      setBusy(false);
    }
  };

  return (
    <AnimatePresence>
      {setupOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.12 }}
          onClick={closeSetup}
          className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center"
        >
          <motion.div
            initial={{ y: 10, scale: 0.98, opacity: 0 }}
            animate={{ y: 0, scale: 1, opacity: 1 }}
            exit={{ y: 6, scale: 0.98, opacity: 0 }}
            transition={{ type: "spring", stiffness: 500, damping: 36 }}
            onClick={(e) => e.stopPropagation()}
            className="bg-paper border border-rule rounded-lg w-full max-w-md shadow-xl"
          >
            <div className="flex items-center justify-between h-9 px-3 border-b border-rule">
              <h2 className="text-[12px] text-ink">Sample</h2>
              <button onClick={closeSetup} className="text-ink-2 hover:text-ink p-1 rounded">
                <X size={14} strokeWidth={2} />
              </button>
            </div>

            <div className="p-3 grid grid-cols-2 gap-3">
              <Field label="Site">
                <input
                  className={inputCls}
                  value={site}
                  onChange={(e) => setSite(e.target.value)}
                  placeholder="Pond"
                />
              </Field>
              <Field label="Container">
                <input
                  className={inputCls}
                  value={container}
                  onChange={(e) => setContainer(e.target.value)}
                />
              </Field>
              <Field label="Preparation">
                <input
                  className={inputCls}
                  value={preparation}
                  onChange={(e) => setPreparation(e.target.value)}
                />
              </Field>
              <div />
              <Field label="Objective">
                <Select value={objective} onChange={setObjective} options={OBJECTIVES} />
              </Field>
              <Field label="Illumination">
                <Select
                  value={illumination}
                  onChange={setIllumination}
                  options={ILLUMINATIONS}
                />
              </Field>
            </div>

            <div className="px-3 py-2 border-t border-rule flex justify-end gap-1">
              <button
                onClick={closeSetup}
                className="text-[12px] text-ink-2 hover:text-ink px-2 py-1 rounded"
              >
                Cancel
              </button>
              <motion.button
                whileTap={{ scale: 0.97 }}
                onClick={save}
                disabled={busy}
                className="bg-accent text-paper px-3 py-1 rounded text-[12px] font-medium disabled:opacity-50"
              >
                {busy ? "Saving" : "Save"}
              </motion.button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
