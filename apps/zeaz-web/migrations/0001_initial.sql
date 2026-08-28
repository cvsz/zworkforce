PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS early_access_requests (
  id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE, full_name TEXT NOT NULL,
  company TEXT NOT NULL DEFAULT '', role TEXT NOT NULL DEFAULT '', country TEXT NOT NULL DEFAULT '',
  interest TEXT NOT NULL CHECK (interest IN ('consumer','professional','enterprise','partner','developer')),
  message TEXT NOT NULL DEFAULT '', locale TEXT NOT NULL DEFAULT 'en' CHECK (locale IN ('en','th')),
  source TEXT NOT NULL DEFAULT 'www.zeaz.dev', status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','contacted','qualified','pilot','closed','rejected')),
  marketing_consent INTEGER NOT NULL DEFAULT 0 CHECK (marketing_consent IN (0,1)), privacy_consent INTEGER NOT NULL DEFAULT 1 CHECK (privacy_consent IN (0,1)),
  ip_hash TEXT NOT NULL, user_agent TEXT NOT NULL DEFAULT '', cf_country TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_early_access_status_created ON early_access_requests(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_early_access_interest ON early_access_requests(interest);
CREATE TABLE IF NOT EXISTS lead_submissions (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, email TEXT NOT NULL, ip_hash TEXT NOT NULL, outcome TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_lead_submissions_ip_created ON lead_submissions(ip_hash, created_at DESC);
