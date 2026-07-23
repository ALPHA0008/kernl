import { CountUp } from "./CountUp";

/** Replay = CI for policy. A one-line diff (tighten the refund window) above the
 *  measured blast radius: decisions replayed, flips, golden failures, publish
 *  gate. Counters count up once on reveal. Values illustrative ("sample
 *  replay"). */
export function ReplayArtifact() {
  return (
    <div className="overflow-hidden rounded-xl bg-canvas shadow-[var(--shadow-2)]">
      <div className="flex items-center justify-between border-b border-hairline px-4 py-2.5">
        <span className="t-eyebrow">replay</span>
        <span className="font-mono text-[11px] text-mute">sample replay</span>
      </div>

      {/* the diff */}
      <div className="border-b border-hairline bg-[color:var(--color-canvas-soft-2)] px-4 py-3 font-mono text-[13px] leading-relaxed">
        <div className="text-mute">refund.annual_full_14d</div>
        <div className="text-deny">
          <span className="select-none pr-2 opacity-70">-</span>days_since_purchase &lt;= 14
        </div>
        <div className="text-approve">
          <span className="select-none pr-2 opacity-70">+</span>days_since_purchase &lt;= 7
        </div>
      </div>

      {/* the blast radius */}
      <div className="grid grid-cols-2 divide-x divide-hairline sm:grid-cols-4">
        {[
          { n: <CountUp to={1284} />, label: "decisions replayed" },
          { n: <CountUp to={3} />, label: "flips", tone: "text-escalate" },
          { n: <CountUp to={0} />, label: "golden failures", tone: "text-approve" },
          { n: "locked", label: "publish gate", mono: true },
        ].map((c, i) => (
          <div key={i} className="px-4 py-4">
            <div className={`font-mono text-2xl tabular-nums ${c.tone ?? "text-ink"} ${c.mono ? "text-base" : ""}`}>
              {c.n}
            </div>
            <div className="mt-1 font-mono text-[11px] uppercase tracking-wide text-mute">{c.label}</div>
          </div>
        ))}
      </div>
      <div className="border-t border-hairline px-4 py-3 text-[13px] text-body">
        Publish unlocks only when a human acknowledges the blast radius.
      </div>
    </div>
  );
}
