"use client";

import { OutcomeBadge } from "@/components/ui/OutcomeBadge";
import type { BundleDiff, PolicyChange } from "@/lib/types";

const CHANGE_LABEL: Record<PolicyChange["change"], string> = {
  added: "added",
  removed: "removed",
  modified: "modified",
};

const CHANGE_DOT: Record<PolicyChange["change"], string> = {
  added: "bg-approve",
  removed: "bg-deny",
  modified: "bg-route",
};

function ChangeRow({ change }: { change: PolicyChange }) {
  const policy = change.after ?? change.before!;
  return (
    <div className="rounded-lg bg-canvas shadow-[var(--shadow-1)]">
      <div className="flex items-center gap-3 px-4 py-3">
        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${CHANGE_DOT[change.change]}`} />
        <span className="min-w-0 flex-1 truncate font-mono text-[13px] font-medium text-ink">
          {change.policy_id}
        </span>
        <span className="shrink-0 text-[11px] font-medium uppercase tracking-wide text-mute">
          {CHANGE_LABEL[change.change]}
        </span>
        <OutcomeBadge kind={policy.effect.kind} />
      </div>

      {change.change === "modified" && change.changed_fields.length > 0 ? (
        <div className="border-t border-hairline px-5 py-3">
          <div className="t-eyebrow mb-2">changed fields</div>
          <div className="flex flex-wrap gap-1.5">
            {change.changed_fields.map((f) => (
              <span
                key={f}
                className="rounded-full bg-canvas-soft px-2 py-0.5 font-mono text-[11px] text-body shadow-[var(--shadow-1)]"
              >
                {f}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {change.change === "modified" && change.before && change.after ? (
        <div className="grid grid-cols-1 gap-0 border-t border-hairline sm:grid-cols-2">
          <div className="border-b border-hairline px-5 py-4 sm:border-b-0 sm:border-r">
            <div className="t-eyebrow mb-2 text-deny">before</div>
            <PolicyDetail policy={change.before} />
          </div>
          <div className="px-5 py-4">
            <div className="t-eyebrow mb-2 text-approve">after</div>
            <PolicyDetail policy={change.after} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function PolicyDetail({ policy }: { policy: PolicyChange["before"] }) {
  if (!policy) return null;
  return (
    <div className="space-y-2 text-xs">
      <p className="font-mono text-ink">
        {policy.effect.kind} → {policy.effect.action} · prio {policy.priority}
      </p>
      {policy.conditions.length === 0 ? (
        <p className="text-mute">unconditional</p>
      ) : (
        <ul className="space-y-0.5">
          {policy.conditions.map((c, i) => (
            <li key={`${c.field}-${i}`} className="font-mono text-ink">
              {c.field} {c.operator} {JSON.stringify(c.value)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Structural diff between a candidate bundle and its baseline (default: the
 *  active published bundle) -- the Policy Workbench's "blast radius, in
 *  policy terms" view. Complementary to Replay, which diffs decision
 *  *outcomes* on a case set; this diffs the policies themselves. */
export function BundleDiffView({ diff, baselineRecordId }: { diff: BundleDiff; baselineRecordId: string | null }) {
  const isEmpty = diff.added.length === 0 && diff.removed.length === 0 && diff.modified.length === 0;

  if (!baselineRecordId) {
    return (
      <p className="rounded-md bg-canvas-soft px-3.5 py-2.5 text-sm text-body shadow-[var(--shadow-1)]">
        No baseline to compare against — this is either the active bundle itself or a tenant&rsquo;s first draft.
      </p>
    );
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
        <span className="text-approve">
          <span className="font-medium tabular-nums">{diff.added.length}</span> added
        </span>
        <span className="text-hairline-strong">·</span>
        <span className="text-deny">
          <span className="font-medium tabular-nums">{diff.removed.length}</span> removed
        </span>
        <span className="text-hairline-strong">·</span>
        <span className="text-route">
          <span className="font-medium tabular-nums">{diff.modified.length}</span> modified
        </span>
        <span className="text-hairline-strong">·</span>
        <span className="text-body">
          <span className="font-medium tabular-nums">{diff.unchanged_count}</span> unchanged
        </span>
      </div>

      {isEmpty ? (
        <p className="rounded-lg bg-canvas-soft px-5 py-8 text-center text-sm text-mute shadow-[var(--shadow-1)]">
          No policy content differs from the baseline.
        </p>
      ) : (
        <div className="space-y-1.5">
          {[...diff.removed, ...diff.modified, ...diff.added].map((c) => (
            <ChangeRow key={c.policy_id} change={c} />
          ))}
        </div>
      )}
    </div>
  );
}
