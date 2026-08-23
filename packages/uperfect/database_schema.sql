-- U.Perfect Social Commerce OS - PostgreSQL deployment schema
-- This file contains schema and merchant-provided catalogue facts only.
-- Provider credentials, signing values, and account tokens never belong here.

CREATE TABLE IF NOT EXISTS products (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  size TEXT NOT NULL,
  price_thb NUMERIC(12,2),
  description TEXT NOT NULL DEFAULT '',
  seller TEXT NOT NULL DEFAULT '',
  merchant_provided BOOLEAN NOT NULL DEFAULT TRUE,
  available BOOLEAN NOT NULL DEFAULT TRUE,
  stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
  usage TEXT NOT NULL DEFAULT '',
  warning TEXT NOT NULL DEFAULT '',
  allergen_warning TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS product_keywords (
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  keyword TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'alias',
  position INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (product_id, keyword)
);

CREATE TABLE IF NOT EXISTS ingredients (
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  benefit_copy TEXT NOT NULL,
  position INTEGER NOT NULL,
  PRIMARY KEY (product_id, name)
);

CREATE TABLE IF NOT EXISTS product_inci (
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  position INTEGER NOT NULL,
  PRIMARY KEY (product_id, name)
);

CREATE TABLE IF NOT EXISTS promotions (
  id BIGSERIAL PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  minimum_quantity INTEGER NOT NULL CHECK (minimum_quantity > 0),
  bundle_price_thb NUMERIC(12,2) NOT NULL CHECK (bundle_price_thb >= 0),
  original_price_thb NUMERIC(12,2),
  label TEXT NOT NULL,
  shipping_free BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (product_id, minimum_quantity)
);

CREATE TABLE IF NOT EXISTS product_sources (
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  listing_id TEXT PRIMARY KEY,
  source_url TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
  id UUID PRIMARY KEY,
  platform TEXT NOT NULL,
  customer_id TEXT NOT NULL,
  active_product_id TEXT REFERENCES products(id),
  selected_quantity INTEGER,
  current_step TEXT NOT NULL DEFAULT 'greeting',
  human_takeover BOOLEAN NOT NULL DEFAULT FALSE,
  takeover_until TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  UNIQUE (platform, customer_id)
);

CREATE TABLE IF NOT EXISTS messages (
  id UUID PRIMARY KEY,
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  direction TEXT NOT NULL CHECK (direction IN ('inbound','outbound')),
  text TEXT NOT NULL,
  intent TEXT NOT NULL DEFAULT 'fallback',
  automated BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
  id UUID PRIMARY KEY,
  conversation_id UUID REFERENCES conversations(id),
  customer_name TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','awaiting_payment','pending_review','confirmed','fulfilled','cancelled')),
  total_thb NUMERIC(12,2) NOT NULL CHECK (total_thb >= 0),
  payment_reference TEXT,
  address_json JSONB,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
  id BIGSERIAL PRIMARY KEY,
  order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  product_id TEXT NOT NULL REFERENCES products(id),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  unit_price_thb NUMERIC(12,2) NOT NULL CHECK (unit_price_thb >= 0),
  line_total_thb NUMERIC(12,2) NOT NULL CHECK (line_total_thb >= 0)
);

CREATE TABLE IF NOT EXISTS inventory_reservations (
  product_id TEXT PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
  reserved INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0)
);

