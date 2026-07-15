/** TypeScript mirrors of the /v1 API JSON shapes (backend pydantic models).
 *  Source of truth: backend/runtime/evaluator.py, backend/ledger/events.py,
 *  backend/escalation/service.py, backend/replay/engine.py,
 *  backend/bundle/schema.py + lifecycle.py, backend/v1_api.py. */

export type Scalar = string | number | boolean;

export type OutcomeKind = "approve" | "deny" | "route" | "escalate";

export type EscalationReason =
  | "missing_facts"
  | "conflict"
  | "no_matching_policy"
  | "policy_directed"
  | "authority_required";

export interface Principal {
  company_id: string;
  role: "owner" | "approver" | "agent";
  key_id: string;
}

// ---------------------------------------------------------------- bundle IR

export interface Condition {
  field: string;
  operator: string;
  value: Scalar;
  value_type: "string" | "number" | "boolean";
}

export interface Evidence {
  source_id: string;
  source_version: string;
  span_start: number;
  span_end: number;
  excerpt: string;
}

export interface Effect {
  kind: OutcomeKind;
  action: string;
}

export interface Authority {
  approval_required: boolean;
  approver_role: string | null;
}

export interface Policy {
  id: string;
  workflow: string;
  effect: Effect;
  priority: number;
  conditions: Condition[];
  authority?: Authority;
  evidence: Evidence[];
  overrides: string[];
  unconditional_ack: boolean;
  rationale: string;
}

export interface FactSpec {
  name: string;
  value_type: "string" | "number" | "boolean";
  description: string;
  default: Scalar | null;
}

export interface WorkflowSpec {
  name: string;
  facts: FactSpec[];
  description: string;
}

export interface Bundle {
  schema_version: string;
  company_id: string;
  workflows: WorkflowSpec[];
  policies: Policy[];
}

export type BundleStatus = "draft" | "published" | "superseded";

export interface BundleSummary {
  record_id: string;
  content_hash: string;
  status: BundleStatus;
  created_at: string;
  published_at: string | null;
  policy_count: number;
}

export interface ActiveBundle {
  record_id: string;
  content_hash: string;
  bundle: Bundle;
}

// ------------------------------------------------------------------- trace

export interface ConditionResult {
  field: string;
  operator: string;
  expected: Scalar;
  actual: Scalar | null;
  result: "pass" | "fail" | "missing";
}

export interface PolicyEvaluation {
  policy_id: string;
  priority: number;
  specificity: number;
  status: "matched" | "failed" | "undeterminable";
  conditions: ConditionResult[];
  missing_fields: string[];
}

export interface Elimination {
  policy_id: string;
  eliminated_by: string;
  rule: "overrides" | "specificity" | "priority";
}

export interface PrecedenceTrace {
  applied_rules: string[];
  winner: string | null;
  eliminated: Elimination[];
  tie_between: string[];
  dominance_blocked_by: string[];
}

export interface Outcome {
  kind: OutcomeKind;
  action: string | null;
  policy_id: string | null;
  approval_required: boolean;
  approver_role: string | null;
  escalation_reason: EscalationReason | null;
  missing_facts: string[];
  conflict_between: string[];
}

export interface Trace {
  trace_version: string;
  evaluator_version: string;
  workflow: string;
  facts_supplied: Record<string, unknown>;
  facts_effective: Record<string, Scalar>;
  facts_ignored: string[];
  defaults_applied: string[];
  policies: PolicyEvaluation[];
  precedence: PrecedenceTrace;
}

// ------------------------------------------------------------------ ledger

export interface Actor {
  type: "human" | "agent" | "service";
  id: string;
  api_key_id: string | null;
}

export interface DecisionEvent {
  event_id: string;
  event_type: "decision" | "adjudication";
  company_id: string;
  workflow: string;
  actor: Actor;
  idempotency_key: string;
  facts: Record<string, unknown>;
  outcome: Outcome;
  trace: Trace;
  bundle_hash: string;
  linked_event_id: string | null;
  created_at: string;
  prev_event_hash: string | null;
  event_hash: string;
}

export interface EvaluateResponse {
  decision_id: string;
  created: boolean;
  outcome: Outcome;
  bundle_hash: string;
  escalation_id: string | null;
}

export interface ChainVerify {
  chain_valid: boolean;
  chain_head: string | null;
}

// -------------------------------------------------------------- escalation

export type EscalationStatus = "open" | "resolved";

export interface Resolution {
  chosen_action: string;
  outcome_kind: string;
  rationale: string;
  resolver: Actor;
  adjudication_event_id: string;
  resolved_at: string;
  promoted_to_golden: boolean;
}

export interface Escalation {
  escalation_id: string;
  company_id: string;
  workflow: string;
  decision_event_id: string;
  reason: EscalationReason;
  detail: Record<string, unknown>;
  status: EscalationStatus;
  created_at: string;
  resolution: Resolution | null;
}

// ------------------------------------------------------------------ replay

export interface CaseResult {
  case_id: string;
  workflow: string;
  candidate_kind: string | null;
  candidate_action: string | null;
  candidate_policy_id: string | null;
  expected_kind: string | null;
  expected_action: string | null;
  reference_kind: string | null;
  reference_action: string | null;
  golden_pass: boolean | null;
  flipped: boolean | null;
  error: string | null;
}

export interface ReplaySummary {
  total: number;
  golden_passed: number;
  golden_failed: number;
  flips: number;
  new_escalations: number;
  errors: number;
}

export interface ReplayRun {
  run_id: string;
  company_id: string;
  candidate_bundle_hash: string;
  reference_bundle_hash: string | null;
  case_set_hash: string;
  created_at: string;
  summary: ReplaySummary;
  results: CaseResult[];
  acknowledged_by: string | null;
  acknowledged_at: string | null;
}

export interface ReplayRunSummary {
  run_id: string;
  candidate_bundle_hash: string;
  created_at: string;
  summary: ReplaySummary;
  acknowledged_by: string | null;
}

// ------------------------------------------------------------ cases/drafts

export interface GoldenCase {
  case_id: string;
  company_id: string;
  workflow: string;
  facts: Record<string, unknown>;
  expected: { kind: string; action: string | null; escalation_reason: string | null };
  provenance: string;
  synthetic: boolean;
  notes: string;
}

export interface PolicyDraft {
  draft_id: string;
  compile_job_id: string | null;
  source_skill_id: string | null;
  proposed_json: Record<string, unknown>;
  issues_json: string[];
  evidence_texts: string[];
  publishable: boolean;
  status: string;
  created_at: string;
}

// --------------------------------------------------------------- onboarding

export interface SourceSummary {
  source_id: string;
  filename: string;
  content_hash: string;
  byte_length: number;
  created_at: string;
}

export interface SourceSnapshot extends SourceSummary {
  company_id: string;
  content: string;
}

export interface OnboardingDraft {
  draft_id: string;
  company_id: string;
  proposed_json: Policy; // editable Policy-shaped JSON
  evidence_json: Evidence[]; // grounded verified spans
  origin: "authored" | "extracted";
  source_skill_id: string | null;
  status: "draft" | "accepted" | "rejected";
  publishable: boolean;
  issues_json: string[];
  created_at: string;
  updated_at: string;
}

export interface ProvisionResult {
  company_id: string;
  name: string;
  owner_api_key: string; // shown once
}

export interface AssembleResult {
  record_id: string;
  content_hash: string;
  status: string;
  policy_count: number;
  workflow_count: number;
}
