import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import type { Policy, Trace } from "@/lib/types";

const STATUS_STYLE: Record<string, string> = {
  matched: "bg-approve-bg text-approve",
  failed: "bg-deny-bg text-deny",
  undeterminable: "bg-escalate-bg text-escalate",
};

const RESULT_STYLE: Record<string, string> = {
  pass: "text-approve",
  fail: "text-deny",
  missing: "text-escalate",
};

function FactsBlock({ trace }: { trace: Trace }) {
  const effective = Object.entries(trace.facts_effective);
  return (
    <Card elevation={2}>
      <CardHeader eyebrow="Facts" />
      <CardBody className="!py-0">
        {effective.length === 0 ? (
          <p className="py-4 text-sm text-mute">No declared facts supplied.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="table-ledger">
              <thead>
                <tr>
                  <th>fact</th>
                  <th>value</th>
                  <th>source</th>
                </tr>
              </thead>
              <tbody>
                {effective.map(([name, value]) => (
                  <tr key={name}>
                    <td className="font-mono text-xs text-ink">{name}</td>
                    <td className="font-mono text-xs">{JSON.stringify(value)}</td>
                    <td className="text-xs text-mute">
                      {trace.defaults_applied.includes(name) ? "default applied" : "supplied"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {trace.facts_ignored.length > 0 ? (
          <p className="py-3 text-xs text-mute">
            ignored (not declared): <span className="font-mono">{trace.facts_ignored.join(", ")}</span>
          </p>
        ) : null}
      </CardBody>
    </Card>
  );
}

function PrecedenceBlock({ trace }: { trace: Trace }) {
  const p = trace.precedence;
  return (
    <Card elevation={2}>
      <CardHeader eyebrow="Precedence" />
      <CardBody className="text-sm">
        <div className="mb-2.5 flex items-baseline gap-3">
          <span className="w-28 shrink-0 text-mute">winner</span>
          <span className="font-mono text-xs font-medium text-ink">
            {p.winner ?? "— (no winning policy)"}
          </span>
        </div>
        {p.applied_rules.length > 0 ? (
          <div className="mb-2.5 flex items-baseline gap-3">
            <span className="w-28 shrink-0 text-mute">rules applied</span>
            <span className="font-mono text-xs">{p.applied_rules.join(" → ")}</span>
          </div>
        ) : null}
        {p.eliminated.length > 0 ? (
          <div className="mb-2.5 flex gap-3">
            <span className="w-28 shrink-0 text-mute">eliminated</span>
            <ul className="space-y-0.5">
              {p.eliminated.map((e) => (
                <li key={e.policy_id} className="font-mono text-xs">
                  {e.policy_id} <span className="text-mute">— by {e.eliminated_by} ({e.rule})</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {p.tie_between.length > 0 ? (
          <p className="mb-2 text-xs text-escalate">
            unresolvable tie between: <span className="font-mono">{p.tie_between.join(", ")}</span>
          </p>
        ) : null}
        {p.dominance_blocked_by.length > 0 ? (
          <p className="text-xs text-escalate">
            dominance rule: undeterminable higher-priority polic
            {p.dominance_blocked_by.length > 1 ? "ies" : "y"}{" "}
            <span className="font-mono">{p.dominance_blocked_by.join(", ")}</span> blocked the
            provisional winner — escalated rather than guessed.
          </p>
        ) : null}
      </CardBody>
    </Card>
  );
}

function PoliciesBlock({ trace, policies }: { trace: Trace; policies?: Policy[] }) {
  const evidenceFor = (policyId: string) => policies?.find((p) => p.id === policyId)?.evidence ?? [];
  return (
    <Card elevation={2}>
      <CardHeader eyebrow={`Policies considered · ${trace.policies.length}`} />
      <div>
        {trace.policies.map((pe) => {
          const evidence = evidenceFor(pe.policy_id);
          return (
            <details key={pe.policy_id} className="group border-b border-hairline last:border-b-0">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-3 transition-colors hover:bg-canvas-soft">
                <span className="flex items-center gap-2">
                  <svg width="10" height="10" viewBox="0 0 10 10" className="text-mute transition-transform group-open:rotate-90">
                    <path d="M3 2L7 5L3 8" stroke="currentColor" strokeWidth="1.3" fill="none" />
                  </svg>
                  <span className="min-w-0 truncate font-mono text-xs font-medium text-ink">{pe.policy_id}</span>
                </span>
                <span className="flex shrink-0 items-center gap-2">
                  <span className="t-eyebrow">prio {pe.priority} · spec {pe.specificity}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${STATUS_STYLE[pe.status] ?? ""}`}>
                    {pe.status}
                  </span>
                </span>
              </summary>
              <div className="px-5 pb-3.5">
                {pe.conditions.length === 0 ? (
                  <p className="text-xs text-mute">unconditional (reviewer-acknowledged)</p>
                ) : (
                  <div className="overflow-x-auto rounded-md border border-hairline">
                    <table className="table-ledger">
                      <thead>
                        <tr>
                          <th>condition</th>
                          <th>expected</th>
                          <th>actual</th>
                          <th>result</th>
                        </tr>
                      </thead>
                      <tbody>
                        {pe.conditions.map((c, i) => (
                          <tr key={`${c.field}-${i}`}>
                            <td className="font-mono text-xs text-ink">{c.field} {c.operator}</td>
                            <td className="font-mono text-xs">{JSON.stringify(c.expected)}</td>
                            <td className="font-mono text-xs">
                              {c.actual === null ? "∅ missing" : JSON.stringify(c.actual)}
                            </td>
                            <td className={`text-xs font-medium ${RESULT_STYLE[c.result] ?? ""}`}>{c.result}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {pe.missing_fields.length > 0 ? (
                  <p className="mt-2 text-xs text-escalate">
                    missing fields: <span className="font-mono">{pe.missing_fields.join(", ")}</span>
                  </p>
                ) : null}
                {policies ? (
                  <div className="mt-3">
                    <div className="t-eyebrow mb-1.5">evidence</div>
                    {evidence.length === 0 ? (
                      <p className="text-xs text-mute">no citation on this policy</p>
                    ) : (
                      <ul className="space-y-1.5">
                        {evidence.map((ev, i) => (
                          <li key={i} className="rounded-md border-l-2 border-ink bg-canvas-soft px-3 py-1.5">
                            <p className="text-xs italic text-ink">&ldquo;{ev.excerpt}&rdquo;</p>
                            <p className="mt-0.5 font-mono text-[10px] text-mute">{ev.source_id} · span {ev.span_start}–{ev.span_end}</p>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ) : null}
              </div>
            </details>
          );
        })}
      </div>
    </Card>
  );
}

/** The derivation, rendered — everything to answer "why this outcome". `policies`
 *  (the active bundle's policy list, only passed when it matches this trace's
 *  bundle hash exactly) lets each considered policy show its evidence inline —
 *  the "receipt" is incomplete without the citation that justified the rule. */
export function TraceView({ trace, policies }: { trace: Trace; policies?: Policy[] }) {
  return (
    <div className="space-y-4">
      <FactsBlock trace={trace} />
      <PrecedenceBlock trace={trace} />
      <PoliciesBlock trace={trace} policies={policies} />
      <p className="text-right font-mono text-[11px] text-mute">
        {trace.evaluator_version} · trace {trace.trace_version}
      </p>
    </div>
  );
}