CREATE TABLE IF NOT EXISTS integrations (
  provider TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK (status IN ('unconfigured','configured','verified','degraded','disabled')),
  webhook_path TEXT NOT NULL,
  last_verified_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS workspace_settings (
  key TEXT PRIMARY KEY,
  value_json JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS webhook_receipts (
  provider TEXT NOT NULL,
  event_id TEXT NOT NULL,
  message_id UUID,
  received_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (provider, event_id)
);

CREATE TABLE IF NOT EXISTS notification_outbox (
  id UUID PRIMARY KEY,
  event_type TEXT NOT NULL,
  destination TEXT NOT NULL,
  body TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending','sent','failed')),
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL,
  sent_at TIMESTAMPTZ,
  locked_until TIMESTAMPTZ,
  locked_by TEXT,
  next_attempt_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_events (
  id UUID PRIMARY KEY,
  event_type TEXT NOT NULL,
  entity_id TEXT,
  actor TEXT NOT NULL,
  details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL
);

INSERT INTO products (id, name, size, price_thb, description, seller, stock, usage, warning)
VALUES
  ('LOE_VITC_SERUM', 'VIT C AURA SERUM เลอ บาย ยู เพอร์เฟค วิต ซี ออร่า เซรั่ม', '200 มิลลิลิตร', 98.00,
   'ผลิตภัณฑ์บำรุงผิวกายจาก Loe by U.PERFECT; ราคาและโปรโมชันมาจาก execution brief และต้องตรวจยืนยันก่อน live checkout',
   'U Perfect นายแม่ปุ๊กกี้', 500, 'ใช้ทาบำรุงผิวกาย', 'หากใช้แล้วมีอาการระคายเคืองควรหยุดใช้และปรึกษาแพทย์'),
  ('MALA_CHILI_OIL', 'น้ำพริกเสือร้องไห้ 1 กระปุก 200 กรัม', '200 กรัม', NULL,
   'พริกน้ำมันรำข้าวใส่ถั่วลายเสือ สูตรต้นตำรับ; ไม่มีส่วนประกอบของเนื้อสัตว์',
   'U Perfect นายแม่ปุ๊กกี้', 100, '', 'เปิดแล้วควรปิดฝาให้สนิท และเก็บในที่แห้ง')
ON CONFLICT (id) DO NOTHING;

INSERT INTO promotions (product_id, minimum_quantity, bundle_price_thb, original_price_thb, label, shipping_free)
VALUES ('LOE_VITC_SERUM', 2, 169.00, 378.00, 'โปร 2 ชิ้น', TRUE)
ON CONFLICT (product_id, minimum_quantity) DO NOTHING;

INSERT INTO product_sources (product_id, listing_id, source_url)
VALUES
  ('LOE_VITC_SERUM', '1736533886654383714', 'https://shop.tiktok.com/th/pdp/1736533886654383714'),
  ('LOE_VITC_SERUM', '1736534222483654242', 'https://shop.tiktok.com/th/pdp/1736534222483654242'),
  ('MALA_CHILI_OIL', '1736721811552831074', 'https://shop.tiktok.com/th/pdp/1736721811552831074')
ON CONFLICT (listing_id) DO NOTHING;

INSERT INTO workspace_settings (key, value_json)
VALUES
  ('store_name', '"U.Perfect"'::jsonb),
  ('store_handle', '"@spookyuperfect"'::jsonb),
  ('facebook_page_url', '"https://www.facebook.com/spookyuperfect"'::jsonb),
  ('timezone', '"Asia/Bangkok"'::jsonb),
  ('default_language', '"th"'::jsonb),
  ('assistant_tone', '"warm"'::jsonb),
  ('autobot_enabled', 'true'::jsonb),
  ('human_takeover_timeout_minutes', '30'::jsonb),
  ('n8n_auto_post_enabled', 'false'::jsonb),
  ('n8n_comment_reply_enabled', 'false'::jsonb),
  ('line_notifications_enabled', 'false'::jsonb),
  ('payment_review_alerts_enabled', 'true'::jsonb),
  ('local_only_mode', 'true'::jsonb),
  ('local_host', '"192.168.74.130"'::jsonb),
  ('local_ai_base_url', '"http://192.168.74.130:11434"'::jsonb),
  ('local_ai_model', '"zCoder:latest"'::jsonb)
ON CONFLICT (key) DO NOTHING;

INSERT INTO integrations (provider, status, webhook_path)
VALUES ('local_ai', 'unconfigured', 'http://192.168.74.130:11434/api/tags')
ON CONFLICT (provider) DO UPDATE SET webhook_path = EXCLUDED.webhook_path;
