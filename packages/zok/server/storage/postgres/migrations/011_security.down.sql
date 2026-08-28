ALTER TABLE integrations DROP CONSTRAINT IF EXISTS integrations_tenant_id_secret_id_fkey;
ALTER TABLE integrations DROP COLUMN IF EXISTS secret_id;
ALTER TABLE integrations DROP COLUMN IF EXISTS credentials_encrypted;
ALTER TABLE integrations DROP COLUMN IF EXISTS api_key_prefix;
ALTER TABLE integrations DROP COLUMN IF EXISTS api_key_hash;

DROP POLICY IF EXISTS secret_access_logs_tenant_isolation ON secret_access_logs;
ALTER TABLE secret_access_logs NO FORCE ROW LEVEL SECURITY;
ALTER TABLE secret_access_logs DISABLE ROW LEVEL SECURITY;
DROP TABLE IF EXISTS secret_access_logs CASCADE;

DROP POLICY IF EXISTS secrets_tenant_isolation ON secrets;
ALTER TABLE secrets NO FORCE ROW LEVEL SECURITY;
ALTER TABLE secrets DISABLE ROW LEVEL SECURITY;
DROP TABLE IF EXISTS secrets CASCADE;

DROP POLICY IF EXISTS api_keys_tenant_isolation ON api_keys;
ALTER TABLE api_keys NO FORCE ROW LEVEL SECURITY;
ALTER TABLE api_keys DISABLE ROW LEVEL SECURITY;
DROP TABLE IF EXISTS api_keys CASCADE;
