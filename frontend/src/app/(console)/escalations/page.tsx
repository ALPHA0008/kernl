"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
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

const TABS = [
  { value: "open", label: "Open" },
  { value: "resolved", label: "Resolved" },
  { value: "", label: "All" },
] as const;

export default function EscalationsPage() {
  const { apiKey } = useSession();
  const [tab, setTab] = useState<string>("open");
  const [rows, setRows] = useState<Escalation[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let live = true;
    listEscalations(apiKey, tab || undefined)
      .then(({ escalations }) => live && (setRows(escalations), setError(null)))
      .catch((e) => live && (setError(e), setRows([])));
    return () => { live = false; };
  }, [apiKey, tab]);

  return (
    <>
      <PageHeader eyebrow="Operate" title="Escalations" subtitle="Where ambiguity becomes precedent. Resolutions are ledgered adjudications." />

      <Tabs tabs={TABS.map((t) => ({ value: t.value, label: t.label }))} value={tab} onChange={setTab} />

      {error ? <ErrorNotice error={error} /> : null}
      {!rows && !error ? <SkeletonTable rows={5} cols={6} /> : null}

      {rows ? (
        rows.length === 0 ? (
          <EmptyState
            title={tab === "open" ? "Inbox zero" : "Nothing here"}
            hint={tab === "open" ? "Escalations appear when the evaluator refuses to guess: missing facts, conflicts, or required authority." : undefined}
          />
        ) : (
          <TableSurface>
            <table className="table-ledger">
              <thead>
                <tr><th>opened</th><th>age</th><th>workflow</th><th>reason</th><th>status</th><th>resolution</th><th className="text-right"></th></tr>
              </thead>
              <tbody>
                {rows.map((e) => (
                  <tr key={e.escalation_id}>
                    <td className="whitespace-nowrap text-xs text-body">{fmtDate(e.created_at)}</td>
                    <td className="whitespace-nowrap text-xs text-mute">{timeAgo(e.created_at)}</td>
                    <td className="font-mono text-xs text-ink">{e.workflow}</td>
                    <td><ReasonChip reason={e.reason} /></td>
                    <td><StatusPill status={e.status} /></td>
                    <td className="max-w-52 truncate font-mono text-xs text-body" title={e.resolution?.chosen_action ?? ""}>
                      {e.resolution ? `${e.resolution.outcome_kind}: ${e.resolution.chosen_action}` : "—"}
                    </td>
                    <td className="text-right">
                      <Link href={`/escalations/${e.escalation_id}`} className="text-xs font-medium text-link hover:underline">
                        {e.status === "open" ? "Adjudicate →" : "View"}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableSurface>
        )
      ) : null}
    </>
  );
}
