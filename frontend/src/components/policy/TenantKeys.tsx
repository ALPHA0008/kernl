"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { SkeletonCards } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { issueTenantKey, listTenantKeys, revokeTenantKey } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { ApiKeySummary } from "@/lib/types";

const ROLES = ["owner", "approver", "agent"] as const;

/** Owner-only key management: issue (shown once, never retrievable again) and
 *  revoke. Backend already refuses to revoke the last active owner key --
 *  rotation is issue-then-revoke, in that order, so a tenant can never lock
 *  itself out. */
export function TenantKeys({ apiKey, companyId }: { apiKey: string; companyId: string }) {
  const { toast } = useToast();
  const [keys, setKeys] = useState<ApiKeySummary[] | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [role, setRole] = useState<(typeof ROLES)[number]>("agent");
  const [issuing, setIssuing] = useState(false);
  const [issueError, setIssueError] = useState<unknown>(null);
  const [issued, setIssued] = useState<string | null>(null);
  const [revokingId, setRevokingId] = useState<string | null>(null);

  const reload = useCallback(() => {
    listTenantKeys(apiKey, companyId)
      .then(({ keys }) => setKeys([...keys].sort((a, b) => b.created_at.localeCompare(a.created_at))))
      .catch(setLoadError);
  }, [apiKey, companyId]);

  useEffect(reload, [reload]);

  async function issue() {
    setIssuing(true);
    setIssueError(null);
    try {
      const res = await issueTenantKey(apiKey, companyId, role);
      setIssued(res.api_key);
      reload();
    } catch (err) {
      setIssueError(err);
    } finally {
      setIssuing(false);
    }
  }

  async function revoke(keyId: string) {
    setRevokingId(keyId);
    setLoadError(null);
    try {
      await revokeTenantKey(apiKey, companyId, keyId);
      toast("Key revoked.", "success");
      reload();
    } catch (err) {
      setLoadError(err);
    } finally {
      setRevokingId(null);
    }
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div>
          <label className="t-eyebrow mb-1 block" htmlFor="new-key-role">new key role</label>
          <select
            id="new-key-role"
            value={role}
            onChange={(e) => setRole(e.target.value as (typeof ROLES)[number])}
            className="h-9 rounded-[6px] border border-hairline bg-canvas px-2.5 text-[13px] text-ink shadow-[var(--shadow-1)]"
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>
        <Button size="sm" loading={issuing} onClick={() => void issue()}>Issue key</Button>
      </div>

      {issueError ? <div className="mb-4"><ErrorNotice error={issueError} /></div> : null}

      {issued ? (
        <div className="mb-4 rounded-md border border-hairline bg-canvas-soft px-3.5 py-3">
          <p className="mb-2 text-xs font-medium text-approve">
            New key issued — shown once, store it now. It will never be shown again.
          </p>
          <code className="block break-all rounded-md bg-canvas px-3 py-2 font-mono text-xs text-ink shadow-[var(--shadow-1)]">
            {issued}
          </code>
          <button type="button" onClick={() => setIssued(null)} className="mt-2 text-xs text-mute hover:text-ink">dismiss</button>
        </div>
      ) : null}

      {loadError ? <div className="mb-4"><ErrorNotice error={loadError} /></div> : null}

      {keys === null ? (
        <SkeletonCards count={2} />
      ) : keys.length === 0 ? (
        <p className="text-sm text-mute">No keys found.</p>
      ) : (
        <div className="space-y-1.5">
          {keys.map((k) => (
            <div
              key={k.key_id}
              className="flex items-center justify-between gap-3 rounded-lg bg-canvas px-4 py-2.5 shadow-[var(--shadow-1)]"
            >
              <div className="flex min-w-0 items-center gap-3">
                <span className="truncate font-mono text-xs text-ink">{k.key_id}</span>
                <span className="shrink-0 rounded-full bg-canvas-soft px-2 py-0.5 text-[11px] text-body shadow-[var(--shadow-1)]">
                  {k.role}
                </span>
                <span className="shrink-0 text-[11px] text-mute">{fmtDate(k.created_at)}</span>
              </div>
              {k.active ? (
                <button
                  type="button"
                  onClick={() => void revoke(k.key_id)}
                  disabled={revokingId === k.key_id}
                  className="shrink-0 text-xs font-medium text-deny hover:underline disabled:opacity-50"
                >
                  {revokingId === k.key_id ? "revoking…" : "revoke"}
                </button>
              ) : (
                <span className="shrink-0 text-xs text-mute">revoked</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
