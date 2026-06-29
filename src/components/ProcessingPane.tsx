import { AnimatePresence, motion } from "framer-motion";
import { RotateCcw, X } from "lucide-react";
import type { CSSProperties } from "react";
import { useSettings, useUpdateSettings } from "../lib/api";
import type { Settings, SettingsPatch } from "../lib/api";
import { useApp } from "../state";

type ProcessingValues = Pick<
  Settings,
  | "brightness"
  | "contrast"
  | "gamma"
  | "wb_r"
  | "wb_g"
  | "wb_b"
  | "invert"
  | "local_contrast"
  | "sharpness"
  | "grayscale"
>;

interface Preset {
  id: string;
  name: string;
  detail: string;
  values: ProcessingValues;
  previewStyle: CSSProperties;
}

const NATURAL: ProcessingValues = {
  brightness: 0,
  contrast: 1,
  gamma: 1,
  wb_r: 1,
  wb_g: 1,
  wb_b: 1,
  invert: false,
  local_contrast: 0,
  sharpness: 0,
  grayscale: false,
};

const PRESETS: Preset[] = [
  {
    id: "natural",
    name: "Natural",
    detail: "Unprocessed reference",
    values: NATURAL,
    previewStyle: {},
  },
  {
    id: "cell-detail",
    name: "Cell detail",
    detail: "Local contrast and fine edges",
    values: {
      ...NATURAL,
      contrast: 1.15,
      local_contrast: 2,
      sharpness: 0.45,
    },
    previewStyle: { filter: "contrast(1.45) saturate(.8)" },
  },
  {
    id: "low-light",
    name: "Low light",
    detail: "Lift dim structures",
    values: {
      ...NATURAL,
      brightness: 12,
      contrast: 1.1,
      gamma: 1.35,
      local_contrast: 1.25,
      sharpness: 0.2,
    },
    previewStyle: { filter: "brightness(1.35) contrast(1.15)" },
  },
  {
    id: "monochrome",
    name: "Monochrome",
    detail: "Shape without color distraction",
    values: {
      ...NATURAL,
      contrast: 1.2,
      grayscale: true,
      local_contrast: 1.5,
      sharpness: 0.3,
    },
    previewStyle: { filter: "grayscale(1) contrast(1.35)" },
  },
  {
    id: "negative",
    name: "Negative",
    detail: "Reverse faint light structures",
    values: {
      ...NATURAL,
      contrast: 1.15,
      invert: true,
      local_contrast: 1.25,
      sharpness: 0.25,
    },
    previewStyle: { filter: "invert(1) contrast(1.25)" },
  },
  {
    id: "warm-stain",
    name: "Warm stain",
    detail: "Emphasize red and brown stain",
    values: {
      ...NATURAL,
      contrast: 1.1,
      wb_r: 1.2,
      wb_g: 0.95,
      wb_b: 0.82,
      local_contrast: 1,
      sharpness: 0.2,
    },
    previewStyle: { filter: "sepia(.35) saturate(1.35) contrast(1.15)" },
  },
];

const PROCESSING_KEYS = Object.keys(NATURAL) as (keyof ProcessingValues)[];

function matchesPreset(settings: Settings, values: ProcessingValues) {
  return PROCESSING_KEYS.every((key) => {
    const actual = settings[key];
    const expected = values[key];
    return typeof actual === "number" && typeof expected === "number"
      ? Math.abs(actual - expected) < 0.001
      : actual === expected;
  });
}

