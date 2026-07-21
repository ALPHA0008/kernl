"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { BundleDiffView } from "@/components/policy/BundleDiffView";
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
  getBundleDiff,
  getReplay,
  listBundles,
  listOnboardingDrafts,
  publishBundle,
  runReplay,
  saveOnboardingDraft,
} from "@/lib/api";
import { useSession } from "@/lib/auth";
import { fmtDate } from "@/lib/format";
import type { ActiveBundle, BundleDiffResponse, BundleSummary, OnboardingDraft, ReplayRun } from "@/lib/types";

const BLANK_POLICY = {
  id: "",
  workflow: "",
  effect: { kind: "approve" as const, action: "" },
  priority: 50,
  conditions: [],
  authority: { approval_required: false, approver_role: null },
  evidence: [],
  overrides: [],
  unconditional_ack: false,
  rationale: "",
};

type Tab = "published" | "registry";

export default function PoliciesPage() {
  const { apiKey, principal } = useSession();
  const { toast } = useToast();
  const router = useRouter();
  const isOwner = principal.role === "owner";

  const [tab, setTab] = useState<Tab>("published");
  const [active, setActive] = useState<ActiveBundle | null>(null);
  const [bundles, setBundles] = useState<BundleSummary[] | null>(null);
  const [openDrafts, setOpenDrafts] = useState<OnboardingDraft[] | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [authoring, setAuthoring] = useState(false);

  const [flowRecord, setFlowRecord] = useState<string | null>(null);
  const [run, setRun] = useState<ReplayRun | null>(null);
  const [flowBusy, setFlowBusy] = useState(false);
  const [flowError, setFlowError] = useState<unknown>(null);

  const [diffRecord, setDiffRecord] = useState<string | null>(null);
  const [diff, setDiff] = useState<BundleDiffResponse | null>(null);
  const [diffBusy, setDiffBusy] = useState(false);
  const [diffError, setDiffError] = useState<unknown>(null);

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
    if (isOwner) {
      listOnboardingDrafts(apiKey)
        .then(({ drafts }) => setOpenDrafts(drafts.filter((d) => d.status !== "rejected")))
        .catch(() => {});
    }
  }, [apiKey, isOwner]);

  useEffect(reload, [reload]);

  async function draftNewPolicy() {
    setAuthoring(true);
    setLoadError(null);
    try {
      const d = await saveOnboardingDraft(apiKey, BLANK_POLICY);
      router.push(`/onboarding/drafts/${d.draft_id}`);
    } catch (err) {
      setLoadError(err);
      setAuthoring(false);
    }
  }

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

  async function viewDiff(recordId: string) {
    setDiffRecord(recordId);
    setDiff(null);
    setDiffError(null);
    setDiffBusy(true);
    try {
      setDiff(await getBundleDiff(apiKey, recordId));
    } catch (err) {
      setDiffError(err);
    } finally {
      setDiffBusy(false);
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
        <span className="flex items-center gap-3">
          {active ? (
            <span className="flex items-center gap-2">
              <span className="t-eyebrow">active</span>
              <HashChip hash={active.content_hash} />
            </span>
          ) : null}
          {isOwner ? (
            <Button size="sm" loading={authoring} onClick={() => void draftNewPolicy()}>
              Draft a new policy
            </Button>
          ) : null}
        </span>
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

          {isOwner && openDrafts && openDrafts.length > 0 ? (
            <div>
              <h3 className="t-eyebrow mb-2">Open drafts · not yet in a registered bundle</h3>
              <div className="space-y-1.5">
                {openDrafts.map((d) => (
                  <Link
                    key={d.draft_id}
                    href={`/onboarding/drafts/${d.draft_id}`}
                    className="flex items-center justify-between gap-3 rounded-lg bg-canvas px-4 py-2.5 shadow-[var(--shadow-1)] transition-colors hover:bg-canvas-soft"
                  >
                    <span className="min-w-0 flex-1 truncate font-mono text-xs text-ink">
                      {d.proposed_json.id || "(untitled policy)"}
                    </span>
                    <span className="shrink-0 text-xs text-mute">{d.proposed_json.workflow || "—"}</span>
                    <StatusPill status={d.status === "accepted" ? "resolved" : "open"} />
                    <span className={`shrink-0 text-xs font-medium ${d.publishable ? "text-approve" : "text-escalate"}`}>
                      {d.publishable ? "grounded" : "needs citation"}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
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
                          <span className="inline-flex items-center gap-3">
                            {!isActive ? (
                              <button type="button" onClick={() => void viewDiff(b.record_id)} className="text-xs font-medium text-link hover:underline">Diff vs active</button>
                            ) : null}
                            {isOwner && b.status === "draft" ? (
                              <button type="button" onClick={() => startReplay(b.record_id)} className="text-xs font-medium text-link hover:underline">Replay &amp; publish →</button>
                            ) : isOwner && b.status !== "draft" && !isActive ? (
                              <button type="button" onClick={() => void activate(b.record_id)} className="text-xs font-medium text-link hover:underline">Activate (rollback)</button>
                            ) : isActive ? (
                              <span className="text-xs text-mute">live</span>
                            ) : null}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </TableSurface>
          )}

          {diffRecord ? (
            <Card elevation={3} className="page-enter">
              <CardHeader
                eyebrow="Policy diff"
                action={
                  <button type="button" onClick={() => { setDiffRecord(null); setDiff(null); setDiffError(null); }} className="text-xs text-mute hover:text-ink">close</button>
                }
              />
              <CardBody>
                {diffBusy && !diff ? <Loading label="Computing diff…" /> : null}
                {diffError ? <div className="mb-4"><ErrorNotice error={diffError} /></div> : null}
                {diff ? (
                  <BundleDiffView diff={diff.diff} baselineRecordId={diff.baseline_record_id} />
                ) : null}
              </CardBody>
            </Card>
          ) : null}

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
