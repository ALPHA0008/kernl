/** The hero's live detail: sample ledger entries that rise and seal in sequence
 *  on load (CSS one-shot, see globals.css .strip-row/.seal-chip). Server
 *  component — no interactivity, the motion is pure CSS. Values are illustrative
 *  ("sample entries"), never claimed as real customer data. */
const ROWS = [
  { id: "#4819", policy: "refund.annual_full_14d", outcome: "approve", tone: "approve", hash: "e5f2…b1" },
  { id: "#4820", policy: "discount.startup_20", outcome: "approve", tone: "approve", hash: "77ac…04" },
  { id: "#4821", policy: "refund.high_value", outcome: "escalate", tone: "escalate", hash: "human review" },
] as const;

const TONE: Record<string, string> = {
  approve: "bg-approve-bg text-approve",
  escalate: "bg-escalate-bg text-escalate",
};

export function LedgerStrip() {
  return (
    <div
      className="mt-10 w-full overflow-hidden rounded-lg bg-canvas shadow-[var(--shadow-2)]"
      role="img"
      aria-label="Sample decision ledger: two refund and discount decisions approved and sealed, one high-value refund escalated to human review."
    >
      <div className="flex items-center justify-between border-b border-hairline px-4 py-2">
        <span className="t-eyebrow">decision ledger</span>
        <span className="font-mono text-[11px] text-mute">sample entries</span>
      </div>
      <div className="divide-y divide-hairline">
        {ROWS.map((r) => (
          <div
            key={r.id}
            className="strip-row grid grid-cols-[auto_1fr_auto] items-center gap-3 px-4 py-3 font-mono text-[13px] sm:grid-cols-[auto_1fr_auto_auto_auto]"
          >
            <span className="text-mute">{r.id}</span>
            <span className="truncate text-ink">{r.policy}</span>
            <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${TONE[r.tone]}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${r.tone === "approve" ? "bg-approve" : "bg-escalate"}`} />
              {r.outcome}
            </span>
            <span className="hidden text-mute sm:block">{r.hash}</span>
            <span
              className={`seal-chip hidden items-center gap-1 text-[11px] sm:inline-flex ${
                r.tone === "escalate" ? "text-escalate" : "text-approve"
              }`}
            >
              {r.tone === "escalate" ? "→ adjudicated" : "sealed"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
