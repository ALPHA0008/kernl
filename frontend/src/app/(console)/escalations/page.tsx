"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { PageHeader } from "@/components/ui/PageHeader";
import { ReasonChip } from "@/components/ui/ReasonChip";
import { SkeletonTable } from "@/components/ui/Skeleton";
import { StatusPill } from "@/components/ui/StatusPill";
import { Tabs } from "@/components/ui/Tabs";
import { TableSurface } from "@/components/ui/Toolbar";
import { listEscalations } from "@/lib/api";
import { useSession } from "@/lib/auth";
import { fmtDate, timeAgo } from "@/lib/format";
import type { Escalation } from "@/lib/types";

/** For missing-facts escalations the deficient fields live in `detail` — surface
 *  them in the row so an adjudicator knows WHAT was missing without opening each
 *  one. Values are joined; keys are shown when values are empty/flags. */
function missingSummary(e: Escalation): string | null {
  if (e.reason !== "missing_facts") return null;
  const keys = Object.keys(e.detail ?? {});
  if (keys.length === 0) return null;
  const flat = keys.map((k) => {
    const v = e.detail[k];
    return Array.isArray(v) ? v.join(", ") : v == null || v === "" ? k : String(v);
  });
  return flat.join(" · ");
}

export default function EscalationsPage() {
  const { apiKey } = useSession();
  const router = useRouter();
  const [tab, setTab] = useState<string>("open");
  const [rows, setRows] = useState<Escalation[] | null>(null);
  const [counts, setCounts] = useState<{ open: number; resolved: number } | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let live = true;
    listEscalations(apiKey, tab || undefined)
      .then(({ escalations }) => live && (setRows(escalations), setError(null)))
      .catch((e) => live && (setError(e), setRows([])));
    return () => { live = false; };
  }, [apiKey, tab]);

  // Load open/resolved counts once for the tab badges + queue summary.
  useEffect(() => {
    let live = true;
    Promise.all([
      listEscalations(apiKey, "open").then((r) => r.escalations.length).catch(() => 0),
      listEscalations(apiKey, "resolved").then((r) => r.escalations.length).catch(() => 0),
    ]).then(([open, resolved]) => live && setCounts({ open, resolved }));
    return () => { live = false; };
  }, [apiKey, rows]);

  const isOpenView = tab === "open";

  // Oldest open escalation drives an at-a-glance urgency line.
  const oldestOpenAge = useMemo(() => {
    if (!rows || !isOpenView || rows.length === 0) return null;
    const oldest = rows.reduce((a, b) => (a.created_at < b.created_at ? a : b));
    return timeAgo(oldest.created_at);
  }, [rows, isOpenView]);

  const tabs = [
    { value: "open", label: counts ? `Open · ${counts.open}` : "Open" },
    { value: "resolved", label: counts ? `Resolved · ${counts.resolved}` : "Resolved" },
    { value: "", label: "All" },
  ];

  return (
    <>
      <PageHeader eyebrow="Operate" title="Escalations" subtitle="Where ambiguity becomes precedent. Resolutions are ledgered adjudications.">
        {counts && counts.open > 0 ? (
          <span className="flex items-center gap-2 rounded-full bg-escalate-bg px-3 py-1.5 text-xs font-medium text-escalate">
            <span className="h-1.5 w-1.5 rounded-full bg-escalate" />
            {counts.open} awaiting adjudication{oldestOpenAge ? ` · oldest ${oldestOpenAge}` : ""}
          </span>
        ) : null}
      </PageHeader>

      <Tabs tabs={tabs} value={tab} onChange={setTab} />

      {error ? <ErrorNotice error={error} /> : null}
      {!rows && !error ? <SkeletonTable rows={5} cols={6} /> : null}

      {rows ? (
        rows.length === 0 ? (
          <EmptyState
            title={isOpenView ? "Inbox zero" : "Nothing here"}
            hint={isOpenView ? "Escalations appear when the evaluator refuses to guess: missing facts, conflicts, or required authority." : undefined}
          />
        ) : (
          <TableSurface>
            <table className="table-ledger">
              <thead>
                <tr>
                  <th>opened</th>
                  <th>age</th>
                  <th>workflow</th>
                  <th>reason</th>
                  <th>detail</th>
                  {!isOpenView ? <th>resolution</th> : null}
                  <th className="text-right"></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((e) => {
                  const missing = missingSummary(e);
                  return (
                    <tr
                      key={e.escalation_id}
                      onClick={() => router.push(`/escalations/${e.escalation_id}`)}
                      className="cursor-pointer"
                    >
                      <td className="whitespace-nowrap text-xs text-body">{fmtDate(e.created_at)}</td>
                      <td className="whitespace-nowrap text-xs text-mute">{timeAgo(e.created_at)}</td>
                      <td className="font-mono text-xs text-ink">{e.workflow}</td>
                      <td><ReasonChip reason={e.reason} /></td>
                      <td className="max-w-52 truncate font-mono text-xs text-mute" title={missing ?? ""}>
                        {missing ?? "—"}
                      </td>
                      {!isOpenView ? (
                        <td className="max-w-52 truncate font-mono text-xs text-body" title={e.resolution?.chosen_action ?? ""}>
                          {e.resolution ? `${e.resolution.outcome_kind}: ${e.resolution.chosen_action}` : (
                            <StatusPill status={e.status} />
                          )}
                        </td>
                      ) : null}
                      <td className="whitespace-nowrap text-right">
                        <span className="text-xs font-medium text-link">
                          {e.status === "open" ? "Adjudicate →" : "View →"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </TableSurface>
        )
      ) : null}
    </>
  );
}
