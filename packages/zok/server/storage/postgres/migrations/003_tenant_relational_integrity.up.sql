-- Ensure related rows belong to the same tenant even if an application bug
-- supplies a globally valid object id from another tenant.

ALTER TABLE roles
  ADD CONSTRAINT roles_tenant_id_id_key UNIQUE (tenant_id, id);
ALTER TABLE users
  ADD CONSTRAINT users_tenant_id_id_key UNIQUE (tenant_id, id);
ALTER TABLE contacts
  ADD CONSTRAINT contacts_tenant_id_id_key UNIQUE (tenant_id, id);
ALTER TABLE conversations
  ADD CONSTRAINT conversations_tenant_id_id_key UNIQUE (tenant_id, id);

ALTER TABLE user_roles
  ADD CONSTRAINT user_roles_tenant_user_fkey
  FOREIGN KEY (tenant_id, user_id) REFERENCES users (tenant_id, id) ON DELETE CASCADE;
ALTER TABLE user_roles
  ADD CONSTRAINT user_roles_tenant_role_fkey
  FOREIGN KEY (tenant_id, role_id) REFERENCES roles (tenant_id, id) ON DELETE CASCADE;

ALTER TABLE conversations
  ADD CONSTRAINT conversations_tenant_contact_fkey
  FOREIGN KEY (tenant_id, contact_id) REFERENCES contacts (tenant_id, id);

ALTER TABLE messages
  ADD CONSTRAINT messages_tenant_conversation_fkey
  FOREIGN KEY (tenant_id, conversation_id)
  REFERENCES conversations (tenant_id, id) ON DELETE CASCADE;

ALTER TABLE consent_records
  ADD CONSTRAINT consent_records_tenant_contact_fkey
  FOREIGN KEY (tenant_id, contact_id) REFERENCES contacts (tenant_id, id) ON DELETE CASCADE;

ALTER TABLE sessions
  ADD CONSTRAINT sessions_tenant_user_fkey
  FOREIGN KEY (tenant_id, user_id) REFERENCES users (tenant_id, id) ON DELETE CASCADE;

ALTER TABLE audit_events
  ADD CONSTRAINT audit_events_tenant_actor_fkey
  FOREIGN KEY (tenant_id, actor_user_id) REFERENCES users (tenant_id, id);
