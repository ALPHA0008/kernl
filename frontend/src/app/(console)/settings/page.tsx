"use client";

import { useEffect, useState } from "react";
import { TenantKeys } from "@/components/policy/TenantKeys";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { PageHeader } from "@/components/ui/PageHeader";
import { SkeletonCards } from "@/components/ui/Skeleton";
import { ApiError, API_URL, getActiveBundle, listPolicyDrafts, verifyLedger } from "@/lib/api";
import { useSession } from "@/lib/auth";
import { fmtDate } from "@/lib/format";
import type { ActiveBundle, ChainVerify, PolicyDraft } from "@/lib/types";

export default function SettingsPage() {
  const { apiKey, principal } = useSession();
  const [active, setActive] = useState<ActiveBundle | null>(null);
  const [verify, setVerify] = useState<ChainVerify | null>(null);
  const [drafts, setDrafts] = useState<PolicyDraft[] | null>(null);
  const [draftsUnavailable, setDraftsUnavailable] = useState<string | null>(null);

  useEffect(() => {
    getActiveBundle(apiKey).then(setActive).catch(() => setActive(null));
    verifyLedger(apiKey).then(setVerify).catch(() => setVerify(null));
    if (principal.role === "owner") {
      listPolicyDrafts(apiKey)
        .then(({ drafts }) => setDrafts(drafts))
        .catch((e) => {
          if (e instanceof ApiError && e.status === 503) setDraftsUnavailable(e.detail);
          else setDraftsUnavailable(e instanceof Error ? e.message : String(e));
          setDrafts([]);
        });
    }
  }, [apiKey, principal.role]);

  return (
    <>
      <PageHeader eyebrow="Build" title="Settings" subtitle="Tenant, session, and extraction proposals." />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card elevation={2}>
          <CardHeader eyebrow="Session" />
          <CardBody>
            <dl className="space-y-2 text-sm">
              <Row label="tenant" value={principal.company_id} mono />
              <Row label="role" value={principal.role} />
              <Row label="key id" value={principal.key_id} mono />
              <Row label="API endpoint" value={API_URL} mono />
            </dl>
          </CardBody>
        </Card>

        <Card elevation={2}>
          <CardHeader eyebrow="System" />
          <CardBody>
            <dl className="space-y-2 text-sm">
              <Row label="active bundle" value={active ? active.content_hash.slice(0, 22) + "…" : "none published"} mono />
              <Row label="ledger chain" value={verify ? (verify.chain_valid ? "verified" : "BROKEN") : "—"} tone={verify ? (verify.chain_valid ? "ok" : "bad") : undefined} />
              <Row label="workflows" value={String(active?.bundle.workflows.length ?? 0)} />
              <Row label="policies" value={String(active?.bundle.policies.length ?? 0)} />
            </dl>
          </CardBody>
        </Card>
      </div>

      {active ? (
        <Card elevation={2} className="mt-6">
          <CardHeader eyebrow="Workflow fact schemas" />
          <CardBody>
            {active.bundle.workflows.map((w) => (
              <div key={w.name} className="mb-4 last:mb-0">
                <p className="font-mono text-sm font-medium text-ink">{w.name}</p>
                {w.description ? <p className="text-xs text-mute">{w.description}</p> : null}
                <ul className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
                  {w.facts.map((f) => (
                    <li key={f.name} className="font-mono text-xs text-body">
                      {f.name}<span className="text-mute">:{f.value_type}</span>
                      {f.default !== null ? <span className="text-mute">={String(f.default)}</span> : null}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </CardBody>
        </Card>
      ) : null}

      {principal.role === "owner" ? (
        <section className="mt-6">
          <h2 className="t-display-sm mb-2 text-ink">API keys</h2>
          <p className="mb-3 text-sm text-body">
            Issue and revoke keys for your own tenant. A new key&rsquo;s plaintext is shown once — rotate by issuing a replacement, then revoking the old key.
          </p>
          <TenantKeys apiKey={apiKey} companyId={principal.company_id} />
        </section>
      ) : null}

      {principal.role === "owner" ? (
        <section className="mt-6">
          <h2 className="t-display-sm mb-2 text-ink">Extraction drafts</h2>
          <p className="mb-3 text-sm text-body">
            Policies proposed by the compiler. They are never runtime authority — a draft publishes only after a reviewer attaches verified source spans.
          </p>
          {draftsUnavailable ? (
            <ErrorNotice error={new ApiError(503, draftsUnavailable)} />
          ) : drafts === null ? (
            <SkeletonCards count={3} />
          ) : drafts.length === 0 ? (
            <EmptyState title="No pending drafts" hint="Run the extraction pipeline over a source document to propose drafts." />
          ) : (
            <div className="space-y-2">
              {drafts.map((d) => (
                <details key={d.draft_id} className="rounded-lg bg-canvas shadow-[var(--shadow-1)]">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-3 transition-colors hover:bg-canvas-soft">
                    <span className="font-mono text-xs text-ink">{d.source_skill_id ?? d.draft_id}</span>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${d.publishable ? "bg-approve-bg text-approve" : "bg-escalate-bg text-escalate"}`}>
                      {d.publishable ? "ready" : "needs spans"}
                    </span>
                  </summary>
                  <div className="border-t border-hairline px-5 py-3">
                    {d.issues_json.length > 0 ? (
                      <ul className="mb-2 list-inside list-disc text-xs text-escalate">{d.issues_json.map((iss, i) => <li key={i}>{iss}</li>)}</ul>
                    ) : null}
                    <p className="font-mono text-[10px] text-mute">created {fmtDate(d.created_at)}</p>
                  </div>
                </details>
              ))}
            </div>
          )}
        </section>
      ) : null}
    </>
  );
}

function Row({ label, value, mono, tone }: { label: string; value: string; mono?: boolean; tone?: "ok" | "bad" }) {
  const color = tone === "ok" ? "text-approve" : tone === "bad" ? "text-deny font-medium" : "text-ink";
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-mute">{label}</dt>
      <dd className={`${mono ? "font-mono text-xs" : ""} ${color}`}>{value}</dd>
    </div>
  );
}
