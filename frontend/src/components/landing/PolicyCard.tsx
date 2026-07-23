/** Policy as code: a typed condition rule with its byte-verified citation chip.
 *  The "no uncited norm" rule made visible. Values illustrative. */
export function PolicyCard() {
  return (
    <div
      className="overflow-hidden rounded-xl bg-canvas shadow-[var(--shadow-2)]"
      role="img"
      aria-label="Policy refund.annual_full_14d: if plan type is annual and days since purchase is 14 or fewer, then approve a full refund. Cited to refund-policy.md, bytes 214 to 312, verified."
    >
      <div className="flex items-center justify-between border-b border-hairline px-4 py-2.5">
        <span className="font-mono text-[13px] font-medium text-ink">refund.annual_full_14d</span>
        <span className="font-mono text-[11px] text-mute">priority 70</span>
      </div>
      <div className="space-y-1 px-4 py-4 font-mono text-[13px] leading-relaxed">
        <div>
          <span className="text-link">IF</span> <span className="text-ink">plan_type</span>{" "}
          <span className="text-mute">=</span> <span className="text-approve">annual</span>
        </div>
        <div>
          <span className="text-link">AND</span> <span className="text-ink">days_since_purchase</span>{" "}
          <span className="text-mute">&lt;=</span> <span className="text-approve">14</span>
        </div>
        <div>
          <span className="text-link">THEN</span> <span className="text-ink">approve</span>{" "}
          <span className="text-mute">full_refund</span>
        </div>
      </div>
      <div className="flex items-center gap-2 border-t border-hairline bg-canvas-soft px-4 py-2.5">
        <svg width="13" height="13" viewBox="0 0 16 16" className="shrink-0 text-approve" aria-hidden>
          <path d="M3.5 8.5l3 3 6-6" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="font-mono text-[11px] text-body">refund-policy.md · bytes 214-312 · verified</span>
      </div>
    </div>
  );
}
