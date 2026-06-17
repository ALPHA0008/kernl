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
