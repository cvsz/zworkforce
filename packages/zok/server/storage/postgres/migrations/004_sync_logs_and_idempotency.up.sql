CREATE TABLE sync_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  log_text TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE TABLE zok_cutover_idempotency (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  collection TEXT NOT NULL,
  external_id TEXT NOT NULL,
  migrated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (collection, external_id)
);

CREATE INDEX sync_logs_tenant_idx ON sync_logs (tenant_id);

ALTER TABLE sync_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_logs FORCE ROW LEVEL SECURITY;
CREATE POLICY sync_logs_tenant_isolation ON sync_logs
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
