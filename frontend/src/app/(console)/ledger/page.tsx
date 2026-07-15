"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { HashChip } from "@/components/ui/HashChip";
import { Select } from "@/components/ui/Input";
import { OutcomeBadge } from "@/components/ui/OutcomeBadge";
import { PageHeader } from "@/components/ui/PageHeader";
import { SkeletonTable } from "@/components/ui/Skeleton";
import { TableSurface, Toolbar } from "@/components/ui/Toolbar";
import { getActiveBundle, listLedger, verifyLedger } from "@/lib/api";
import { useSession } from "@/lib/auth";
import { fmtDate, shortHash } from "@/lib/format";
import type { ChainVerify, DecisionEvent } from "@/lib/types";

const PAGE_SIZE = 50;
const OUTCOME_KINDS = ["approve", "deny", "route", "escalate"];

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function exportJson(events: DecisionEvent[]) {
  triggerDownload(
    new Blob([JSON.stringify(events, null, 2)], { type: "application/json" }),
    `kernl-ledger-${Date.now()}.json`,
  );
}

function exportCsv(events: DecisionEvent[]) {
  const esc = (v: unknown) => `"${String(v ?? "").replaceAll('"', '""')}"`;
  const rows = [
    ["event_id", "event_type", "created_at", "workflow", "outcome_kind", "action", "policy_id", "actor", "idempotency_key", "bundle_hash", "event_hash"].join(","),
    ...events.map((e) =>
      [e.event_id, e.event_type, e.created_at, e.workflow, e.outcome.kind, e.outcome.action, e.outcome.policy_id, `${e.actor.type}:${e.actor.id}`, e.idempotency_key, e.bundle_hash, e.event_hash].map(esc).join(","),
    ),
  ];
  triggerDownload(new Blob([rows.join("\n")], { type: "text/csv" }), `kernl-ledger-${Date.now()}.csv`);
}

export default function LedgerPage() {
  const { apiKey } = useSession();
  const [events, setEvents] = useState<DecisionEvent[] | null>(null);
  const [verify, setVerify] = useState<ChainVerify | null>(null);
  const [workflows, setWorkflows] = useState<string[]>([]);
  const [error, setError] = useState<unknown>(null);

  const [workflow, setWorkflow] = useState("");
  const [outcome, setOutcome] = useState("");
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    let live = true;
    listLedger(apiKey, { workflow: workflow || undefined, outcome: outcome || undefined, limit: PAGE_SIZE, offset })
      .then(({ events }) => live && (setEvents(events), setError(null)))
      .catch((e) => live && (setError(e), setEvents([])));
    verifyLedger(apiKey).then((v) => live && setVerify(v)).catch(() => live && setVerify(null));
    return () => { live = false; };
  }, [apiKey, workflow, outcome, offset]);

  useEffect(() => {
    getActiveBundle(apiKey).then((a) => setWorkflows(a.bundle.workflows.map((w) => w.name))).catch(() => {});
  }, [apiKey]);

  return (
    <>
      <PageHeader eyebrow="Operate" title="Ledger" subtitle="Append-only institutional memory. Every ruling, hash-chained.">
        {verify ? (
          <span
            className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium ${
              verify.chain_valid ? "bg-approve-bg text-approve" : "bg-deny-bg text-deny"
            }`}
            title={verify.chain_head ?? undefined}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${verify.chain_valid ? "bg-approve" : "bg-deny"}`} />
            {verify.chain_valid ? "chain verified" : "CHAIN BROKEN"}
            {verify.chain_head ? <span className="font-mono opacity-70">{shortHash(verify.chain_head, 8)}</span> : null}
          </span>
        ) : null}
      </PageHeader>

      <Toolbar
        actions={
          <>
            <Button variant="secondary" size="sm" disabled={!events?.length} onClick={() => events && exportJson(events)}>Export JSON</Button>
            <Button variant="secondary" size="sm" disabled={!events?.length} onClick={() => events && exportCsv(events)}>Export CSV</Button>
          </>
        }
      >
        <Select value={workflow} onChange={(e) => { setWorkflow(e.target.value); setOffset(0); }} mono className="!h-8 w-auto min-w-[150px]" aria-label="Filter by workflow">
          <option value="">all workflows</option>
          {workflows.map((w) => <option key={w} value={w}>{w}</option>)}
        </Select>
        <Select value={outcome} onChange={(e) => { setOutcome(e.target.value); setOffset(0); }} mono className="!h-8 w-auto min-w-[130px]" aria-label="Filter by outcome">
          <option value="">all outcomes</option>
          {OUTCOME_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
        </Select>
      </Toolbar>

      {error ? <ErrorNotice error={error} /> : null}
      {!events && !error ? <SkeletonTable rows={8} cols={8} /> : null}

      {events ? (
        events.length === 0 ? (
          <EmptyState
            title={offset > 0 ? "No more events" : "No ledger events match"}
            hint={offset > 0 ? undefined : "Run a decision from Evaluate — every ruling lands here."}
          />
        ) : (
          <TableSurface>
            <table className="table-ledger">
              <thead>
                <tr>
                  <th>when</th><th>type</th><th>workflow</th><th>outcome</th><th>action</th><th>actor</th><th>bundle</th><th className="text-right">event</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.event_id}>
                    <td className="whitespace-nowrap text-xs text-body">{fmtDate(e.created_at)}</td>
                    <td className="text-xs">
                      {e.event_type === "adjudication" ? <span className="font-medium text-link">adjudication</span> : <span className="text-body">decision</span>}
                    </td>
                    <td className="font-mono text-xs text-ink">{e.workflow}</td>
                    <td><OutcomeBadge kind={e.outcome.kind} /></td>
                    <td className="max-w-48 truncate font-mono text-xs text-body" title={e.outcome.action ?? ""}>{e.outcome.action ?? "—"}</td>
                    <td className="font-mono text-xs text-body">{e.actor.type}:{e.actor.id}</td>
                    <td><HashChip hash={e.bundle_hash} chars={8} /></td>
                    <td className="text-right">
                      <Link href={`/decisions/${e.event_id}`} className="font-mono text-xs text-link hover:underline">{e.event_id.slice(0, 8)}…</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableSurface>
        )
      ) : null}

      {events && events.length > 0 ? (
        <div className="mt-4 flex items-center justify-between">
          <Button variant="ghost" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>← Newer</Button>
          <span className="text-xs text-mute">{offset + 1}–{offset + events.length}</span>
          <Button variant="ghost" size="sm" disabled={events.length < PAGE_SIZE} onClick={() => setOffset(offset + PAGE_SIZE)}>Older →</Button>
        </div>
      ) : null}
    </>
  );
}
