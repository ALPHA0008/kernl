"use client";

import { useEffect, useRef, useState } from "react";

/** Adds `.in-view` once the element scrolls into view (one-shot). The whole
 *  landing's reveal + artifact-entrance motion keys off this single observer
 *  pattern — no animation library. Reduced-motion is handled in CSS (the
 *  .reveal/.in-view rules collapse to no-op), so this stays purely structural. */
export function useReveal<T extends HTMLElement = HTMLDivElement>(
  opts: { amount?: number; rootMargin?: string } = {},
) {
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || inView) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            setInView(true);
            io.disconnect();
          }
        }
      },
      { threshold: opts.amount ?? 0.25, rootMargin: opts.rootMargin ?? "0px 0px -8% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [inView, opts.amount, opts.rootMargin]);

  return { ref, inView };
}