export function ProcessingPane() {
  const { processingOpen, closeProcessing } = useApp();
  const { data } = useSettings();
  const update = useUpdateSettings();

  if (!processingOpen) return null;

  const patch = (next: SettingsPatch) => update.mutate(next);
  const activePreset = data
    ? PRESETS.find((preset) => matchesPreset(data, preset.values))?.id
    : undefined;

  return (
    <AnimatePresence>
      <motion.aside
        initial={{ x: 18, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 12, opacity: 0 }}
        transition={{ type: "spring", stiffness: 500, damping: 38 }}
        className="fixed z-40 right-2 top-12 bottom-13 w-[360px] max-w-[calc(100vw-16px)] bg-paper border border-rule-2 rounded-lg shadow-2xl flex flex-col overflow-hidden"
        aria-label="Image enhancement"
      >
        <div className="flex items-center justify-between h-10 px-3 border-b border-rule shrink-0">
          <div>
            <h2 className="text-[12px] font-medium text-ink">Image enhancement</h2>
            <p className="text-[9px] text-ink-3">Live preview, clips, and snapshots</p>
          </div>
          <button
            onClick={closeProcessing}
            title="Close image enhancement"
            className="text-ink-2 hover:text-ink p-1 rounded"
          >
            <X size={14} strokeWidth={2} />
          </button>
        </div>

        {!data ? (
          <div className="p-4 text-[12px] text-ink-2">Loading</div>
        ) : (
          <div className="overflow-y-auto p-3">
            <section>
              <div className="flex items-baseline justify-between mb-2">
                <h3 className="text-[11px] text-ink-2">Quick looks</h3>
                <span className="text-[9px] text-ink-3">
                  {activePreset ? "Preset active" : "Custom"}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2">
                {PRESETS.map((preset) => {
                  const active = activePreset === preset.id;
                  return (
                    <button
                      key={preset.id}
                      onClick={() => patch(preset.values)}
                      aria-pressed={active}
                      title={preset.detail}
                      className={
                        "group rounded-md border p-1.5 text-left transition-colors " +
                        (active
                          ? "border-accent bg-accent/10"
                          : "border-rule bg-paper-2 hover:border-rule-2 hover:bg-paper-3")
                      }
                    >
                      <div
                        className="processing-preview relative h-12 rounded overflow-hidden mb-1.5"
                        style={preset.previewStyle}
                      >
                        <span className="processing-preview-cell" />
                        <span className="processing-preview-cell processing-preview-cell-small" />
                      </div>
                      <div className={"text-[10px] " + (active ? "text-accent" : "text-ink")}>
                        {preset.name}
                      </div>
                    </button>
                  );
                })}
              </div>
            </section>

            <section className="mt-5 pt-3 border-t border-rule">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-[11px] text-ink-2">Fine tune</h3>
                <button
                  onClick={() => patch(NATURAL)}
                  className="flex items-center gap-1 text-[10px] text-ink-2 hover:text-ink"
                >
                  <RotateCcw size={10} strokeWidth={2} />
                  Reset
                </button>
              </div>

              <Slider
                label="Brightness"
                value={data.brightness}
                min={-100}
                max={100}
                step={1}
                format={(v) => `${v > 0 ? "+" : ""}${v}`}
                onChange={(v) => patch({ brightness: v })}
              />
              <Slider
                label="Global contrast"
                value={data.contrast}
                min={0.3}
                max={2.5}
                step={0.05}
                format={(v) => `${v.toFixed(2)}×`}
                onChange={(v) => patch({ contrast: v })}
              />
              <Slider
                label="Local contrast"
                value={data.local_contrast}
                min={0}
                max={4}
                step={0.25}
                format={(v) => (v === 0 ? "Off" : v.toFixed(2))}
                onChange={(v) => patch({ local_contrast: v })}
              />
              <Slider
                label="Sharpness"
                value={data.sharpness}
                min={0}
                max={2}
                step={0.05}
                format={(v) => (v === 0 ? "Off" : v.toFixed(2))}
                onChange={(v) => patch({ sharpness: v })}
              />
              <Slider
                label="Gamma"
                value={data.gamma}
                min={0.3}
                max={3}
                step={0.05}
                format={(v) => v.toFixed(2)}
                onChange={(v) => patch({ gamma: v })}
              />

              <div className="mt-4 mb-2 text-[11px] text-ink-2">White balance</div>
              <Slider
                label="Red"
                value={data.wb_r}
                min={0.3}
                max={2.5}
                step={0.05}
                format={(v) => v.toFixed(2)}
                onChange={(v) => patch({ wb_r: v })}
                accent="#fb4934"
              />
              <Slider
                label="Green"
                value={data.wb_g}
                min={0.3}
                max={2.5}
                step={0.05}
                format={(v) => v.toFixed(2)}
                onChange={(v) => patch({ wb_g: v })}
                accent="#b8bb26"
              />
              <Slider
                label="Blue"
                value={data.wb_b}
                min={0.3}
                max={2.5}
                step={0.05}
                format={(v) => v.toFixed(2)}
                onChange={(v) => patch({ wb_b: v })}
                accent="#83a598"
              />

              <div className="mt-4 pt-1 border-t border-rule">
                <Checkbox
                  label="Monochrome"
                  value={data.grayscale}
                  onChange={(value) => patch({ grayscale: value })}
                />
                <Checkbox
                  label="Invert"
                  value={data.invert}
                  onChange={(value) => patch({ invert: value })}
                />
              </div>
            </section>

            <p className="text-[9px] leading-4 text-ink-3 mt-4 border-t border-rule pt-3">
              Enhancement changes saved pixels and can affect automated detection. Use Natural for
              an unprocessed reference.
            </p>
          </div>
        )}
      </motion.aside>
    </AnimatePresence>
  );
}

function Slider({
  label,
  value,
  min,
  max,
  step,
  format,
  onChange,
  accent,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (value: number) => string;
  onChange: (value: number) => void;
  accent?: string;
}) {
  return (
    <label className="block mb-2.5">
      <div className="flex justify-between items-baseline mb-1">
        <span className="text-[11px] text-ink">{label}</span>
        <span className="text-[10px] text-ink-2 tabular-nums">{format(value)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        style={accent ? ({ accentColor: accent } as CSSProperties) : undefined}
        className="w-full accent-accent"
      />
    </label>
  );
}

function Checkbox({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 mt-3 w-fit text-[11px] text-ink">
      <input
        type="checkbox"
        checked={value}
        onChange={(event) => onChange(event.target.checked)}
        className="size-3.5 accent-accent"
      />
      <span>{label}</span>
    </label>
  );
}
