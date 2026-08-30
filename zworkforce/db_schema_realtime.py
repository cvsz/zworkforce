from __future__ import annotations


DASHBOARD_EVENT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS dashboard_events2(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dashboard_events2_tenant_id
    ON dashboard_events2(tenant_id,id);
"""
