CREATE TABLE ai_config_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  version INTEGER NOT NULL,
  config JSONB NOT NULL,
  risk_level TEXT NOT NULL DEFAULT 'low' CHECK (risk_level IN ('low', 'medium', 'high')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  UNIQUE (tenant_id, version)
);

CREATE TABLE ai_telemetry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  request_id TEXT NOT NULL,
  user_id UUID,
  model TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  response_hash TEXT NOT NULL,
  latency_ms INTEGER NOT NULL,
  tokens_used INTEGER NOT NULL,
  approval_status TEXT NOT NULL DEFAULT 'approved' CHECK (approval_status IN ('pending', 'approved', 'rejected', 'auto_approved')),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE TABLE ai_approvals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  request_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  risk_level TEXT NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'expired')),
  payload JSONB NOT NULL,
  approved_by UUID,
  approved_at TIMESTAMPTZ,
  rejected_by UUID,
  rejected_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (rejected_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX ai_config_versions_tenant_idx ON ai_config_versions (tenant_id, version);
CREATE INDEX ai_telemetry_tenant_created_idx ON ai_telemetry (tenant_id, created_at DESC);
CREATE INDEX ai_approvals_tenant_status_idx ON ai_approvals (tenant_id, status, expires_at);
