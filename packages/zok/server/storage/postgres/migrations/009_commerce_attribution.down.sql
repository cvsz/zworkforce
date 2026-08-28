DROP POLICY IF EXISTS commerce_orders_tenant_isolation ON commerce_orders;
DROP POLICY IF EXISTS commerce_products_tenant_isolation ON commerce_products;
DROP POLICY IF EXISTS commerce_customers_tenant_isolation ON commerce_customers;
DROP POLICY IF EXISTS attribution_touchpoints_tenant_isolation ON attribution_touchpoints;
DROP POLICY IF EXISTS order_attributions_tenant_isolation ON order_attributions;
DROP POLICY IF EXISTS reconciliation_records_tenant_isolation ON reconciliation_records;
DROP POLICY IF EXISTS integration_status_logs_tenant_isolation ON integration_status_logs;

DROP TABLE IF EXISTS commerce_orders CASCADE;
DROP TABLE IF EXISTS commerce_products CASCADE;
DROP TABLE IF EXISTS commerce_customers CASCADE;
DROP TABLE IF EXISTS attribution_touchpoints CASCADE;
DROP TABLE IF EXISTS order_attributions CASCADE;
DROP TABLE IF EXISTS reconciliation_records CASCADE;
DROP TABLE IF EXISTS integration_status_logs CASCADE;
