import { HashChip } from "@/components/ui/HashChip";
import { fmtDate } from "@/lib/format";
import type { ReplayRun } from "@/lib/types";

function Stat({ label, value, tone }: { label: string; value: number; tone?: "bad" | "warn" | "ok" }) {
  const color =
    tone === "bad" && value > 0 ? "text-deny"
    : tone === "warn" && value > 0 ? "text-escalate"
    : tone === "ok" ? "text-approve"
    : "text-ink";
  return (
    <div className="rounded-md bg-canvas px-3 py-2.5 text-center shadow-[var(--shadow-1)]">
      <div className={`text-xl font-semibold tabular-nums ${color}`}>{value}</div>
      <div className="t-eyebrow mt-0.5">{label}</div>
    </div>
  );
}

/** The blast radius, rendered: golden pass/fail, flips (with the policy that
 *  caused each), new escalations, errors. CI for policy. */
export function ReplayReport({ run }: { run: ReplayRun }) {
  const s = run.summary;
  const flips = run.results.filter((r) => r.flipped);
  const goldenFails = run.results.filter((r) => r.golden_pass === false);
  const errors = run.results.filter((r) => r.error);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
        <Stat label="cases" value={s.total} />
        <Stat label="golden pass" value={s.golden_passed} tone="ok" />
        <Stat label="golden fail" value={s.golden_failed} tone="bad" />
        <Stat label="flips" value={s.flips} tone="warn" />
        <Stat label="new esc." value={s.new_escalations} tone="warn" />
        <Stat label="errors" value={s.errors} tone="bad" />
      </div>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-mute">
        <span className="flex items-center gap-1.5">candidate <HashChip hash={run.candidate_bundle_hash} chars={10} /></span>
        {run.reference_bundle_hash ? <span className="flex items-center gap-1.5">reference <HashChip hash={run.reference_bundle_hash} chars={10} /></span> : null}
        <span>ran {fmtDate(run.created_at)}</span>
        {run.acknowledged_by ? <span className="font-medium text-approve">acknowledged by {run.acknowledged_by}</span> : null}
      </div>

      {goldenFails.length > 0 ? (
        <section>
          <h3 className="t-eyebrow mb-2 text-deny">Golden failures · {goldenFails.length}</h3>
          <div className="overflow-x-auto rounded-lg bg-canvas shadow-[var(--shadow-1)]">
            <table className="table-ledger">
              <thead><tr><th>case</th><th>expected</th><th>got</th></tr></thead>
              <tbody>
                {goldenFails.map((r) => (
                  <tr key={r.case_id}>
                    <td className="font-mono text-xs text-ink">{r.case_id}</td>
                    <td className="font-mono text-xs">{r.expected_kind}{r.expected_action ? `:${r.expected_action}` : ""}</td>
                    <td className="font-mono text-xs text-deny">{r.candidate_kind ?? "—"}{r.candidate_action ? `:${r.candidate_action}` : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {flips.length > 0 ? (
        <section>
          <h3 className="t-eyebrow mb-2 text-escalate">Flips vs reference · {flips.length}</h3>
          <div className="overflow-x-auto rounded-lg bg-canvas shadow-[var(--shadow-1)]">
            <table className="table-ledger">
              <thead><tr><th>case</th><th>reference</th><th>candidate</th><th>caused by policy</th></tr></thead>
              <tbody>
                {flips.map((r) => (
                  <tr key={r.case_id}>
                    <td className="font-mono text-xs text-ink">{r.case_id}</td>
                    <td className="font-mono text-xs">{r.reference_kind ?? "—"}{r.reference_action ? `:${r.reference_action}` : ""}</td>
                    <td className="font-mono text-xs font-medium text-ink">{r.candidate_kind ?? "—"}{r.candidate_action ? `:${r.candidate_action}` : ""}</td>
                    <td className="font-mono text-xs text-mute">{r.candidate_policy_id ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {errors.length > 0 ? (
        <section>
          <h3 className="t-eyebrow mb-2 text-deny">Errors · {errors.length}</h3>
          <ul className="rounded-lg bg-canvas px-4 py-3 text-xs shadow-[var(--shadow-1)]">
            {errors.map((r) => (
              <li key={r.case_id} className="font-mono">{r.case_id}: <span className="text-deny">{r.error}</span></li>
            ))}
          </ul>
        </section>
      ) : null}

      {flips.length === 0 && goldenFails.length === 0 && errors.length === 0 ? (
        <p className="rounded-md bg-approve-bg px-4 py-3 text-sm font-medium text-approve">
          Clean run — no golden failures, no flips, no errors. Safe to publish.
        </p>
      ) : null}
    </div>
  );
}
