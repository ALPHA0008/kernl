"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import { TraceView } from "@/components/trace/TraceView";
import { BackLink } from "@/components/ui/BackLink";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { HashChip } from "@/components/ui/HashChip";
import { OutcomeBadge } from "@/components/ui/OutcomeBadge";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { evaluate, getActiveBundle, getDecision, listBundles, listEscalations, runReplay } from "@/lib/api";
import { useSession } from "@/lib/auth";
import { fmtDate, newIdempotencyKey } from "@/lib/format";
import type { ActiveBundle, BundleSummary, DecisionEvent } from "@/lib/types";
import { isAdjudicationTrace } from "@/lib/types";

export default function DecisionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { apiKey, principal } = useSession();
  const router = useRouter();
  const isOwner = principal.role === "owner";

  const [event, setEvent] = useState<DecisionEvent | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [escalationId, setEscalationId] = useState<string | null>(null);
  const [activeHash, setActiveHash] = useState<string | null>(null);
  const [activeBundle, setActiveBundle] = useState<ActiveBundle | null>(null);
  const [reeval, setReeval] = useState<{ same: boolean } | null>(null);
  const [reevalBusy, setReevalBusy] = useState(false);
  const [reevalError, setReevalError] = useState<unknown>(null);

  const [drafts, setDrafts] = useState<BundleSummary[] | null>(null);
  const [replayPickerOpen, setReplayPickerOpen] = useState(false);
  const [replayBusy, setReplayBusy] = useState(false);
  const [replayError, setReplayError] = useState<unknown>(null);

  useEffect(() => {
    getDecision(apiKey, id).then(setEvent).catch(setError);
    listEscalations(apiKey)
      .then(({ escalations }) => {
        const esc = escalations.find((e) => e.decision_event_id === id);
        if (esc) setEscalationId(esc.escalation_id);
      })
      .catch(() => {});
    getActiveBundle(apiKey)
      .then((a) => {
        setActiveHash(a.content_hash);
        setActiveBundle(a);
      })
      .catch(() => {});
    if (isOwner) {
      listBundles(apiKey)
        .then(({ bundles }) => setDrafts(bundles.filter((b) => b.status === "draft")))
        .catch(() => {});
    }
  }, [apiKey, id, isOwner]);

  async function replayAgainstDraft(recordId: string) {
    setReplayBusy(true);
    setReplayError(null);
    try {
      const run = await runReplay(apiKey, { candidate_record_id: recordId, include_reference: true });
      router.push(`/replays/${run.run_id}`);
    } catch (err) {
      setReplayError(err);
    } finally {
      setReplayBusy(false);
    }
  }

  async function reEvaluate() {
    if (!event) return;
    setReevalBusy(true);
    setReevalError(null);
    try {
      const res = await evaluate(apiKey, {
        workflow: event.workflow,
        facts: event.facts,
        idempotency_key: newIdempotencyKey("reeval"),
      });
      setReeval({ same: JSON.stringify(res.outcome) === JSON.stringify(event.outcome) });
    } catch (err) {
      setReevalError(err);
    } finally {
      setReevalBusy(false);
    }
  }

  if (error) {
    return (
      <>
        <BackLink href="/ledger" label="Back to Ledger" />
        <PageHeader title="Decision" />
        <ErrorNotice error={error} />
      </>
    );
  }
  if (!event) {
    return (
      <>
        <BackLink href="/ledger" label="Back to Ledger" />
        <Skeleton className="mb-4 h-8 w-64" />
        <Skeleton className="mb-4 h-28" />
        <Skeleton className="h-64" />
      </>
    );
  }

  const sameBundleActive = activeHash !== null && activeHash === event.bundle_hash;
  const isAdjudication = isAdjudicationTrace(event.trace);

  return (
    <>
      <BackLink href="/ledger" label="Back to Ledger" />
      <PageHeader
        eyebrow={isAdjudication ? "Adjudication" : "Decision"}
        title={isAdjudication ? "Adjudication receipt" : "Decision receipt"}
        subtitle={`${event.workflow} · ${fmtDate(event.created_at)}`}
      >
        <OutcomeBadge kind={event.outcome.kind} size="lg" />
      </PageHeader>

      <Card elevation={2} className="mb-4">
        <CardBody>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm lg:grid-cols-3">
            <Field label="event id" value={<span className="font-mono text-xs break-all">{event.event_id}</span>} />
            <Field label="actor" value={<span className="font-mono text-xs">{event.actor.type}:{event.actor.id}</span>} />
            <Field label="idempotency key" value={<span className="font-mono text-xs break-all">{event.idempotency_key}</span>} />
            <Field
              label="bundle"
              value={
                <span className="flex items-center gap-2">
                  <HashChip hash={event.bundle_hash} />
                  {activeHash !== null && !sameBundleActive ? (
                    <span className="text-[11px] text-escalate">not current</span>
                  ) : null}
                </span>
              }
            />
            <Field label="event hash" value={<HashChip hash={event.event_hash} />} />
            <Field label="previous event" value={<HashChip hash={event.prev_event_hash} />} />
            {event.outcome.action ? (
              <Field label="action" value={<span className="font-mono text-xs">{event.outcome.action}</span>} />
            ) : null}
            {event.outcome.policy_id ? (
              <Field label="winning policy" value={<span className="font-mono text-xs">{event.outcome.policy_id}</span>} />
            ) : null}
            {event.linked_event_id ? (
              <Field
                label="adjudicates"
                value={
                  <Link href={`/decisions/${event.linked_event_id}`} className="font-mono text-xs text-link underline underline-offset-2">
                    {event.linked_event_id.slice(0, 13)}…
                  </Link>
                }
              />
            ) : null}
          </dl>
        </CardBody>
        <div className="flex flex-wrap items-center gap-2.5 border-t border-hairline px-5 py-3.5">
          {escalationId ? (
            <Link href={`/escalations/${escalationId}`}>
              <Button variant="secondary" size="sm">View escalation</Button>
            </Link>
          ) : null}
          {/* Re-evaluate / replay operate on a decision's facts+bundle. An
              adjudication is a human ruling with no derivation to re-run, so
              these actions don't apply to it. */}
          {!isAdjudication ? (
            <>
              <Button
                variant="ghost"
                size="sm"
                loading={reevalBusy}
                onClick={() => void reEvaluate()}
                title="Re-submit these exact facts against the CURRENT active bundle"
              >
                Re-evaluate now
              </Button>
              {reeval ? (
                <span className={`text-xs font-medium ${reeval.same ? "text-approve" : "text-escalate"}`}>
                  {reeval.same
                    ? "✓ identical under active bundle"
                    : sameBundleActive
                      ? "✗ outcome differs on same bundle — report this"
                      : "outcome differs — active bundle changed since this decision"}
                </span>
              ) : null}
              {reevalError ? <ErrorNotice error={reevalError} /> : null}

              {isOwner && drafts && drafts.length > 0 ? (
                <div className="relative">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setReplayPickerOpen((v) => !v)}
                    title="Run the golden-set replay against a candidate draft bundle"
                  >
                    Replay against draft…
                  </Button>
                  {replayPickerOpen ? (
                    <div className="menu-enter absolute left-0 top-full z-10 mt-1.5 w-72 rounded-md bg-canvas p-1.5 shadow-[var(--shadow-4)]" style={{ ["--menu-origin" as string]: "top left" }}>
                      {drafts.map((d) => (
                        <button
                          key={d.record_id}
                          type="button"
                          disabled={replayBusy}
                          onClick={() => void replayAgainstDraft(d.record_id)}
                          className="flex w-full items-center justify-between gap-2 rounded-md px-2.5 py-2 text-left text-xs hover:bg-canvas-soft disabled:opacity-50"
                        >
                          <span className="font-mono text-ink">{d.content_hash.slice(0, 16)}…</span>
                          <span className="tabular-nums text-mute">{d.policy_count} policies</span>
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
              {replayError ? <ErrorNotice error={replayError} /> : null}
            </>
          ) : null}
        </div>
      </Card>

      {isAdjudicationTrace(event.trace) ? (
        <AdjudicationReceipt event={event} trace={event.trace} />
      ) : (
        <TraceView
          trace={event.trace}
          policies={sameBundleActive ? activeBundle?.bundle.policies : undefined}
        />
      )}
    </>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="t-eyebrow mb-1">{label}</dt>
      <dd className="text-ink">{value}</dd>
    </div>
  );
}

/** An adjudication is a human ruling on an escalation — not a machine
 *  derivation. It has no facts/policies/precedence of its own; its "why" is
 *  the adjudicator's rationale, and the full derivation lives on the original
 *  decision it resolves. This view shows the ruling and routes to that trace,
 *  rather than trying to render a decision-shaped trace it doesn't have. */
function AdjudicationReceipt({
  event,
  trace,
}: {
  event: DecisionEvent;
  trace: import("@/lib/types").AdjudicationTrace;
}) {
  const rationale = event.outcome.rationale;
  return (
    <Card elevation={2}>
      <CardBody>
        <div className="mb-5 flex items-center gap-2.5">
          <span className="t-eyebrow">human ruling</span>
          <span className="font-mono text-xs text-mute">
            {event.actor.type}:{event.actor.id}
          </span>
        </div>

        <dl className="mb-5 grid grid-cols-2 gap-x-8 gap-y-3 text-sm">
          <Field label="outcome" value={<OutcomeBadge kind={event.outcome.kind} />} />
          {event.outcome.action ? (
            <Field label="chosen action" value={<span className="font-mono text-xs text-ink">{event.outcome.action}</span>} />
          ) : null}
        </dl>

        <div className="mb-5">
          <div className="t-eyebrow mb-1.5">rationale</div>
          {rationale ? (
            <p className="rounded-md border-l-2 border-ink bg-canvas-soft px-3.5 py-2.5 text-sm italic text-ink">
              &ldquo;{rationale}&rdquo;
            </p>
          ) : (
            <p className="text-xs text-mute">no rationale recorded</p>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 rounded-md bg-canvas-soft px-4 py-3">
          <div>
            <div className="t-eyebrow mb-0.5">resolves decision</div>
            <span className="font-mono text-xs text-mute">{trace.original_event_id.slice(0, 20)}…</span>
          </div>
          <Link href={`/decisions/${trace.original_event_id}`}>
            <Button variant="secondary" size="sm">View original derivation →</Button>
          </Link>
        </div>
      </CardBody>
    </Card>
  );
}
