-- Run these in Supabase SQL editor before starting

CREATE TABLE companies (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  industry TEXT,
  company_size TEXT,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

INSERT INTO companies VALUES ('rivanly-inc', 'Rivanly Inc.', now());

CREATE TABLE skills_files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id TEXT REFERENCES companies(id),
  version TEXT NOT NULL,
  brain_json JSONB NOT NULL,
  source_hashes JSONB NOT NULL,
  compiled_at TIMESTAMPTZ DEFAULT now(),
  is_current BOOLEAN DEFAULT false
);

CREATE UNIQUE INDEX idx_skills_files_current ON skills_files(company_id) WHERE is_current = true;

CREATE TABLE skills (
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

CREATE TABLE source_files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id TEXT REFERENCES companies(id),
  filename TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  uploaded_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE compile_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id TEXT REFERENCES companies(id),
  status TEXT NOT NULL CHECK (status IN ('started','running','complete','error')),
  started_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ,
  duration_ms INTEGER,
  result_version TEXT,
  error_detail TEXT
);

CREATE INDEX idx_skills_files_company ON skills_files(company_id, compiled_at DESC);
CREATE INDEX idx_skills_company ON skills(company_id);
