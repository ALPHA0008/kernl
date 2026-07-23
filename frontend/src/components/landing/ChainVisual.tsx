/** The chain: four ledger entries linked prev → hash, one an adjudication that
 *  links back to the decision it resolves, closing with a verify stamp. Connective
 *  strokes draw on reveal (CSS keyed off parent `.in-view`). Values illustrative. */
const ENTRIES = [
  { id: "#4819", kind: "decision", policy: "refund.annual_full_14d", outcome: "approve", tone: "approve", hash: "e5f2…b1" },
  { id: "#4820", kind: "decision", policy: "discount.startup_20", outcome: "approve", tone: "approve", hash: "77ac…04" },
  { id: "#4821", kind: "decision", policy: "refund.high_value", outcome: "escalate", tone: "escalate", hash: "c19d…7a" },
  { id: "#4822", kind: "adjudication", policy: "human ruling · links #4821", outcome: "approve", tone: "approve", hash: "9b12…dc" },
] as const;

const DOT: Record<string, string> = { approve: "bg-approve", escalate: "bg-escalate" };

export function ChainVisual() {
  return (
    <div
      className="overflow-hidden rounded-xl bg-canvas shadow-[var(--shadow-2)]"
      role="img"
      aria-label="A hash chain of four ledger entries, each linking to the previous by hash, including an adjudication that links back to the escalated decision it resolves, closing with a verified stamp."
    >
      <div className="flex items-center justify-between border-b border-hairline px-4 py-2.5">
        <span className="t-eyebrow">hash-chained ledger</span>
        <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-approve">
          <span className="h-1.5 w-1.5 rounded-full bg-approve" />
          chain verified
        </span>
      </div>
      <ol className="divide-y divide-hairline">
        {ENTRIES.map((e, i) => (
          <li key={e.id} className="relative flex items-center gap-3 px-4 py-3.5 font-mono text-[13px]">
            {/* connective stroke to the next entry */}
            {i < ENTRIES.length - 1 ? (
              <svg
                aria-hidden
                className="absolute bottom-0 left-[26px] h-[14px] w-3 translate-y-full text-hairline-strong"
                viewBox="0 0 12 14"
              >
                <path className="chain-link" d="M6 0 V14" stroke="currentColor" strokeWidth="1.25" fill="none" />
              </svg>
            ) : null}
            <span className={`h-2 w-2 shrink-0 rounded-full ${DOT[e.tone]}`} />
            <span className="w-12 shrink-0 text-mute">{e.id}</span>
            <span className={`w-24 shrink-0 text-[11px] ${e.kind === "adjudication" ? "text-link" : "text-mute"}`}>
              {e.kind}
            </span>
            <span className="min-w-0 flex-1 truncate text-ink">{e.policy}</span>
            <span className="hidden shrink-0 text-mute sm:block">prev ⟶ {e.hash}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
