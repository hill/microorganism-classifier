import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronDown } from "lucide-react";

interface Props<T extends string> {
  value: T;
  onChange: (value: T) => void;
  options: readonly { value: T; label: string }[];
  className?: string;
}

export function Select<T extends string>({ value, onChange, options, className }: Props<T>) {
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

  const current = options.find((o) => o.value === value);

  return (
    <div ref={ref} className={"relative " + (className || "")}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 h-7 px-2.5 rounded-md bg-paper border border-rule text-ink hover:bg-paper-2 text-[12px] min-w-[88px] justify-between"
      >
        <span>{current?.label || value}</span>
        <ChevronDown size={12} className="text-ink-2" />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.1 }}
            className="absolute right-0 top-full mt-1 min-w-full bg-paper border border-rule rounded-md shadow-lg z-50 py-1"
          >
            {options.map((opt) => (
              <button
                key={opt.value}
                onClick={() => {
                  onChange(opt.value);
                  setOpen(false);
                }}
                className={
                  "w-full flex items-center justify-between gap-3 px-2.5 py-1.5 text-[12px] hover:bg-paper-2 text-left " +
                  (opt.value === value ? "text-ink" : "text-ink-2")
                }
              >
                <span>{opt.label}</span>
                {opt.value === value && <Check size={12} className="text-accent" />}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
