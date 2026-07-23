"use client";

import { useEffect, useRef, useState } from "react";

/** Counts from 0 to `to` once, when scrolled into view. rAF-driven, no React
 *  state on the animation frame beyond the displayed value. Reduced-motion and
 *  no-IO paths render the final value immediately. */
export function CountUp({
  to,
  durationMs = 850,
  className = "",
  format = (n: number) => n.toLocaleString(),
}: {
  to: number;
  durationMs?: number;
  className?: string;
  format?: (n: number) => string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const [value, setValue] = useState(0);

  useEffect(() => {
    const el = ref.current;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!el || reduce) {
      setValue(to);
      return;
    }
    let raf = 0;
    let start = 0;
    const io = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting) return;
        io.disconnect();
        const ease = (t: number) => 1 - Math.pow(1 - t, 3); // ease-out cubic
        const tick = (now: number) => {
          if (!start) start = now;
          const p = Math.min(1, (now - start) / durationMs);
          setValue(Math.round(ease(p) * to));
          if (p < 1) raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
      },
      { threshold: 0.5 },
    );
    io.observe(el);
    return () => {
      io.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [to, durationMs]);

  return (
    <span ref={ref} className={className}>
      {format(value)}
    </span>
  );
}
