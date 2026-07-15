"use client";

import { useRouter } from "next/navigation";
import { use, useEffect, useRef, useState } from "react";
import { PolicyEditor } from "@/components/onboarding/PolicyEditor";
import { BackLink } from "@/components/ui/BackLink";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Loading } from "@/components/ui/Loading";
import { PageHeader } from "@/components/ui/PageHeader";
import { Select } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusPill } from "@/components/ui/StatusPill";
import { useToast } from "@/components/ui/Toast";
import {
  getOnboardingDraft,
  getSource,
  groundDraft,
  listSources,
  removeDraftEvidence,
  saveOnboardingDraft,
  setDraftStatus,
} from "@/lib/api";
import { useSession } from "@/lib/auth";
import type { OnboardingDraft, Policy, SourceSnapshot, SourceSummary } from "@/lib/types";

export default function DraftReviewerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { apiKey } = useSession();
  const router = useRouter();
  const { toast } = useToast();

  const [draft, setDraft] = useState<OnboardingDraft | null>(null);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [sources, setSources] = useState<SourceSummary[]>([]);
  const [activeSourceId, setActiveSourceId] = useState<string>("");
  const [source, setSource] = useState<SourceSnapshot | null>(null);
  const [selection, setSelection] = useState<{ start: number; end: number; text: string } | null>(null);

  const [error, setError] = useState<unknown>(null);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const preRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    getOnboardingDraft(apiKey, id)
      .then((d) => {
        setDraft(d);
        setPolicy(d.proposed_json);
      })
      .catch(setError);
    listSources(apiKey)
      .then(({ sources }) => {
        setSources(sources);
        if (sources.length > 0) setActiveSourceId(sources[0].source_id);
      })
      .catch(() => {});
  }, [apiKey, id]);

  useEffect(() => {
    if (!activeSourceId) return;
    getSource(apiKey, activeSourceId).then(setSource).catch(() => setSource(null));
  }, [apiKey, activeSourceId]);

  function captureSelection() {
    const sel = window.getSelection();
    const pre = preRef.current;
    if (!sel || sel.rangeCount === 0 || !pre || !source) {
      setSelection(null);
      return;
    }
    const range = sel.getRangeAt(0);
    if (!pre.contains(range.commonAncestorContainer) || sel.isCollapsed) {
      setSelection(null);
      return;
    }
    const pre_range = range.cloneRange();
    pre_range.selectNodeContents(pre);
    pre_range.setEnd(range.startContainer, range.startOffset);
    const start = pre_range.toString().length;
    const text = sel.toString();
    setSelection({ start, end: start + text.length, text });
  }

  async function persistPolicy(next: Policy) {
    setPolicy(next);
    setSaveState("saving");
    try {
      const updated = await saveOnboardingDraft(apiKey, next, { draft_id: id });
      setDraft(updated);
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), 1000);
    } catch (err) {
      setError(err);
      setSaveState("idle");
    }
  }

  async function ground() {
    if (!selection || !activeSourceId) return;
    setError(null);
    try {
      const updated = await groundDraft(apiKey, id, {
        source_id: activeSourceId,
        span_start: selection.start,
        span_end: selection.end,
        excerpt: selection.text,
      });
      setDraft(updated);
      setSelection(null);
      window.getSelection()?.removeAllRanges();
      toast("Citation verified against the source bytes.", "success");
    } catch (err) {
      setError(err);
    }
  }

  async function unground(index: number) {
    try {
      setDraft(await removeDraftEvidence(apiKey, id, index));
    } catch (err) {
      setError(err);
    }
  }

  async function accept() {
    setError(null);
    try {
      await setDraftStatus(apiKey, id, "accepted");
      toast("Draft accepted into the bundle.", "success");
      router.push("/onboarding");
    } catch (err) {
      setError(err);
    }
  }

  async function reject() {
    try {
      await setDraftStatus(apiKey, id, "rejected");
      router.push("/onboarding");
    } catch (err) {
      setError(err);
    }
  }

  if (error && !draft) {
    return (
      <>
        <BackLink href="/onboarding" label="Back to Onboarding" />
        <PageHeader title="Ground draft" />
        <ErrorNotice error={error} />
      </>
    );
  }
  if (!draft || !policy) {
    return (
      <>
        <BackLink href="/onboarding" label="Back to Onboarding" />
        <Skeleton className="mb-4 h-8 w-64" />
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-96" />
          <Skeleton className="h-96" />
        </div>
      </>
    );
  }

  const accepted = draft.status === "accepted";

  return (
    <>
      <BackLink href="/onboarding" label="Back to Onboarding" />
      <PageHeader eyebrow="Build" title="Ground draft" subtitle="Select the source text that justifies this policy — the selection becomes a verified citation.">
        <StatusPill status={draft.publishable ? "published" : "draft"} />
        {saveState !== "idle" ? <span className="text-xs text-mute">{saveState === "saving" ? "saving…" : "saved"}</span> : null}
      </PageHeader>

      {error ? <div className="mb-4"><ErrorNotice error={error} /></div> : null}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* source (highlight here) — sticky so the doc stays in view while editing */}
        <Card elevation={2} className="lg:sticky lg:top-20 lg:self-start">
          <CardHeader
            eyebrow="Source document"
            action={
              sources.length > 0 ? (
                <Select value={activeSourceId} onChange={(e) => setActiveSourceId(e.target.value)} mono className="w-auto min-w-[140px]">
                  {sources.map((s) => <option key={s.source_id} value={s.source_id}>{s.filename}</option>)}
                </Select>
              ) : undefined
            }
          />
          {source ? (
            <>
              <pre
                ref={preRef}
                onMouseUp={captureSelection}
                className="max-h-[calc(100vh-16rem)] cursor-text overflow-auto whitespace-pre-wrap px-5 py-4 font-mono text-[13px] leading-relaxed text-ink selection:bg-[color:var(--color-warning-soft)]"
              >
                {source.content}
              </pre>
              <div className={`flex items-center gap-3 border-t px-5 py-3.5 transition-colors ${selection && !accepted ? "border-hairline-strong bg-warning-soft/40" : "border-hairline"}`}>
                <Button size="sm" onClick={() => void ground()} disabled={!selection || accepted}>Cite selection</Button>
                <span className="min-w-0 flex-1 truncate text-xs text-mute">
                  {selection ? `"${selection.text.slice(0, 60)}${selection.text.length > 60 ? "…" : ""}"` : "highlight text in the document to cite it"}
                </span>
              </div>
            </>
          ) : sources.length === 0 ? (
            <CardBody>
              <p className="text-sm text-mute">
                No source uploaded. You can still author the policy, but publishing needs a grounded citation — upload a document on the Onboarding page.
              </p>
            </CardBody>
          ) : (
            <Loading label="Loading source…" />
          )}
        </Card>

        {/* policy + evidence + accept */}
        <div className="space-y-4">
          <Card elevation={2}>
            <CardHeader eyebrow="Policy" />
            <CardBody>
              <PolicyEditor policy={policy} onChange={(p) => void persistPolicy(p)} />
            </CardBody>
          </Card>

          <Card elevation={2}>
            <CardHeader eyebrow={`Grounded evidence · ${draft.evidence_json.length}`} />
            <CardBody>
              {draft.evidence_json.length === 0 ? (
                <p className="text-xs text-deny">No citation yet — this policy cannot publish until you cite the source.</p>
              ) : (
                <ul className="space-y-2">
                  {draft.evidence_json.map((ev, i) => (
                    <li key={i} className="flex items-start justify-between gap-2 rounded-md border-l-2 border-ink bg-canvas-soft px-3 py-2">
                      <div className="min-w-0">
                        <p className="text-xs italic text-ink">&ldquo;{ev.excerpt}&rdquo;</p>
                        <p className="mt-0.5 font-mono text-[10px] text-mute">{ev.source_id} · span {ev.span_start}–{ev.span_end}</p>
                      </div>
                      {!accepted ? <button type="button" onClick={() => void unground(i)} className="shrink-0 text-xs text-mute hover:text-deny">remove</button> : null}
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>

          {draft.issues_json.length > 0 && !accepted ? (
            <ul className="list-inside list-disc rounded-md bg-warning-soft px-4 py-2.5 text-xs text-warning-deep">
              {draft.issues_json.map((iss, i) => <li key={i}>{iss}</li>)}
            </ul>
          ) : null}

          {!accepted ? (
            <div className="flex items-center gap-3">
              <Button onClick={() => void accept()} disabled={!draft.publishable} title={draft.publishable ? "Accept into the bundle" : "Ground a citation and complete the policy first"}>
                Accept draft
              </Button>
              <button type="button" onClick={() => void reject()} className="text-sm text-mute underline underline-offset-2 hover:text-deny">Reject</button>
            </div>
          ) : (
            <p className="rounded-md bg-approve-bg px-4 py-2.5 text-sm text-approve">
              Accepted — this policy will be included when you assemble the bundle.
            </p>
          )}
        </div>
      </div>
    </>
  );
}
