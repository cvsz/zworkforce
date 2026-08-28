DROP INDEX IF EXISTS campaign_schedules_next_run_idx;
DROP INDEX IF EXISTS dead_letter_queue_tenant_campaign_idx;
DROP INDEX IF EXISTS campaign_executions_scheduled_idx;
DROP INDEX IF EXISTS campaign_executions_tenant_campaign_idx;
DROP TABLE IF EXISTS campaign_schedules;
DROP TABLE IF EXISTS dead_letter_queue;
DROP TABLE IF EXISTS campaign_executions;

ALTER TABLE campaigns DROP CONSTRAINT IF EXISTS campaigns_status_check;
ALTER TABLE campaigns ADD CONSTRAINT campaigns_status_check CHECK (status IN ('draft', 'scheduled', 'running', 'completed', 'cancelled'));
