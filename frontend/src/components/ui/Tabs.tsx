"use client";

/** Consistent underline tab bar used across list screens. */
export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="mb-5 flex gap-1 border-b border-hairline">
      {tabs.map((t) => {
        const active = value === t.value;
        return (
          <button
            key={t.value}
            type="button"
            onClick={() => onChange(t.value)}
            className={`relative px-4 py-2.5 text-sm font-medium transition-colors ${active ? "text-ink" : "text-mute hover:text-body"}`}
          >
            {t.label}
            {active ? <span className="absolute inset-x-4 bottom-0 h-0.5 rounded-full bg-ink" /> : null}
          </button>
        );
      })}
    </div>
  );
}
