import { OutcomeBadge } from "@/components/ui/OutcomeBadge";
import type { Policy } from "@/lib/types";

/** One policy, with conditions, effect, authority, and — non-negotiable — its
 *  evidence spans shown inline. A published policy always has a citation. */
export function PolicyCard({ policy }: { policy: Policy }) {
  return (
    <details className="group rounded-lg bg-canvas shadow-[var(--shadow-1)] transition-shadow open:shadow-[var(--shadow-2)]">
      <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3 transition-colors hover:bg-canvas-soft">
        <svg width="10" height="10" viewBox="0 0 10 10" className="shrink-0 text-mute transition-transform group-open:rotate-90">
          <path d="M3 2L7 5L3 8" stroke="currentColor" strokeWidth="1.3" fill="none" />
        </svg>
        <span className="min-w-0 flex-1 truncate font-mono text-[13px] font-medium text-ink">{policy.id}</span>
        <span className="shrink-0 font-mono text-[11px] tabular-nums text-mute">prio {policy.priority}</span>
        <OutcomeBadge kind={policy.effect.kind} />
      </summary>

      <div className="border-t border-hairline px-5 py-4">
        {policy.rationale ? <p className="mb-4 text-sm text-body">{policy.rationale}</p> : null}

        <div className="mb-4">
          <div className="t-eyebrow mb-1">effect</div>
          <p className="font-mono text-xs text-ink">
            {policy.effect.kind} → {policy.effect.action}
            {policy.authority?.approval_required ? ` (approval: ${policy.authority.approver_role ?? "required"})` : ""}
          </p>
        </div>

        <div className="mb-4">
          <div className="t-eyebrow mb-1">conditions</div>
          {policy.conditions.length === 0 ? (
            <p className="text-xs text-mute">unconditional{policy.unconditional_ack ? " (reviewer-acknowledged)" : ""}</p>
          ) : (
            <ul className="space-y-0.5">
              {policy.conditions.map((c, i) => (
                <li key={`${c.field}-${i}`} className="font-mono text-xs text-ink">
                  {c.field} {c.operator} {JSON.stringify(c.value)} <span className="text-mute">({c.value_type})</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {policy.overrides.length > 0 ? (
          <div className="mb-4">
            <div className="t-eyebrow mb-1">overrides</div>
            <p className="font-mono text-xs text-ink">{policy.overrides.join(", ")}</p>
          </div>
        ) : null}

        <div>
          <div className="t-eyebrow mb-1">evidence</div>
          {policy.evidence.length === 0 ? (
            <p className="text-xs text-deny">no citation — not runtime authority</p>
          ) : (
            <ul className="space-y-2">
              {policy.evidence.map((ev, i) => (
                <li key={i} className="rounded-md border-l-2 border-ink bg-canvas-soft px-3 py-2">
                  <p className="text-xs italic text-ink">&ldquo;{ev.excerpt}&rdquo;</p>
                  <p className="mt-1 font-mono text-[10px] text-mute">{ev.source_id} · span {ev.span_start}–{ev.span_end}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </details>
  );
}
