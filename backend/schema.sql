-- Kernl Database Schema
-- Run this in Supabase SQL editor before starting

CREATE TABLE IF NOT EXISTS companies (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

INSERT INTO companies VALUES ('rivanly-inc', 'Rivanly Inc.', now()) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS skills_files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id TEXT REFERENCES companies(id),
  version TEXT NOT NULL,
  brain_json JSONB NOT NULL,
  graph_json JSONB DEFAULT '{}'::jsonb,
  source_hashes JSONB NOT NULL,
  compiled_at TIMESTAMPTZ DEFAULT now(),
  is_current BOOLEAN DEFAULT false
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_skills_files_current ON skills_files(company_id) WHERE is_current = true;

CREATE TABLE IF NOT EXISTS skills (
  id TEXT NOT NULL,
  company_id TEXT REFERENCES companies(id),
  skills_file_id UUID REFERENCES skills_files(id),
  name TEXT NOT NULL,
  domain TEXT NOT NULL,
  version TEXT NOT NULL,
  confidence FLOAT NOT NULL,
  stale BOOLEAN DEFAULT false,
  review_required BOOLEAN DEFAULT false,
  skill_json JSONB NOT NULL,
  PRIMARY KEY (id, company_id, skills_file_id)
);

CREATE TABLE IF NOT EXISTS source_files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id TEXT REFERENCES companies(id),
  filename TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  uploaded_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS compile_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id TEXT REFERENCES companies(id),
  status TEXT NOT NULL CHECK (status IN ('started','running','complete','error')),
  started_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ,
  duration_ms INTEGER,
  result_version TEXT,
  error_detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_skills_files_company ON skills_files(company_id, compiled_at DESC);
CREATE INDEX IF NOT EXISTS idx_skills_company ON skills(company_id);

-- Phase 2: Operational Entities

CREATE TABLE IF NOT EXISTS operational_entities (
  id TEXT NOT NULL,
  company_id TEXT REFERENCES companies(id),
  skills_file_id UUID REFERENCES skills_files(id),
  entity_type TEXT NOT NULL,
  properties JSONB NOT NULL,
  confidence FLOAT NOT NULL DEFAULT 0.5,
  requires_review BOOLEAN DEFAULT false,
  PRIMARY KEY (id, company_id, skills_file_id)
);

CREATE TABLE IF NOT EXISTS relationship_edges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id TEXT REFERENCES companies(id),
  skills_file_id UUID REFERENCES skills_files(id),
  source_entity_id TEXT NOT NULL,
  target_entity_id TEXT NOT NULL,
  relation_type TEXT NOT NULL,
  conditions JSONB DEFAULT '[]'::jsonb,
  confidence FLOAT NOT NULL DEFAULT 0.5,
  source TEXT
);

