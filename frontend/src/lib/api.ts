/** Typed client for the /v1 API. Every call carries the tenant API key;
 *  errors are normalized to ApiError with the backend's `detail` string so
 *  screens can render the real failure (409 publish gate, 503 ledger down)
 *  instead of a generic toast. */

import type {
  ActiveBundle,
  ApiKeySummary,
  AssembleResult,
  BundleDiffResponse,
  BundleSummary,
  ChainVerify,
  DecisionEvent,
  Escalation,
  EvaluateResponse,
  GoldenCase,
  IssuedApiKey,
  OnboardingDraft,
  Policy,
  PolicyDraft,
  Principal,
  ProvisionResult,
  ReplayRun,
  ReplayRunSummary,
  SourceSnapshot,
  SourceSummary,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_KERNL_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

async function call<T>(
  key: string,
  path: string,
  init?: { method?: string; body?: unknown },
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: init?.method ?? "GET",
      headers: {
        "X-API-Key": key,
        ...(init?.body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
  } catch {
    throw new ApiError(0, `Cannot reach the Kernl API at ${API_URL}. Is the backend running?`);
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body?.detail)) {
        // FastAPI validation errors: [{loc:[...], msg:"..."}] -> readable sentence
        detail = body.detail
          .map((e: { loc?: unknown[]; msg?: string }) => {
            const field = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : undefined;
            return field ? `${field}: ${e.msg}` : e.msg;
          })
          .join("; ");
      } else if (body?.detail) {
        detail = JSON.stringify(body.detail);
      }
    } catch {
      /* non-JSON error body; keep status text */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

// ------------------------------------------------------------------- auth

export const getMe = (key: string) => call<Principal>(key, "/v1/me");

// -------------------------------------------------------------- decisions

export const evaluate = (
  key: string,
  body: { workflow: string; facts: Record<string, unknown>; idempotency_key: string },
) => call<EvaluateResponse>(key, "/v1/decisions/evaluate", { method: "POST", body });

export const getDecision = (key: string, id: string) =>
  call<DecisionEvent>(key, `/v1/decisions/${encodeURIComponent(id)}`);

// ----------------------------------------------------------------- ledger

export const listLedger = (
  key: string,
  q: {
    workflow?: string;
    outcome?: string;
    bundle_hash?: string;
    since?: string;
    until?: string;
    limit?: number;
    offset?: number;
  } = {},
) => {
  const params = new URLSearchParams();
  if (q.workflow) params.set("workflow", q.workflow);
  if (q.outcome) params.set("outcome", q.outcome);
  if (q.bundle_hash) params.set("bundle_hash", q.bundle_hash);
  if (q.since) params.set("since", q.since);
  if (q.until) params.set("until", q.until);
  if (q.limit !== undefined) params.set("limit", String(q.limit));
  if (q.offset !== undefined) params.set("offset", String(q.offset));
  const qs = params.toString();
  return call<{ events: DecisionEvent[] }>(key, `/v1/ledger${qs ? `?${qs}` : ""}`);
};

export const verifyLedger = (key: string) =>
  call<ChainVerify>(key, "/v1/ledger/verify");

// ---------------------------------------------------------------- bundles

export const listBundles = (key: string) =>
  call<{ bundles: BundleSummary[] }>(key, "/v1/bundles");

export const getActiveBundle = (key: string) =>
  call<ActiveBundle>(key, "/v1/bundles/active");

export const createDraft = (key: string, bundle: Record<string, unknown>) =>
  call<{ record_id: string; content_hash: string; status: string }>(
    key,
    "/v1/bundles/drafts",
    { method: "POST", body: { bundle } },
  );

export const publishBundle = (key: string, recordId: string) =>
  call<{ record_id: string; content_hash: string; status: string; replay_run_id: string }>(
    key,
    `/v1/bundles/${encodeURIComponent(recordId)}/publish`,
    { method: "POST" },
  );

export const getBundleDiff = (key: string, recordId: string, against?: string) =>
  call<BundleDiffResponse>(
    key,
    `/v1/bundles/${encodeURIComponent(recordId)}/diff${against ? `?against=${encodeURIComponent(against)}` : ""}`,
  );

export const activateBundle = (key: string, recordId: string) =>
  call<{ record_id: string; content_hash: string; status: string }>(
    key,
    `/v1/bundles/${encodeURIComponent(recordId)}/activate`,
    { method: "POST" },
  );

// ----------------------------------------------------------------- replay

export const runReplay = (
  key: string,
  body: { candidate_record_id: string; include_reference?: boolean },
) => call<ReplayRun>(key, "/v1/replays", { method: "POST", body });

export const listReplays = (key: string) =>
  call<{ runs: ReplayRunSummary[] }>(key, "/v1/replays");

export const getReplay = (key: string, runId: string) =>
  call<ReplayRun>(key, `/v1/replays/${encodeURIComponent(runId)}`);

export const acknowledgeReplay = (key: string, runId: string) =>
  call<{ run_id: string; acknowledged_by: string; acknowledged_at: string }>(
    key,
    `/v1/replays/${encodeURIComponent(runId)}/acknowledge`,
    { method: "POST" },
  );

// ------------------------------------------------------------ escalations

export const listEscalations = (key: string, status?: string) =>
  call<{ escalations: Escalation[] }>(
    key,
    `/v1/escalations${status ? `?status=${encodeURIComponent(status)}` : ""}`,
  );

export const getEscalation = (key: string, id: string) =>
  call<Escalation>(key, `/v1/escalations/${encodeURIComponent(id)}`);

export const resolveEscalation = (
  key: string,
  id: string,
  body: {
    chosen_action: string;
    outcome_kind: string;
    rationale: string;
    promote_to_golden: boolean;
  },
) =>
  call<Escalation>(key, `/v1/escalations/${encodeURIComponent(id)}/resolve`, {
    method: "POST",
    body,
  });

// ---------------------------------------------------------- cases/drafts

export const listCases = (key: string, workflow?: string) =>
  call<{ cases: GoldenCase[] }>(
    key,
    `/v1/cases${workflow ? `?workflow=${encodeURIComponent(workflow)}` : ""}`,
  );

export const listPolicyDrafts = (key: string, status = "pending_review") =>
  call<{ drafts: PolicyDraft[] }>(
    key,
    `/v1/drafts?status=${encodeURIComponent(status)}`,
  );

// -------------------------------------------------------------- onboarding

export const provisionTenant = (adminKey: string, companyId: string, name: string) =>
  call<ProvisionResult>(adminKey, "/v1/tenants", {
    method: "POST",
    body: { company_id: companyId, name },
  });

export const uploadSource = (key: string, filename: string, content: string) =>
  call<SourceSummary>(key, "/v1/sources", {
    method: "POST",
    body: { filename, content },
  });

export const listSources = (key: string) =>
  call<{ sources: SourceSummary[] }>(key, "/v1/sources");

export const getSource = (key: string, sourceId: string) =>
  call<SourceSnapshot>(key, `/v1/sources/${encodeURIComponent(sourceId)}`);

export const extractDrafts = (key: string, sourceId: string) =>
  call<{ drafts: OnboardingDraft[] }>(key, "/v1/onboarding/extract", {
    method: "POST",
    body: { source_id: sourceId },
  });

export const listOnboardingDrafts = (key: string, status?: string) =>
  call<{ drafts: OnboardingDraft[] }>(
    key,
    `/v1/onboarding/drafts${status ? `?status=${encodeURIComponent(status)}` : ""}`,
  );

export const getOnboardingDraft = (key: string, draftId: string) =>
  call<OnboardingDraft>(key, `/v1/onboarding/drafts/${encodeURIComponent(draftId)}`);

export const saveOnboardingDraft = (
  key: string,
  proposed: Policy,
  opts: { draft_id?: string; origin?: string } = {},
) =>
  call<OnboardingDraft>(key, "/v1/onboarding/drafts", {
    method: "POST",
    body: { proposed, draft_id: opts.draft_id, origin: opts.origin ?? "authored" },
  });

export const groundDraft = (
  key: string,
  draftId: string,
  body: { source_id: string; span_start: number; span_end: number; excerpt: string },
) =>
  call<OnboardingDraft>(
    key,
    `/v1/onboarding/drafts/${encodeURIComponent(draftId)}/ground`,
    { method: "POST", body },
  );

export const removeDraftEvidence = (key: string, draftId: string, index: number) =>
  call<OnboardingDraft>(
    key,
    `/v1/onboarding/drafts/${encodeURIComponent(draftId)}/evidence/${index}`,
    { method: "DELETE" },
  );

export const setDraftStatus = (key: string, draftId: string, status: string) =>
  call<OnboardingDraft>(
    key,
    `/v1/onboarding/drafts/${encodeURIComponent(draftId)}/status`,
    { method: "POST", body: { status } },
  );

export const assembleBundle = (key: string) =>
  call<AssembleResult>(key, "/v1/onboarding/assemble", { method: "POST" });

// ---------------------------------------------------------------- api keys

export const listTenantKeys = (key: string, companyId: string) =>
  call<{ keys: ApiKeySummary[] }>(key, `/v1/tenants/${encodeURIComponent(companyId)}/keys`);

export const issueTenantKey = (key: string, companyId: string, role: string) =>
  call<IssuedApiKey>(key, `/v1/tenants/${encodeURIComponent(companyId)}/keys`, {
    method: "POST",
    body: { role },
  });

export const revokeTenantKey = (key: string, companyId: string, keyId: string) =>
  call<{ key_id: string; revoked_at: string }>(
    key,
    `/v1/tenants/${encodeURIComponent(companyId)}/keys/${encodeURIComponent(keyId)}`,
    { method: "DELETE" },
  );
