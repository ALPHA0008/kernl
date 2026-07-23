"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";

/** Consistent underline tab bar used across list screens. A SINGLE underline
 *  slides between tabs (measured from the active button) rather than a fresh
 *  span teleporting in on each tab — the underline is this app's most-repeated
 *  interaction, so the movement should read as one continuous element.
 *  Reduced-motion drops the slide (the indicator still jumps, just instantly). */
export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  const listRef = useRef<HTMLDivElement>(null);
  const btnRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [indicator, setIndicator] = useState<{ left: number; width: number } | null>(null);
  // Suppress the slide on first paint (and after resize) so the indicator
  // appears in place instead of animating in from the left edge.
  const [ready, setReady] = useState(false);

  const measure = () => {
    const el = btnRefs.current[value];
    const list = listRef.current;
    if (!el || !list) return;
    setIndicator({ left: el.offsetLeft, width: el.offsetWidth });
  };

  useLayoutEffect(measure, [value, tabs]);

  useEffect(() => {
    const id = requestAnimationFrame(() => setReady(true));
    const onResize = () => {
      setReady(false);
      measure();
      requestAnimationFrame(() => setReady(true));
    };
    window.addEventListener("resize", onResize);
    return () => {
      cancelAnimationFrame(id);
      window.removeEventListener("resize", onResize);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div ref={listRef} className="relative mb-5 flex gap-1 border-b border-hairline">
      {tabs.map((t) => {
        const active = value === t.value;
        return (
          <button
            key={t.value}
            ref={(el) => {
              btnRefs.current[t.value] = el;
            }}
            type="button"
            onClick={() => onChange(t.value)}
            className={`relative px-4 py-2.5 text-sm font-medium transition-colors ${
              active ? "text-ink" : "text-mute hover:text-body"
            }`}
          >
            {t.label}
          </button>
        );
      })}
      {indicator ? (
        <span
          aria-hidden
          className={`absolute bottom-0 h-0.5 rounded-full bg-ink ${
            ready ? "tab-underline" : ""
          }`}
          style={{ left: indicator.left + 16, width: indicator.width - 32 }}
        />
      ) : null}
    </div>
  );
}
