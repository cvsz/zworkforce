CREATE TABLE webhook_idempotency (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key TEXT NOT NULL UNIQUE,
  provider TEXT NOT NULL,
  event_type TEXT NOT NULL,
  contact_id TEXT NOT NULL,
  processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX webhook_idempotency_key_idx ON webhook_idempotency (key);
CREATE INDEX webhook_idempotency_expires_idx ON webhook_idempotency (expires_at);
