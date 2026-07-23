import { Fragment } from "react";

/** FACTS → POLICY BUNDLE → DECISION → LEDGER. The mechanism in one glance.
 *  Four labeled nodes with directional connectors between them: horizontal on
 *  desktop, vertical on mobile. Boxes and arrows are alternating flex siblings
 *  so every box shares one height and the arrows sit between them (not beneath).
 *  Server component — the only motion is the parent section's reveal. */
const NODES = [
  { label: "FACTS", sub: "typed input" },
  { label: "POLICY BUNDLE", sub: "versioned, cited" },
  { label: "DECISION", sub: "deterministic" },
  { label: "LEDGER", sub: "signed, chained" },
];

export function FlowDiagram() {
  return (
    <div
      className="w-full rounded-xl bg-canvas p-6 shadow-[var(--shadow-2)] sm:p-8"
      role="img"
      aria-label="Flow: typed facts enter a versioned, cited policy bundle, produce a deterministic decision, and are recorded as a signed, hash-chained ledger entry."
    >
      <div className="flex flex-col items-stretch sm:flex-row sm:items-stretch">
        {NODES.map((n, i) => (
          <Fragment key={n.label}>
            <div className="flex flex-1 flex-col items-center justify-center rounded-lg border border-hairline bg-canvas-soft px-4 py-4 text-center">
              <span className="font-mono text-[11px] font-medium uppercase tracking-wide text-ink">
                {n.label}
              </span>
              <span className="mt-0.5 font-mono text-[10px] text-mute">{n.sub}</span>
            </div>
            {i < NODES.length - 1 ? (
              <div
                aria-hidden
                className="flex shrink-0 items-center justify-center text-hairline-strong"
              >
                {/* horizontal arrow (desktop) */}
                <svg className="hidden sm:block" width="32" height="10" viewBox="0 0 32 10" fill="none">
                  <line x1="2" y1="5" x2="26" y2="5" stroke="currentColor" strokeWidth="1.25" />
                  <path d="M22 1.5 L27 5 L22 8.5" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                {/* vertical arrow (mobile) */}
                <svg className="my-1.5 sm:hidden" width="10" height="24" viewBox="0 0 10 24" fill="none">
                  <line x1="5" y1="2" x2="5" y2="18" stroke="currentColor" strokeWidth="1.25" />
                  <path d="M1.5 14 L5 19 L8.5 14" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
            ) : null}
          </Fragment>
        ))}
      </div>
    </div>
  );
}
