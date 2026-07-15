"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { HashChip } from "@/components/ui/HashChip";
import { Input, Textarea } from "@/components/ui/Input";
import { SkeletonCards } from "@/components/ui/Skeleton";
import { StatusPill } from "@/components/ui/StatusPill";
import { PageHeader } from "@/components/ui/PageHeader";
import { TableSurface } from "@/components/ui/Toolbar";
import { useToast } from "@/components/ui/Toast";
import {
  assembleBundle,
  extractDrafts,
  listOnboardingDrafts,
  listSources,
  saveOnboardingDraft,
  uploadSource,
} from "@/lib/api";
import { useSession } from "@/lib/auth";
import type { OnboardingDraft, SourceSummary } from "@/lib/types";

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

function StepBadge({ n }: { n: number }) {
  return (
    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-ink text-[11px] font-semibold text-on-primary">
      {n}
    </span>
  );
}

export default function OnboardingPage() {
  const { apiKey, principal } = useSession();
  const { toast } = useToast();
  const [sources, setSources] = useState<SourceSummary[] | null>(null);
  const [drafts, setDrafts] = useState<OnboardingDraft[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  const [filename, setFilename] = useState("");
  const [content, setContent] = useState("");
  const [uploadBusy, setUploadBusy] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const isOwner = principal.role === "owner";

  const reload = useCallback(() => {
    listSources(apiKey).then(({ sources }) => setSources(sources)).catch(setError);
    listOnboardingDrafts(apiKey).then(({ drafts }) => setDrafts(drafts)).catch(setError);
  }, [apiKey]);

  useEffect(reload, [reload]);

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    if (!filename.trim() || !content.trim() || uploadBusy) return;
    setUploadBusy(true);
    setError(null);
    try {
      await uploadSource(apiKey, filename.trim(), content);
      toast(`Uploaded "${filename.trim()}" as an immutable snapshot.`, "success");
      setFilename("");
      setContent("");
      reload();
    } catch (err) {
      setError(err);
    } finally {
      setUploadBusy(false);
    }
  }

  async function extract(sourceId: string) {
    setBusyId(sourceId);
    setError(null);
    try {
      const { drafts } = await extractDrafts(apiKey, sourceId);
      toast(`Extraction proposed ${drafts.length} draft${drafts.length === 1 ? "" : "s"} — each still needs grounding.`, "success");
      reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusyId(null);
    }
  }

  async function authorBlank() {
    setError(null);
    try {
      const d = await saveOnboardingDraft(apiKey, BLANK_POLICY);
      window.location.href = `/onboarding/drafts/${d.draft_id}`;
    } catch (err) {
      setError(err);
    }
  }

  async function assemble() {
    setError(null);
    try {
      const res = await assembleBundle(apiKey);
      toast(`Assembled a draft bundle (${res.policy_count} policies). Publish via Policies → Registry.`, "success");
    } catch (err) {
      setError(err);
    }
  }

  const accepted = drafts?.filter((d) => d.status === "accepted") ?? [];
  const open = drafts?.filter((d) => d.status !== "rejected") ?? [];

  return (
    <>
      <PageHeader eyebrow="Build" title="Onboarding" subtitle="Turn your policy documents into a cited, published decision bundle.">
        {accepted.length > 0 ? (
          <Button onClick={() => void assemble()}>Assemble bundle · {accepted.length} accepted</Button>
        ) : null}
      </PageHeader>

      {error ? <div className="mb-4"><ErrorNotice error={error} /></div> : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card elevation={2}>
          <CardHeader eyebrow="Step 1" title={<span className="flex items-center gap-2"><StepBadge n={1} /> Upload a policy document</span>} />
          <CardBody>
            <form onSubmit={upload}>
              <Input value={filename} onChange={(e) => setFilename(e.target.value)} placeholder="filename, e.g. refund-policy.md" mono className="mb-2.5 h-9" />
              <Textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={7}
                placeholder="Paste the raw policy text. It becomes a frozen, hashed snapshot that evidence spans cite into."
              />
              <div className="mt-3.5 flex items-center gap-3">
                <Button type="submit" loading={uploadBusy} disabled={!filename.trim() || !content.trim()}>Upload snapshot</Button>
                <button type="button" onClick={() => void authorBlank()} className="text-sm text-link underline underline-offset-2">or author from scratch</button>
              </div>
            </form>
          </CardBody>
        </Card>

        <Card elevation={2}>
          <CardHeader eyebrow="Step 2" title={<span className="flex items-center gap-2"><StepBadge n={2} /> Sources &amp; extraction</span>} />
          <CardBody>
            {!sources ? (
              <SkeletonCards count={2} />
            ) : sources.length === 0 ? (
              <p className="text-sm text-mute">No sources uploaded yet.</p>
            ) : (
              <ul className="space-y-2">
                {sources.map((s) => (
                  <li key={s.source_id} className="flex items-center justify-between gap-3 rounded-md border border-hairline px-3 py-2.5">
                    <div className="min-w-0">
                      <p className="truncate font-mono text-xs font-medium text-ink">{s.filename}</p>
                      <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-mute">{s.byte_length} bytes · <HashChip hash={s.content_hash} chars={8} /></p>
                    </div>
                    {isOwner ? (
                      <Button variant="secondary" size="sm" loading={busyId === s.source_id} onClick={() => void extract(s.source_id)} title="LLM proposes drafts; you still ground each citation">Extract</Button>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 text-[11px] text-mute">Extraction proposes drafts with an LLM; it never grants authority. If the LLM backend is down you can still author by hand.</p>
          </CardBody>
        </Card>
      </div>

      <section className="mt-6">
        <div className="mb-3 flex items-center gap-2">
          <StepBadge n={3} />
          <h2 className="t-display-sm text-ink">Review &amp; ground drafts</h2>
        </div>
        {!drafts ? (
          <SkeletonCards count={3} />
        ) : open.length === 0 ? (
          <EmptyState title="No drafts yet" hint="Upload a document and extract, or author a policy from scratch." />
        ) : (
          <TableSurface>
            <table className="table-ledger">
              <thead><tr><th>policy id</th><th>workflow</th><th>origin</th><th>evidence</th><th>status</th><th>ready</th><th className="text-right"></th></tr></thead>
              <tbody>
                {open.map((d) => (
                  <tr key={d.draft_id}>
                    <td className="font-mono text-xs text-ink">{d.proposed_json.id || "—"}</td>
                    <td className="font-mono text-xs text-body">{d.proposed_json.workflow || "—"}</td>
                    <td className="text-xs text-mute">{d.origin}</td>
                    <td className="text-xs tabular-nums text-ink">{d.evidence_json.length}</td>
                    <td><StatusPill status={d.status === "accepted" ? "resolved" : "open"} /></td>
                    <td><span className={`text-xs font-medium ${d.publishable ? "text-approve" : "text-escalate"}`}>{d.publishable ? "✓ grounded" : "needs citation"}</span></td>
                    <td className="text-right"><Link href={`/onboarding/drafts/${d.draft_id}`} className="text-xs font-medium text-link hover:underline">{d.status === "accepted" ? "View" : "Ground →"}</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableSurface>
        )}
      </section>
    </>
  );
}
