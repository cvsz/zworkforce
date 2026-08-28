ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS audit_events_tenant_actor_fkey;
ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_tenant_user_fkey;
ALTER TABLE consent_records DROP CONSTRAINT IF EXISTS consent_records_tenant_contact_fkey;
ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_tenant_conversation_fkey;
ALTER TABLE conversations DROP CONSTRAINT IF EXISTS conversations_tenant_contact_fkey;
ALTER TABLE user_roles DROP CONSTRAINT IF EXISTS user_roles_tenant_role_fkey;
ALTER TABLE user_roles DROP CONSTRAINT IF EXISTS user_roles_tenant_user_fkey;

ALTER TABLE conversations DROP CONSTRAINT IF EXISTS conversations_tenant_id_id_key;
ALTER TABLE contacts DROP CONSTRAINT IF EXISTS contacts_tenant_id_id_key;
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_tenant_id_id_key;
ALTER TABLE roles DROP CONSTRAINT IF EXISTS roles_tenant_id_id_key;
