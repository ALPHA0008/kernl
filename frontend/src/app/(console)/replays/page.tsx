"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { GoldenCasesPanel } from "@/components/replay/GoldenCasesPanel";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { HashChip } from "@/components/ui/HashChip";
import { PageHeader } from "@/components/ui/PageHeader";
import { SkeletonTable } from "@/components/ui/Skeleton";
import { Tabs } from "@/components/ui/Tabs";
import { TableSurface } from "@/components/ui/Toolbar";
import { listReplays } from "@/lib/api";
import { useSession } from "@/lib/auth";
import { fmtDate } from "@/lib/format";
import type { ReplayRunSummary } from "@/lib/types";

function verdict(s: ReplayRunSummary["summary"]): { text: string; pill: string } {
  if (s.errors > 0) return { text: "errors", pill: "bg-deny-bg text-deny" };
  if (s.golden_failed > 0) return { text: `${s.golden_failed} golden fail`, pill: "bg-deny-bg text-deny" };
  if (s.flips > 0) return { text: `${s.flips} flip${s.flips > 1 ? "s" : ""}`, pill: "bg-escalate-bg text-escalate" };
  return { text: "clean", pill: "bg-approve-bg text-approve" };
}

type Tab = "runs" | "cases";

export default function ReplaysPage() {
  const { apiKey } = useSession();
  const [tab, setTab] = useState<Tab>("runs");
  const [runs, setRuns] = useState<ReplayRunSummary[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    listReplays(apiKey)
      .then(({ runs }) => setRuns([...runs].sort((a, b) => b.created_at.localeCompare(a.created_at))))
      .catch(setError);
  }, [apiKey]);

  return (
    <>
      <PageHeader eyebrow="Govern" title="Replay" subtitle="CI for policy. Every publish is gated on an acknowledged run for that exact draft." />

      <Tabs
        tabs={[
          { value: "runs", label: "Runs" },
          { value: "cases", label: "Golden cases" },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "cases" ? <GoldenCasesPanel /> : null}

      {tab === "runs" ? (
        <>
          {error ? <ErrorNotice error={error} /> : null}
          {!runs && !error ? <SkeletonTable rows={5} cols={6} /> : null}

          {runs ? (
            runs.length === 0 ? (
              <EmptyState title="No replay runs yet" hint="Create a draft in Policies or Onboarding, then run replay from its publish flow — the report lands here." />
            ) : (
              <TableSurface>
                <table className="table-ledger">
                  <thead><tr><th>ran</th><th>candidate</th><th>cases</th><th>verdict</th><th>acknowledged</th><th className="text-right"></th></tr></thead>
                  <tbody>
                    {runs.map((r) => {
                      const v = verdict(r.summary);
                      return (
                        <tr key={r.run_id}>
                          <td className="whitespace-nowrap text-xs text-body">{fmtDate(r.created_at)}</td>
                          <td><HashChip hash={r.candidate_bundle_hash} chars={10} /></td>
                          <td className="text-xs tabular-nums text-ink">{r.summary.total}</td>
                          <td><span className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${v.pill}`}>{v.text}</span></td>
                          <td className="text-xs">{r.acknowledged_by ? <span className="text-approve">{r.acknowledged_by}</span> : <span className="text-mute">pending</span>}</td>
                          <td className="text-right"><Link href={`/replays/${r.run_id}`} className="text-xs font-medium text-link hover:underline">View report →</Link></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </TableSurface>
            )
          ) : null}
        </>
      ) : null}
    </>
  );
}
