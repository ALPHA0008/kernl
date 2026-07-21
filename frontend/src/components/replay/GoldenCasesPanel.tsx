"use client";

import { useEffect, useMemo, useState } from "react";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { OutcomeBadge } from "@/components/ui/OutcomeBadge";
import { SkeletonTable } from "@/components/ui/Skeleton";
import { TableSurface } from "@/components/ui/Toolbar";
import { listCases } from "@/lib/api";
import { useSession } from "@/lib/auth";
import type { GoldenCase } from "@/lib/types";

/** The golden-case corpus, browsable: what replay actually runs against, and
 *  where adjudicated escalations land once promoted (V1_EXECUTION_PLAN.md
 *  §7's "golden-case growth" loop step, and the Escalations screen's own
 *  success metric -- "≥30% of resolutions promoted to golden cases" -- made
 *  visible instead of unverifiable). `[synthetic]` is always shown, never
 *  quoted as capability without the label (CLAUDE.md rule). */
export function GoldenCasesPanel() {
  const { apiKey } = useSession();
  const [cases, setCases] = useState<GoldenCase[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    listCases(apiKey)
      .then(({ cases }) => setCases([...cases].sort((a, b) => a.workflow.localeCompare(b.workflow))))
      .catch(setError);
  }, [apiKey]);

  const promoted = useMemo(() => cases?.filter((c) => c.provenance.startsWith("adjudication:")) ?? [], [cases]);
  const synthetic = useMemo(() => cases?.filter((c) => c.synthetic) ?? [], [cases]);

  if (error) return <ErrorNotice error={error} />;
  if (!cases) return <SkeletonTable rows={6} cols={5} />;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
        <span className="text-ink">
          <span className="font-medium tabular-nums">{cases.length}</span> cases
        </span>
        <span className="text-hairline-strong">·</span>
        <span className="text-body">
          <span className="font-medium tabular-nums">{synthetic.length}</span> [synthetic]
        </span>
        <span className="text-hairline-strong">·</span>
        <span className="text-approve">
          <span className="font-medium tabular-nums">{promoted.length}</span> promoted from adjudication
        </span>
      </div>

      {cases.length === 0 ? (
        <p className="rounded-lg bg-canvas-soft px-5 py-8 text-center text-sm text-mute shadow-[var(--shadow-1)]">
          No golden cases yet. Seed corpora populate this on first run; escalation resolutions can promote more.
        </p>
      ) : (
        <TableSurface>
          <table className="table-ledger">
            <thead>
              <tr>
                <th>case id</th>
                <th>workflow</th>
                <th>expected</th>
                <th>provenance</th>
                <th>label</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.case_id}>
                  <td className="font-mono text-xs text-ink">{c.case_id}</td>
                  <td className="font-mono text-xs text-body">{c.workflow}</td>
                  <td>
                    <OutcomeBadge kind={c.expected.kind} />
                  </td>
                  <td className="max-w-[220px] truncate text-xs text-mute" title={c.provenance}>{c.provenance}</td>
                  <td className="text-xs">
                    {c.synthetic ? (
                      <span className="rounded-full bg-canvas-soft px-2 py-0.5 text-[11px] text-body shadow-[var(--shadow-1)]">[synthetic]</span>
                    ) : (
                      <span className="text-approve">real</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableSurface>
      )}
    </div>
  );
}
