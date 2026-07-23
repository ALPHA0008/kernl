"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { TraceView } from "@/components/trace/TraceView";
import { BackLink } from "@/components/ui/BackLink";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { HashChip } from "@/components/ui/HashChip";
import { FieldLabel, Input, Select, Textarea } from "@/components/ui/Input";
import { Loading } from "@/components/ui/Loading";
import { OutcomeBadge } from "@/components/ui/OutcomeBadge";
import { PageHeader } from "@/components/ui/PageHeader";
import { ReasonChip } from "@/components/ui/ReasonChip";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusPill } from "@/components/ui/StatusPill";
import { useToast } from "@/components/ui/Toast";
import { getActiveBundle, getDecision, getEscalation, resolveEscalation } from "@/lib/api";
import { useSession } from "@/lib/auth";
import { fmtDate } from "@/lib/format";
import type { DecisionEvent, Escalation } from "@/lib/types";
import { isAdjudicationTrace } from "@/lib/types";

const OUTCOME_KINDS = ["approve", "deny", "route", "escalate"] as const;

export default function EscalationDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { apiKey, principal } = useSession();
  const { toast } = useToast();

  const [esc, setEsc] = useState<Escalation | null>(null);
  const [decision, setDecision] = useState<DecisionEvent | null>(null);
  const [candidates, setCandidates] = useState<string[]>([]);
  const [error, setError] = useState<unknown>(null);

  const [chosenAction, setChosenAction] = useState("");
  const [outcomeKind, setOutcomeKind] = useState<string>("approve");
  const [rationale, setRationale] = useState("");
  const [promote, setPromote] = useState(true);
  const [busy, setBusy] = useState(false);
  const [resolveError, setResolveError] = useState<unknown>(null);

  const canResolve = principal.role === "owner" || principal.role === "approver";

  useEffect(() => {
    getEscalation(apiKey, id)
      .then((e) => {
        setEsc(e);
        getActiveBundle(apiKey)
          .then((a) => {
            const actions = new Set<string>();
            for (const p of a.bundle.policies) {
              if (p.workflow === e.workflow && p.effect.action) actions.add(p.effect.action);
            }
            setCandidates([...actions].sort());
          })
          .catch(() => {});
        return getDecision(apiKey, e.decision_event_id);
      })
      .then(setDecision)
      .catch(setError);
  }, [apiKey, id]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!chosenAction.trim() || !rationale.trim() || busy) return;
    setBusy(true);
    setResolveError(null);
    try {
      const updated = await resolveEscalation(apiKey, id, {
        chosen_action: chosenAction.trim(),
        outcome_kind: outcomeKind,
        rationale: rationale.trim(),
        promote_to_golden: promote,
      });
      setEsc(updated);
      toast("Escalation resolved — adjudication ledgered.", "success");
    } catch (err) {
      setResolveError(err);
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    return (
      <>
        <BackLink href="/escalations" label="Back to Escalations" />
        <PageHeader title="Escalation" />
        <ErrorNotice error={error} />
      </>
    );
  }
  if (!esc) {
    return (
      <>
        <BackLink href="/escalations" label="Back to Escalations" />
        <Skeleton className="mb-4 h-8 w-64" />
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-96" />
          <Skeleton className="h-72" />
        </div>
      </>
    );
  }

  const resolved = esc.status === "resolved";

  return (
    <>
      <BackLink href="/escalations" label="Back to Escalations" />
      <PageHeader eyebrow="Adjudication" title="Escalation" subtitle={`${esc.workflow} · opened ${fmtDate(esc.created_at)}`}>
        <ReasonChip reason={esc.reason} />
        <StatusPill status={esc.status} />
      </PageHeader>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <div>
          <Card elevation={2} className="mb-4">
            <CardBody>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="t-eyebrow">originating decision</span>
                <Link href={`/decisions/${esc.decision_event_id}`} className="font-mono text-xs text-link underline underline-offset-2">
                  {esc.decision_event_id.slice(0, 13)}…
                </Link>
              </div>
              {Object.keys(esc.detail).length > 0 ? (
                <dl className="mt-3 space-y-1 text-sm">
                  {Object.entries(esc.detail).map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-4">
                      <dt className="text-mute">{k}</dt>
                      <dd className="font-mono text-xs text-ink">{Array.isArray(v) ? v.join(", ") : String(v)}</dd>
                    </div>
                  ))}
                </dl>
              ) : null}
            </CardBody>
          </Card>

          {decision ? (
            isAdjudicationTrace(decision.trace) ? (
              <Card elevation={2}>
                <CardBody>
                  <p className="text-sm text-mute">
                    The originating event is an adjudication, not a machine decision —{" "}
                    <Link href={`/decisions/${decision.event_id}`} className="text-link underline underline-offset-2">
                      view its receipt
                    </Link>
                    .
                  </p>
                </CardBody>
              </Card>
            ) : (
              <TraceView trace={decision.trace} />
            )
          ) : (
            <Loading label="Loading trace…" />
          )}
        </div>

        <div className="lg:sticky lg:top-20 lg:self-start">
          {resolved && esc.resolution ? (
            <Card elevation={2}>
              <CardHeader eyebrow="Resolution" action={<OutcomeBadge kind={esc.resolution.outcome_kind} />} />
              <CardBody>
                <dl className="space-y-2.5 text-sm">
                  <div className="flex justify-between gap-4"><dt className="text-mute">action</dt><dd className="font-mono text-xs text-ink">{esc.resolution.chosen_action}</dd></div>
                  <div><dt className="text-mute">rationale</dt><dd className="mt-1 text-ink">{esc.resolution.rationale}</dd></div>
                  <div className="flex justify-between gap-4"><dt className="text-mute">resolved by</dt><dd className="font-mono text-xs text-ink">{esc.resolution.resolver.type}:{esc.resolution.resolver.id}</dd></div>
                  <div className="flex justify-between gap-4"><dt className="text-mute">promoted to golden</dt><dd className="font-mono text-xs text-ink">{esc.resolution.promoted_to_golden ? "yes" : "no"}</dd></div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-mute">adjudication event</dt>
                    <dd><Link href={`/decisions/${esc.resolution.adjudication_event_id}`} className="font-mono text-xs text-link underline underline-offset-2">{esc.resolution.adjudication_event_id.slice(0, 10)}…</Link></dd>
                  </div>
                </dl>
              </CardBody>
              <div className="flex items-center gap-2 border-t border-hairline px-5 py-3 text-xs text-mute">
                chain intact <HashChip hash={esc.resolution.adjudication_event_id} chars={8} />
              </div>
            </Card>
          ) : !canResolve ? (
            <EmptyState title="Read-only" hint="Your role can view escalations but not adjudicate. Approver or owner required." />
          ) : (
            <Card elevation={2}>
              <CardHeader eyebrow="Adjudicate" />
              <form onSubmit={submit}>
                <CardBody className="space-y-4">
                  <div>
                    <FieldLabel htmlFor="outcome-kind">Outcome</FieldLabel>
                    <Select id="outcome-kind" value={outcomeKind} onChange={(e) => setOutcomeKind(e.target.value)} mono>
                      {OUTCOME_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
                    </Select>
                  </div>
                  <div>
                    <FieldLabel htmlFor="chosen-action">Chosen action</FieldLabel>
                    <Input id="chosen-action" list="candidate-actions" mono value={chosenAction} onChange={(e) => setChosenAction(e.target.value)} placeholder="e.g. approve_prorated_refund" />
                    {candidates.length > 0 ? (
                      <datalist id="candidate-actions">{candidates.map((a) => <option key={a} value={a} />)}</datalist>
                    ) : null}
                  </div>
                  <div>
                    <FieldLabel htmlFor="rationale" required>Rationale</FieldLabel>
                    <Textarea id="rationale" value={rationale} onChange={(e) => setRationale(e.target.value)} rows={4} placeholder="Why this outcome? This becomes part of the permanent record." />
                    <p className="mt-1.5 text-xs text-mute">A resolution without a rationale is rejected by the server.</p>
                  </div>
                  <label className="flex items-center gap-2 text-sm text-body">
                    <input type="checkbox" checked={promote} onChange={(e) => setPromote(e.target.checked)} className="accent-[color:var(--color-ink)]" />
                    Promote to golden case (guards future replays)
                  </label>
                </CardBody>
                <div className="border-t border-hairline px-5 py-3.5">
                  <Button type="submit" loading={busy} disabled={!chosenAction.trim() || !rationale.trim()}>
                    Resolve &amp; ledger
                  </Button>
                  {resolveError ? <div className="mt-3"><ErrorNotice error={resolveError} /></div> : null}
                </div>
              </form>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
