"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { HashChip } from "@/components/ui/HashChip";
import { PageHeader } from "@/components/ui/PageHeader";
import { SkeletonCards } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { extractDrafts, getSource, listSources } from "@/lib/api";
import { useSession } from "@/lib/auth";
import { fmtDate } from "@/lib/format";
import type { SourceSnapshot, SourceSummary } from "@/lib/types";

/** Thin, read-only source registry (V1_EXECUTION_PLAN.md section 7 nav spec:
 *  "Sources — read-only list + extract-drafts trigger"). Upload itself stays
 *  on Onboarding's Step 1, since it's the entry point into that authoring
 *  flow; this screen is where an Integrator or Owner audits what's on file
 *  and can kick off extraction without wading into the onboarding wizard. */
export default function SourcesPage() {
  const { apiKey, principal } = useSession();
  const { toast } = useToast();
  const isOwner = principal.role === "owner";

  const [sources, setSources] = useState<SourceSummary[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<SourceSnapshot | null>(null);
  const [snapshotError, setSnapshotError] = useState<unknown>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const reload = useCallback(() => {
    listSources(apiKey).then(({ sources }) => setSources(sources)).catch(setError);
  }, [apiKey]);

  useEffect(reload, [reload]);

  async function open(sourceId: string) {
    if (openId === sourceId) {
      setOpenId(null);
      setSnapshot(null);
      return;
    }
    setOpenId(sourceId);
    setSnapshot(null);
    setSnapshotError(null);
    try {
      setSnapshot(await getSource(apiKey, sourceId));
    } catch (err) {
      setSnapshotError(err);
    }
  }

  async function extract(sourceId: string) {
    setBusyId(sourceId);
    setError(null);
    try {
      const { drafts } = await extractDrafts(apiKey, sourceId);
      toast(`Extraction proposed ${drafts.length} draft${drafts.length === 1 ? "" : "s"} — review in Onboarding.`, "success");
    } catch (err) {
      setError(err);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <PageHeader eyebrow="Build" title="Sources" subtitle="Immutable, hashed snapshots of every policy document on file." />

      {error ? <div className="mb-4"><ErrorNotice error={error} /></div> : null}

      {!sources ? (
        <SkeletonCards count={3} />
      ) : sources.length === 0 ? (
        <EmptyState title="No sources uploaded" hint="Upload a policy document from Onboarding to get started." />
      ) : (
        <div className="space-y-1.5">
          {sources.map((s) => (
            <div key={s.source_id} className="rounded-lg bg-canvas shadow-[var(--shadow-1)]">
              <div className="flex items-center gap-3 px-4 py-3">
                <button
                  type="button"
                  onClick={() => void open(s.source_id)}
                  className="min-w-0 flex-1 truncate text-left font-mono text-[13px] font-medium text-ink hover:text-link"
                >
                  {s.filename}
                </button>
                <span className="shrink-0 text-xs tabular-nums text-mute">{s.byte_length} bytes</span>
                <HashChip hash={s.content_hash} chars={8} />
                <span className="shrink-0 text-xs text-mute">{fmtDate(s.created_at)}</span>
                {isOwner ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    loading={busyId === s.source_id}
                    onClick={() => void extract(s.source_id)}
                    title="LLM proposes drafts; you still ground each citation"
                  >
                    Extract
                  </Button>
                ) : null}
              </div>
              {openId === s.source_id ? (
                <div className="border-t border-hairline px-5 py-4">
                  {snapshotError ? (
                    <ErrorNotice error={snapshotError} />
                  ) : !snapshot ? (
                    <p className="text-xs text-mute">loading…</p>
                  ) : (
                    <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-canvas-soft px-3.5 py-3 font-mono text-xs leading-relaxed text-body">
                      {snapshot.content}
                    </pre>
                  )}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
