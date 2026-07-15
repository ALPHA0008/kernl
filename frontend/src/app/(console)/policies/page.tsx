"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PublishedBundle } from "@/components/policy/PublishedBundle";
import { ReplayReport } from "@/components/replay/ReplayReport";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { HashChip } from "@/components/ui/HashChip";
import { Loading } from "@/components/ui/Loading";
import { PageHeader } from "@/components/ui/PageHeader";
import { SkeletonCards, SkeletonTable } from "@/components/ui/Skeleton";
import { StatusPill } from "@/components/ui/StatusPill";
import { Tabs } from "@/components/ui/Tabs";
import { TableSurface } from "@/components/ui/Toolbar";
import { useToast } from "@/components/ui/Toast";
import {
  acknowledgeReplay,
  activateBundle,
  getActiveBundle,
  getReplay,
  listBundles,
  publishBundle,
  runReplay,
} from "@/lib/api";
import { useSession } from "@/lib/auth";
import { fmtDate } from "@/lib/format";
import type { ActiveBundle, BundleSummary, ReplayRun } from "@/lib/types";

type Tab = "published" | "registry";

export default function PoliciesPage() {
  const { apiKey, principal } = useSession();
  const { toast } = useToast();
  const isOwner = principal.role === "owner";

  const [tab, setTab] = useState<Tab>("published");
  const [active, setActive] = useState<ActiveBundle | null>(null);
  const [bundles, setBundles] = useState<BundleSummary[] | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<unknown>(null);

  const [flowRecord, setFlowRecord] = useState<string | null>(null);
  const [run, setRun] = useState<ReplayRun | null>(null);
  const [flowBusy, setFlowBusy] = useState(false);
  const [flowError, setFlowError] = useState<unknown>(null);

  const reload = useCallback(() => {
    getActiveBundle(apiKey)
      .then(setActive)
      .catch((e) => {
        setActive(null);
        if (!(e?.status === 404)) setLoadError(e);
      });
    listBundles(apiKey)
      .then(({ bundles }) => setBundles([...bundles].sort((a, b) => b.created_at.localeCompare(a.created_at))))
      .catch(setLoadError)
      .finally(() => setLoaded(true));
  }, [apiKey]);

  useEffect(reload, [reload]);

  async function startReplay(recordId: string) {
    setFlowRecord(recordId);
    setRun(null);
    setFlowError(null);
    setFlowBusy(true);
    try {
      setRun(await runReplay(apiKey, { candidate_record_id: recordId, include_reference: true }));
    } catch (err) {
      setFlowError(err);
    } finally {
      setFlowBusy(false);
    }
  }

  async function ackAndPublish() {
    if (!run || !flowRecord) return;
    setFlowBusy(true);
    setFlowError(null);
    try {
      if (!run.acknowledged_by) {
        await acknowledgeReplay(apiKey, run.run_id);
        setRun(await getReplay(apiKey, run.run_id));
      }
      await publishBundle(apiKey, flowRecord);
      toast("Published — the active bundle now points to this content.", "success");
      setFlowRecord(null);
      setRun(null);
      reload();
    } catch (err) {
      setFlowError(err);
    } finally {
      setFlowBusy(false);
    }
  }

  async function activate(recordId: string) {
    setLoadError(null);
    try {
      await activateBundle(apiKey, recordId);
      toast("Active pointer moved — rollback is a pointer move, no history rewritten.", "success");
      reload();
    } catch (err) {
      setLoadError(err);
    }
  }

  if (loadError && !bundles) {
    return (
      <>
        <PageHeader eyebrow="Govern" title="Policy Workbench" />
        <ErrorNotice error={loadError} />
      </>
    );
  }

  return (
    <>
      <PageHeader eyebrow="Govern" title="Policy Workbench" subtitle="The compiled constitution. Published policies are cited, versioned, replay-gated.">
        {active ? (
          <span className="flex items-center gap-2">
            <span className="t-eyebrow">active</span>
            <HashChip hash={active.content_hash} />
          </span>
        ) : null}
      </PageHeader>

      {loadError ? <div className="mb-4"><ErrorNotice error={loadError} /></div> : null}

      <Tabs
        tabs={[
          { value: "published", label: "Published bundle" },
          { value: "registry", label: "Registry & publish" },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "published" ? (
        !loaded ? (
          <SkeletonCards count={5} />
        ) : !active ? (
          <EmptyState
            title="No published bundle"
            hint={isOwner ? "Register a draft and publish it from the Registry tab, or build one in Onboarding." : "An owner must publish a bundle before decisions can run."}
            action={isOwner ? <Link href="/onboarding"><Button>Go to Onboarding</Button></Link> : undefined}
          />
        ) : (
          <PublishedBundle policies={active.bundle.policies} workflowCount={active.bundle.workflows.length} />
        )
      ) : null}

      {tab === "registry" ? (
        <div className="space-y-6">
          {!isOwner ? (
            <p className="rounded-md bg-canvas-soft px-3.5 py-2.5 text-sm text-body shadow-[var(--shadow-1)]">
              Registry is read-only for your role. Publishing and rollback require owner.
            </p>
          ) : null}

          {!loaded ? (
            <SkeletonTable rows={4} cols={6} />
          ) : !bundles || bundles.length === 0 ? (
            <EmptyState title="No bundles registered" />
          ) : (
            <TableSurface>
              <table className="table-ledger">
                <thead><tr><th>created</th><th>content hash</th><th>status</th><th>policies</th><th>published</th><th className="text-right"></th></tr></thead>
                <tbody>
                  {bundles.map((b) => {
                    const isActive = active?.content_hash === b.content_hash;
                    return (
                      <tr key={b.record_id}>
                        <td className="whitespace-nowrap text-xs text-body">{fmtDate(b.created_at)}</td>
                        <td><HashChip hash={b.content_hash} chars={12} /></td>
                        <td><StatusPill status={isActive ? "active" : b.status} /></td>
                        <td className="text-xs tabular-nums text-ink">{b.policy_count}</td>
                        <td className="whitespace-nowrap text-xs text-mute">{b.published_at ? fmtDate(b.published_at) : "—"}</td>
                        <td className="whitespace-nowrap text-right">
                          {isOwner && b.status === "draft" ? (
                            <button type="button" onClick={() => startReplay(b.record_id)} className="text-xs font-medium text-link hover:underline">Replay &amp; publish →</button>
                          ) : isOwner && b.status !== "draft" && !isActive ? (
                            <button type="button" onClick={() => void activate(b.record_id)} className="text-xs font-medium text-link hover:underline">Activate (rollback)</button>
                          ) : isActive ? (
                            <span className="text-xs text-mute">live</span>
                          ) : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </TableSurface>
          )}

          {flowRecord ? (
            <Card elevation={3} className="page-enter">
              <CardHeader
                eyebrow="Publish flow"
                action={
                  <button type="button" onClick={() => { setFlowRecord(null); setRun(null); setFlowError(null); }} className="text-xs text-mute hover:text-ink">close</button>
                }
              />
              <CardBody>
                {flowBusy && !run ? <Loading label="Running replay…" /> : null}
                {flowError ? <div className="mb-4"><ErrorNotice error={flowError} /></div> : null}
                {run ? (
                  <>
                    <ReplayReport run={run} />
                    <div className="mt-4 flex items-center gap-3">
                      <Button loading={flowBusy} onClick={() => void ackAndPublish()}>
                        {run.acknowledged_by ? "Publish" : "Acknowledge & publish"}
                      </Button>
                      <Link href={`/replays/${run.run_id}`} className="text-xs text-link underline underline-offset-2">open full report</Link>
                    </div>
                    {run.summary.golden_failed > 0 ? (
                      <p className="mt-2 text-xs text-escalate">
                        This draft fails {run.summary.golden_failed} golden case{run.summary.golden_failed > 1 ? "s" : ""}. Acknowledging means you accept that blast radius on the record.
                      </p>
                    ) : null}
                  </>
                ) : null}
              </CardBody>
            </Card>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
