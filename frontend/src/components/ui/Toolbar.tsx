"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/** Compact inline control bar for list screens — filters left, actions right.
 *  Replaces the full-width stacked selects that made Ledger feel unfinished. */
export function Toolbar({
  children,
  actions,
}: {
  children?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      {children}
      {actions ? <div className="ml-auto flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}

/** A table wrapped in the standard elevated surface with horizontal scroll AND
 *  a visible scroll affordance: a soft right-edge fade appears only when the
 *  content overflows and isn't scrolled to the end, so a user on a narrow
 *  viewport knows there are more columns (e.g. the Escalations action column)
 *  rather than silently losing them off-screen. */
export function TableSurface({ children }: { children: React.ReactNode }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showFade, setShowFade] = useState(false);

  const update = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    // fade shows when there's more to the right than currently scrolled to
    const overflowRight = el.scrollWidth - el.clientWidth - el.scrollLeft;
    setShowFade(overflowRight > 1);
  }, []);

  useEffect(() => {
    update();
    const el = scrollRef.current;
    if (!el) return;
    el.addEventListener("scroll", update, { passive: true });
    // ResizeObserver catches breakpoint changes / data reflows
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => {
      el.removeEventListener("scroll", update);
      ro.disconnect();
    };
  }, [update]);

  return (
    <div className="relative rounded-lg bg-canvas shadow-[var(--shadow-1)]">
      <div ref={scrollRef} className="overflow-x-auto rounded-lg">
        {children}
      </div>
      {/* right-edge scroll cue — non-interactive, motion-friendly opacity only */}
      <div
        aria-hidden
        className={`pointer-events-none absolute inset-y-0 right-0 w-10 rounded-r-lg bg-gradient-to-l from-canvas to-transparent transition-opacity duration-200 ${
          showFade ? "opacity-100" : "opacity-0"
        }`}
      />
    </div>
  );
}
