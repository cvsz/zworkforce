-- Additive PostgreSQL parity for the SQLite v2 outbox migration.
CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE notification_outbox
  ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS locked_by TEXT,
  ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ;

INSERT INTO schema_migrations(version)
VALUES (1), (2)
ON CONFLICT (version) DO NOTHING;
