CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE commerce_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  external_order_id TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('shopify', 'tiktok', 'lazada', 'shopee', 'zok')),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled', 'refunded', 'processing')),
  total NUMERIC(12,2) NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'USD',
  customer_id UUID,
  order_date TIMESTAMPTZ NOT NULL DEFAULT now(),
  items JSONB NOT NULL DEFAULT '[]'::jsonb,
  shipping_address JSONB DEFAULT '{}'::jsonb,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE TABLE commerce_products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  external_product_id TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('shopify', 'tiktok', 'lazada', 'shopee', 'zok')),
  title TEXT NOT NULL,
  description TEXT DEFAULT '',
  variants JSONB NOT NULL DEFAULT '[]'::jsonb,
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE TABLE commerce_customers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  external_customer_id TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('shopify', 'tiktok', 'lazada', 'shopee', 'zok')),
  email TEXT,
  first_name TEXT,
  last_name TEXT,
  phone TEXT,
  tags JSONB NOT NULL DEFAULT '[]'::jsonb,
  accepts_marketing BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE TABLE attribution_touchpoints (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  contact_id TEXT NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('whatsapp', 'line', 'messenger', 'tiktok', 'shopify', 'email', 'sms', 'web')),
  event_type TEXT NOT NULL DEFAULT 'message',
  campaign_id UUID,
  message_id TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE TABLE order_attributions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  contact_id TEXT NOT NULL,
  order_id TEXT NOT NULL,
  order_value NUMERIC(12,2) NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'USD',
  platform TEXT NOT NULL DEFAULT 'zok',
  order_date TIMESTAMPTZ NOT NULL DEFAULT now(),
  model TEXT NOT NULL DEFAULT 'last_touch' CHECK (model IN ('first_touch', 'last_touch', 'multi_touch_linear')),
  attribution_window_days INTEGER NOT NULL DEFAULT 30,
  touchpoint_count INTEGER NOT NULL DEFAULT 0,
  attribution JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE TABLE reconciliation_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  platform_order JSONB,
  existing_order JSONB,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'matched', 'mismatched', 'duplicate', 'missing', 'resolved', 'failed')),
  mode TEXT NOT NULL DEFAULT 'automatic',
  reconciliation_id UUID,
  differences JSONB NOT NULL DEFAULT '{}'::jsonb,
  resolved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE TABLE integration_status_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  provider TEXT NOT NULL,
  external_id TEXT,
  status TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX commerce_orders_tenant_external_idx ON commerce_orders (tenant_id, platform, external_order_id);
CREATE UNIQUE INDEX commerce_products_tenant_external_idx ON commerce_products (tenant_id, platform, external_product_id);
CREATE UNIQUE INDEX commerce_customers_tenant_external_idx ON commerce_customers (tenant_id, platform, external_customer_id);
CREATE INDEX attribution_touchpoints_tenant_contact_idx ON attribution_touchpoints (tenant_id, contact_id, occurred_at);
CREATE INDEX order_attributions_tenant_idx ON order_attributions (tenant_id, created_at DESC);
CREATE INDEX reconciliation_records_tenant_idx ON reconciliation_records (tenant_id, created_at DESC);

ALTER TABLE commerce_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE commerce_orders FORCE ROW LEVEL SECURITY;
CREATE POLICY commerce_orders_tenant_isolation ON commerce_orders
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE commerce_products ENABLE ROW LEVEL SECURITY;
ALTER TABLE commerce_products FORCE ROW LEVEL SECURITY;
CREATE POLICY commerce_products_tenant_isolation ON commerce_products
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE commerce_customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE commerce_customers FORCE ROW LEVEL SECURITY;
CREATE POLICY commerce_customers_tenant_isolation ON commerce_customers
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE attribution_touchpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE attribution_touchpoints FORCE ROW LEVEL SECURITY;
CREATE POLICY attribution_touchpoints_tenant_isolation ON attribution_touchpoints
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE order_attributions ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_attributions FORCE ROW LEVEL SECURITY;
CREATE POLICY order_attributions_tenant_isolation ON order_attributions
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE reconciliation_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE reconciliation_records FORCE ROW LEVEL SECURITY;
CREATE POLICY reconciliation_records_tenant_isolation ON reconciliation_records
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE integration_status_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_status_logs FORCE ROW LEVEL SECURITY;
CREATE POLICY integration_status_logs_tenant_isolation ON integration_status_logs
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
