/** Determinism proof: three identical runs of the same evaluation, one shared
 *  outcome hash. A terminal because this IS terminal output (mono earns its
 *  place here: real command + real data, not costume). Lines reveal in sequence
 *  when the parent enters view. Values illustrative. */
export function Terminal() {
  return (
    <div
      className="overflow-hidden rounded-xl bg-[color:var(--color-canvas-soft-2)] shadow-[var(--shadow-2)]"
      role="img"
      aria-label="Three runs of the same refund evaluation return the identical outcome and a single matching outcome hash, three of three."
    >
      <div className="flex items-center gap-1.5 border-b border-hairline px-4 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-hairline-strong" />
        <span className="h-2.5 w-2.5 rounded-full bg-hairline-strong" />
        <span className="h-2.5 w-2.5 rounded-full bg-hairline-strong" />
        <span className="ml-2 font-mono text-[11px] text-mute">kernl evaluate</span>
      </div>
      <div className="space-y-1 px-4 py-4 font-mono text-[13px] leading-relaxed sm:text-[13px]">
        <div className="term-line text-body">
          <span className="text-mute">$</span> kernl evaluate refund --facts case_4821.json{" "}
          <span className="text-mute">× 3 runs</span>
        </div>
        <div className="term-line text-ink">
          run 1 → <span className="text-approve">approve</span> · approve_full_refund · refund.annual_full_14d
        </div>
        <div className="term-line text-ink">
          run 2 → <span className="text-approve">approve</span> · approve_full_refund · refund.annual_full_14d
        </div>
        <div className="term-line text-ink">
          run 3 → <span className="text-approve">approve</span> · approve_full_refund · refund.annual_full_14d
        </div>
        <div className="term-line pt-1 text-body">
          outcome hash <span className="text-ink">9b12dcee…</span>{" "}
          <span className="text-approve">identical · 3 of 3</span>
        </div>
      </div>
    </div>
  );
}
