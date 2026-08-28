CREATE TABLE rate_limit_records (
  key TEXT NOT NULL,
  requested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX rate_limit_records_key_requested_idx ON rate_limit_records (key, requested_at);
