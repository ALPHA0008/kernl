"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ApiError, evaluate, getActiveBundle } from "@/lib/api";
import { useSession } from "@/lib/auth";
import { newIdempotencyKey } from "@/lib/format";
import type { ActiveBundle, EvaluateResponse, Scalar, WorkflowSpec } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { HashChip } from "@/components/ui/HashChip";
import { Input, Select, Textarea } from "@/components/ui/Input";
import { OutcomeBadge } from "@/components/ui/OutcomeBadge";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";

interface FactInput {
  include: boolean;
  raw: string;
}

function parseFact(raw: string, valueType: string): Scalar {
  if (valueType === "number") {
    const n = Number(raw);
    if (raw.trim() === "" || Number.isNaN(n)) throw new Error(`"${raw}" is not a number`);
    return n;
  }
  if (valueType === "boolean") return raw === "true";
  return raw;
}

export default function EvaluatePage() {
  const { apiKey } = useSession();
  const [active, setActive] = useState<ActiveBundle | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const [workflow, setWorkflow] = useState<string>("");
  const [inputs, setInputs] = useState<Record<string, FactInput>>({});
  const [mode, setMode] = useState<"form" | "json">("form");
  const [jsonFacts, setJsonFacts] = useState("{}");

  const [result, setResult] = useState<EvaluateResponse | null>(null);
  const [rerun, setRerun] = useState<{ same: boolean } | null>(null);
  const [lastFacts, setLastFacts] = useState<Record<string, unknown> | null>(null);
  const [submitError, setSubmitError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getActiveBundle(apiKey)
      .then((a) => {
        setActive(a);
        if (a.bundle.workflows.length > 0) setWorkflow(a.bundle.workflows[0].name);
      })
      .catch((e) => setLoadError(e))
      .finally(() => setLoading(false));
  }, [apiKey]);

  const spec: WorkflowSpec | undefined = useMemo(
    () => active?.bundle.workflows.find((w) => w.name === workflow),
    [active, workflow],
  );

  const [builtFor, setBuiltFor] = useState<string | null>(null);
  if (spec && builtFor !== workflow) {
    const next: Record<string, FactInput> = {};
    for (const f of spec.facts) {
      next[f.name] = {
        include: true,
        raw: f.default !== null ? String(f.default) : f.value_type === "boolean" ? "false" : "",
      };
    }
    setInputs(next);
    setResult(null);
    setRerun(null);
    setSubmitError(null);
    setBuiltFor(workflow);
  }

  function buildFacts(): Record<string, unknown> {
    if (mode === "json") {
      const parsed = JSON.parse(jsonFacts);
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed))
        throw new Error("facts must be a JSON object");
      return parsed as Record<string, unknown>;
    }
    const facts: Record<string, unknown> = {};
    for (const f of spec?.facts ?? []) {
      const input = inputs[f.name];
      if (!input?.include) continue;
      facts[f.name] = parseFact(input.raw, f.value_type);
    }
    return facts;
  }

  async function submit(facts: Record<string, unknown>, isRerun: boolean) {
    setBusy(true);
    setSubmitError(null);
    if (!isRerun) setRerun(null);
    try {
      const res = await evaluate(apiKey, {
        workflow,
        facts,
        idempotency_key: newIdempotencyKey(),
      });
      if (isRerun && result) {
        setRerun({ same: JSON.stringify(res.outcome) === JSON.stringify(result.outcome) });
      } else {
        setResult(res);
        setLastFacts(facts);
      }
    } catch (err) {
      setSubmitError(err);
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    let facts: Record<string, unknown>;
    try {
      facts = buildFacts();
    } catch (err) {
      setSubmitError(err);
      return;
    }
    void submit(facts, false);
  }

  if (loading) {
    return (
      <>
        <PageHeader eyebrow="Operate" title="Evaluate" subtitle="Run a real decision against the active bundle." />
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-80" />
          <Skeleton className="h-40" />
        </div>
      </>
    );
  }

  if (loadError) {
    const noBundle = loadError instanceof ApiError && loadError.status === 404;
    return (
      <>
        <PageHeader eyebrow="Operate" title="Evaluate" subtitle="Run a real decision against the active bundle." />
        {noBundle ? (
          <EmptyState
            title="No published bundle for this tenant"
            hint="Decisions require a published, replay-gated bundle. Start in Onboarding to build one."
            action={
              <Link href="/onboarding">
                <Button>Go to Onboarding</Button>
              </Link>
            }
          />
        ) : (
          <ErrorNotice error={loadError} />
        )}
      </>
    );
  }

  return (
    <>
      <PageHeader eyebrow="Operate" title="Evaluate" subtitle="Run a real decision against the active bundle and inspect exactly why it ruled the way it did.">
        <span className="flex items-center gap-2 rounded-md bg-canvas px-2.5 py-1.5 shadow-[var(--shadow-1)]">
          <span className="t-eyebrow">bundle</span>
          <HashChip hash={active?.content_hash ?? null} />
        </span>
      </PageHeader>

      {/* workflow selector — a deliberate control, not buried in a card header */}
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <label htmlFor="workflow" className="t-eyebrow">Workflow</label>
        <Select
          id="workflow"
          value={workflow}
          onChange={(e) => setWorkflow(e.target.value)}
          mono
          className="w-auto min-w-[200px]"
        >
          {active?.bundle.workflows.map((w) => (
            <option key={w.name} value={w.name}>{w.name}</option>
          ))}
        </Select>
        {spec?.description ? (
          <span className="text-sm text-mute">{spec.description}</span>
        ) : null}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.92fr)]">
        {/* facts form */}
        <Card elevation={2}>
          <form onSubmit={onSubmit}>
            <div className="flex items-center gap-1 border-b border-hairline px-5 pt-3">
              {(["form", "json"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={`relative px-3 py-2.5 text-[13px] font-medium transition-colors ${
                    mode === m ? "text-ink" : "text-mute hover:text-body"
                  }`}
                >
                  {m === "form" ? "Typed facts" : "Raw JSON"}
                  {mode === m ? (
                    <span className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-ink" />
                  ) : null}
                </button>
              ))}
            </div>

            <CardBody className="!px-0 !py-0">
              {mode === "form" ? (
                <div className="divide-y divide-hairline">
                  {(spec?.facts ?? []).map((f) => {
                    const input = inputs[f.name] ?? { include: true, raw: "" };
                    return (
                      <div
                        key={f.name}
                        className={`flex items-center gap-3 px-5 py-3 transition-colors ${input.include ? "" : "bg-canvas-soft/60"}`}
                      >
                        <input
                          type="checkbox"
                          checked={input.include}
                          onChange={(e) =>
                            setInputs((prev) => ({ ...prev, [f.name]: { ...input, include: e.target.checked } }))
                          }
                          className="accent-[color:var(--color-ink)]"
                          title="Uncheck to omit this fact (strict missing-fact semantics)"
                        />
                        <div className="min-w-0 flex-1">
                          <label className="font-mono text-[13px] font-medium text-ink" htmlFor={`fact-${f.name}`}>
                            {f.name}
                          </label>
                          <span className="ml-2 font-mono text-[11px] text-mute">
                            {f.value_type}{f.default !== null ? ` · def ${String(f.default)}` : ""}
                          </span>
                          {f.description ? <p className="text-[11px] text-mute">{f.description}</p> : null}
                        </div>
                        <div className="w-[46%] shrink-0">
                          {f.value_type === "boolean" ? (
                            <Select
                              id={`fact-${f.name}`}
                              value={input.raw}
                              disabled={!input.include}
                              mono
                              onChange={(e) => setInputs((prev) => ({ ...prev, [f.name]: { ...input, raw: e.target.value } }))}
                            >
                              <option value="false">false</option>
                              <option value="true">true</option>
                            </Select>
                          ) : (
                            <Input
                              id={`fact-${f.name}`}
                              type={f.value_type === "number" ? "number" : "text"}
                              step="any"
                              value={input.raw}
                              disabled={!input.include}
                              mono
                              placeholder="—"
                              className="h-9"
                              onChange={(e) => setInputs((prev) => ({ ...prev, [f.name]: { ...input, raw: e.target.value } }))}
                            />
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="p-5">
                  <Textarea value={jsonFacts} onChange={(e) => setJsonFacts(e.target.value)} rows={12} spellCheck={false} mono aria-label="Facts as JSON" />
                </div>
              )}
            </CardBody>

            <div className="flex items-center justify-between border-t border-hairline px-5 py-3.5">
              <span className="text-xs text-mute">Uncheck a fact to omit it — the evaluator escalates rather than guessing.</span>
              <Button type="submit" loading={busy} disabled={!workflow}>Evaluate</Button>
            </div>
          </form>
        </Card>

        {/* result */}
        <div className="lg:sticky lg:top-20 lg:self-start">
          {submitError ? <div className="mb-4"><ErrorNotice error={submitError} /></div> : null}

          {result ? (
            <Card elevation={3} className="page-enter overflow-hidden">
              {/* outcome banner — the headline, unmissable */}
              <div className="flex items-center justify-between gap-4 border-b border-hairline bg-canvas-soft px-5 py-4">
                <div>
                  <div className="t-eyebrow mb-1.5">Decision</div>
                  <OutcomeBadge kind={result.outcome.kind} size="lg" />
                </div>
                {result.outcome.action ? (
                  <code className="max-w-[55%] truncate rounded-md bg-canvas px-2.5 py-1.5 font-mono text-xs text-ink shadow-[var(--shadow-1)]" title={result.outcome.action}>
                    {result.outcome.action}
                  </code>
                ) : null}
              </div>
              <CardBody>
                <dl className="space-y-2.5 text-sm">
                  {result.outcome.policy_id ? <Row label="winning policy" value={<code className="font-mono text-xs">{result.outcome.policy_id}</code>} /> : null}
                  {result.outcome.escalation_reason ? <Row label="escalation reason" value={<code className="font-mono text-xs text-escalate">{result.outcome.escalation_reason}</code>} /> : null}
                  {result.outcome.missing_facts.length > 0 ? <Row label="missing facts" value={<code className="font-mono text-xs">{result.outcome.missing_facts.join(", ")}</code>} /> : null}
                  <Row label="bundle" value={<HashChip hash={result.bundle_hash} />} />
                </dl>
              </CardBody>
              <div className="flex flex-wrap items-center gap-2.5 border-t border-hairline px-5 py-3.5">
                <Link href={`/decisions/${result.decision_id}`}><Button size="sm">Inspect trace</Button></Link>
                {result.escalation_id ? <Link href={`/escalations/${result.escalation_id}`}><Button variant="secondary" size="sm">Open escalation</Button></Link> : null}
                <Button variant="ghost" size="sm" loading={busy} disabled={!lastFacts} onClick={() => lastFacts && void submit(lastFacts, true)} title="Identical facts, new key — the outcome must be identical">
                  Re-run
                </Button>
                {rerun ? (
                  <span className={`text-xs font-medium ${rerun.same ? "text-approve" : "text-error"}`}>
                    {rerun.same ? "✓ identical — deterministic" : "✗ differs — report this"}
                  </span>
                ) : null}
              </div>
            </Card>
          ) : (
            /* Solid-hairline card, not a dashed dropzone: this is a result
               placeholder, not an upload target. A faint mono line previews
               the shape of the answer the user is about to get. */
            <div className="flex min-h-[280px] flex-col items-center justify-center rounded-lg bg-canvas px-6 py-12 text-center shadow-[var(--shadow-1)]">
              <p className="t-body-md font-medium text-ink">No decision yet</p>
              <p className="mt-1.5 max-w-xs text-sm leading-relaxed text-body">
                Set the facts and evaluate. The outcome and a link to its full trace appear here.
              </p>
              <p className="mt-4 font-mono text-xs text-mute">outcome · policy · bundle · trace →</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-mute">{label}</dt>
      <dd className="text-ink">{value}</dd>
    </div>
  );
}