CREATE INDEX IF NOT EXISTS idx_operational_entities_company ON operational_entities(company_id, entity_type);
CREATE INDEX IF NOT EXISTS idx_relationship_edges_company ON relationship_edges(company_id, relation_type);
CREATE INDEX IF NOT EXISTS idx_relationship_edges_source ON relationship_edges(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationship_edges_target ON relationship_edges(target_entity_id);

-- ===========================================================================
-- V1 "Decision Ledger" tables (2026-07-13). Additive; legacy tables above are
-- retained (skills_files/skills/operational_entities/relationship_edges are
-- frozen as legacy reads after the bundle migration).
-- Semantics contract: backend/ledger, backend/bundle, backend/escalation,
-- backend/replay -- the in-memory stores are the reference implementations;
-- these tables must enforce the same invariants (comments below).
-- ===========================================================================

CREATE TABLE IF NOT EXISTS policy_bundles (
    record_id      UUID PRIMARY KEY,
    company_id     TEXT NOT NULL,
    content_hash   TEXT NOT NULL,             -- sha256:... canonical content
    status         TEXT NOT NULL CHECK (status IN ('draft','published','retired')),
    bundle_json    JSONB NOT NULL,            -- immutable after insert
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by     TEXT NOT NULL,
    published_at   TIMESTAMPTZ,
    published_by   TEXT,
    replay_run_id  UUID,                      -- the run that gated the publish
    signature        TEXT,                    -- Ed25519 sig over content_hash (hex)
    signing_pubkey   TEXT,                    -- Ed25519 public key (hex)
    signature_scheme TEXT                     -- 'ed25519'
);
-- Additive columns for pre-existing deployments (idempotent; no-op if present).
ALTER TABLE policy_bundles ADD COLUMN IF NOT EXISTS signature        TEXT;
ALTER TABLE policy_bundles ADD COLUMN IF NOT EXISTS signing_pubkey   TEXT;
ALTER TABLE policy_bundles ADD COLUMN IF NOT EXISTS signature_scheme TEXT;
-- content-addressed dedup: same content registers once per tenant
CREATE UNIQUE INDEX IF NOT EXISTS idx_bundles_company_hash
    ON policy_bundles(company_id, content_hash);

-- exactly one active bundle per tenant: a pointer table, moved atomically
CREATE TABLE IF NOT EXISTS active_bundles (
    company_id  TEXT PRIMARY KEY,
    record_id   UUID NOT NULL REFERENCES policy_bundles(record_id),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS decision_events (
    event_id         UUID PRIMARY KEY,
    event_type       TEXT NOT NULL CHECK (event_type IN ('decision','adjudication')),
    company_id       TEXT NOT NULL,
    workflow         TEXT NOT NULL,
    idempotency_key  TEXT NOT NULL,
    bundle_hash      TEXT NOT NULL,
    outcome_kind     TEXT NOT NULL,            -- extracted for filtering
    linked_event_id  UUID,
    created_at       TIMESTAMPTZ NOT NULL,
    seq              BIGINT NOT NULL,          -- per-company stream position
    prev_event_hash  TEXT,
    event_hash       TEXT NOT NULL,
    event_json       JSONB NOT NULL            -- the sealed event, verbatim source
                                               -- of truth for reconstruction +
                                               -- hash verification
);
-- append-only enforced AT THE DATABASE for every role (owner included):
--   * UPDATE is ALWAYS forbidden -- history is never edited in place.
--   * DELETE is forbidden too, EXCEPT during a sanctioned whole-tenant purge,
--     which announces itself by setting the session variable
--     `kernl.purging_tenant` to the exact company_id being removed. This is
--     the retention policy's "discard the entire logbook" case: removing a
--     whole append-only stream as a unit is NOT the same as tearing one page
--     out of a live stream. The row's own company_id must match the declared
--     purge target, so a purge of tenant A can never delete tenant B's rows.
CREATE OR REPLACE FUNCTION forbid_history_mutation() RETURNS trigger AS $$
DECLARE
    purging TEXT := current_setting('kernl.purging_tenant', true);
BEGIN
    IF TG_OP = 'DELETE' AND purging IS NOT NULL AND purging = OLD.company_id THEN
        RETURN OLD;  -- sanctioned whole-tenant purge of THIS tenant's stream
    END IF;
    RAISE EXCEPTION 'decision_events is append-only (CLAUDE.md rule 3): % blocked', TG_OP;
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS decision_events_append_only ON decision_events;
CREATE TRIGGER decision_events_append_only
    BEFORE UPDATE OR DELETE ON decision_events
    FOR EACH ROW EXECUTE FUNCTION forbid_history_mutation();
-- idempotency: atomic via unique constraint (the store relies on it)
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_idempotency
    ON decision_events(company_id, idempotency_key);
-- single-writer chain: seq is unique per company; prev_event_hash must equal
-- the event_hash at seq-1 (verified by backend.ledger verify_chain)
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_company_seq
    ON decision_events(company_id, seq);
CREATE INDEX IF NOT EXISTS idx_events_company_time
    ON decision_events(company_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_workflow
    ON decision_events(company_id, workflow);
CREATE INDEX IF NOT EXISTS idx_events_outcome
    ON decision_events(company_id, outcome_kind);

CREATE TABLE IF NOT EXISTS escalations (
    escalation_id      UUID PRIMARY KEY,
    company_id         TEXT NOT NULL,
    workflow           TEXT NOT NULL,
    decision_event_id  UUID NOT NULL REFERENCES decision_events(event_id),
    reason             TEXT NOT NULL CHECK (reason IN
        ('missing_facts','no_matching_policy','conflict',
         'policy_directed','authority_required')),
    detail_json        JSONB NOT NULL DEFAULT '{}',
    status             TEXT NOT NULL DEFAULT 'open'
                       CHECK (status IN ('open','resolved')),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolution_json    JSONB                   -- Resolution, incl. adjudication id
);
-- exactly one escalation per decision (the store's add() contract)
CREATE UNIQUE INDEX IF NOT EXISTS idx_escalations_decision
    ON escalations(company_id, decision_event_id);
CREATE INDEX IF NOT EXISTS idx_escalations_open
    ON escalations(company_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS golden_cases (
    case_id      TEXT NOT NULL,
    company_id   TEXT NOT NULL,
    workflow     TEXT NOT NULL,
    facts_json   JSONB NOT NULL,
    expected_json JSONB NOT NULL,
    provenance   TEXT NOT NULL,               -- doc ref or adjudication:<event_id>
    synthetic    BOOLEAN NOT NULL DEFAULT TRUE,  -- [synthetic] labeling is enforced
    notes        TEXT NOT NULL DEFAULT '',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id, case_id)
);

CREATE TABLE IF NOT EXISTS replay_runs (
    run_id                 UUID PRIMARY KEY,
    company_id             TEXT NOT NULL,
    candidate_bundle_hash  TEXT NOT NULL,
    reference_bundle_hash  TEXT,
    case_set_hash          TEXT NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    summary_json           JSONB NOT NULL,
    results_json           JSONB NOT NULL,
    acknowledged_by        TEXT,
    acknowledged_at        TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_replays_candidate
    ON replay_runs(company_id, candidate_bundle_hash, created_at DESC);

CREATE TABLE IF NOT EXISTS api_keys (
    key_id      TEXT PRIMARY KEY,
    key_hash    TEXT NOT NULL,                -- sha256 of the key; never plaintext
    company_id  TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('owner','approver','agent')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_api_keys_company ON api_keys(company_id);

-- Step 6: extraction demoted to draft-proposer ------------------------------
CREATE TABLE IF NOT EXISTS policy_drafts (
    draft_id         TEXT NOT NULL,
    company_id       TEXT NOT NULL,
    compile_job_id   TEXT,                     -- provenance: which run proposed it
    source_skill_id  TEXT NOT NULL,
    proposed_json    JSONB NOT NULL,           -- Policy-shaped, possibly incomplete
    issues_json      JSONB NOT NULL,           -- why it cannot publish yet
    evidence_texts   JSONB NOT NULL DEFAULT '[]',
    publishable      BOOLEAN NOT NULL DEFAULT FALSE,
    status           TEXT NOT NULL DEFAULT 'pending_review'
                     CHECK (status IN ('pending_review','accepted','rejected')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id, draft_id, created_at)
);
CREATE INDEX IF NOT EXISTS idx_drafts_pending
    ON policy_drafts(company_id, status, created_at DESC);

-- W8 surfacing: compile runs carry visible warnings
ALTER TABLE compile_runs ADD COLUMN IF NOT EXISTS warnings JSONB;

-- Onboarding: immutable source snapshots that evidence spans cite into ---------
-- A snapshot is the frozen bytes of an uploaded document. Its content hash is
-- the source_version an Evidence span references; grounding verifies the
-- selected span's bytes against this text (rule 2: no uncited norm).
CREATE TABLE IF NOT EXISTS source_snapshots (
    source_id     TEXT NOT NULL,                -- content-addressed id (sha256 prefix)
    company_id    TEXT NOT NULL,
    filename      TEXT NOT NULL,
    content_hash  TEXT NOT NULL,                -- sha256 of the raw text bytes
    content       TEXT NOT NULL,                -- the frozen document text
    byte_length   INTEGER NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id, source_id)
);
CREATE INDEX IF NOT EXISTS idx_sources_company
    ON source_snapshots(company_id, created_at DESC);

-- Onboarding drafts are richer than the extraction-only policy_drafts table:
-- they carry the full editable proposed policy plus grounded evidence. Kept as
-- a separate table so the extraction proposer (policy_drafts) stays untouched.
CREATE TABLE IF NOT EXISTS onboarding_drafts (
    draft_id       TEXT NOT NULL,
    company_id     TEXT NOT NULL,
    proposed_json  JSONB NOT NULL,              -- full editable Policy-shaped JSON
    evidence_json  JSONB NOT NULL DEFAULT '[]', -- grounded, verified Evidence spans
    origin         TEXT NOT NULL DEFAULT 'authored'
                   CHECK (origin IN ('authored','extracted')),
    source_skill_id TEXT,                       -- provenance when extracted
    status         TEXT NOT NULL DEFAULT 'draft'
                   CHECK (status IN ('draft','accepted','rejected')),
    publishable    BOOLEAN NOT NULL DEFAULT FALSE,
    issues_json    JSONB NOT NULL DEFAULT '[]',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id, draft_id)
);
CREATE INDEX IF NOT EXISTS idx_onboarding_drafts
    ON onboarding_drafts(company_id, status, updated_at DESC);
