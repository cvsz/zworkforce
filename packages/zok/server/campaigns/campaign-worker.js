import { randomUUID } from 'node:crypto';
import { createCampaignExecutor } from './campaign-executor.js';
import { createLogger } from '../observability/logger.js';

const DEFAULT_CONCURRENCY = 4;
const POLL_INTERVAL_MS = 2_000;
const RETRY_BASE_DELAY_MS = 1_000;
const MAX_RETRY_DELAY_MS = 16_000;

class CampaignWorker {
  constructor(options = {}) {
    this.pool = options.pool || null;
    this.concurrency = options.concurrency || DEFAULT_CONCURRENCY;
    this.pollIntervalMs = options.pollIntervalMs || POLL_INTERVAL_MS;
    this.executor = options.executor || createCampaignExecutor();
    this.logger = createLogger({ component: 'campaign-worker' });
    this.running = false;
    this.timer = null;
    this.activeCount = 0;
    this.workers = [];
    this.healthy = true;
  }

  async start() {
    if (this.running) return;
    this.running = true;
    this.healthy = true;
    this.logger.info('campaign worker starting', { concurrency: this.concurrency });

    for (let i = 0; i < this.concurrency; i += 1) {
      this.workers.push(this.runWorkerLoop(i));
    }

    this.timer = setInterval(() => this.checkHealth(), 30_000);
    this.logger.info('campaign worker started');
  }

  async stop() {
    this.running = false;
    this.healthy = false;

    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }

    await Promise.all(this.workers);
    this.workers = [];
    this.logger.info('campaign worker stopped');
  }

  isHealthy() {
    return this.healthy && this.running;
  }

  getActiveCount() {
    return this.activeCount;
  }

  getQueueDepth() {
    return this.workers.length;
  }

  async runWorkerLoop(workerIndex) {
    while (this.running) {
      try {
        await this.processNextExecution();
      } catch (error) {
        this.logger.error('worker loop error', { workerIndex, error: error.message });
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }
  }

  async processNextExecution() {
    const execution = await this.claimNextExecution();
    if (!execution) {
      await new Promise(resolve => setTimeout(resolve, this.pollIntervalMs));
      return;
    }

    this.activeCount += 1;
    try {
      const result = await this.executeClaimed(execution);
      await this.completeExecution(execution.id, result);
    } catch (error) {
      this.logger.error('execution processing error', { executionId: execution.id, error: error.message });
      await this.failExecution(execution.id, error.message);
    } finally {
      this.activeCount -= 1;
    }
  }

  async claimNextExecution() {
    if (!this.pool) return null;

    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');

      const claimed = await client.query(
        `UPDATE campaign_executions
         SET status = 'running', attempt = attempt + 1, updated_at = now()
         WHERE id = (
           SELECT id FROM campaign_executions
           WHERE status = 'pending' AND scheduled_at <= now() AND attempt < max_attempts
           ORDER BY scheduled_at ASC, id ASC
           LIMIT 1
           FOR UPDATE SKIP LOCKED
         )
         RETURNING id, tenant_id AS "tenantId", campaign_id AS "campaignId", contact_id AS "contactId",
           action_type AS "actionType", payload, attempt, max_attempts`,
      );

      if (claimed.rows.length === 0) {
        await client.query('ROLLBACK');
        return null;
      }

      await client.query('COMMIT');
      return claimed.rows[0];
    } catch (error) {
      await client.query('ROLLBACK').catch(() => {});
      this.logger.error('claim execution failed', { error: error.message });
      return null;
    } finally {
      client.release();
    }
  }

  async executeClaimed(execution) {
    const { id: executionId, tenantId, campaignId, contactId, actionType, payload, attempt, maxAttempts } = execution;

    const result = await this.executor.executeAction({
      type: actionType,
      channel: payload.channel,
      contactId,
      campaignId,
      payload: payload.data || {},
      tenantId,
    });

    if (result.status === 'completed') {
      this.logger.info('execution completed', { executionId, campaignId, contactId, attempt });
      return { status: 'completed', result: result.result };
    }

    if (result.status === 'skipped') {
      this.logger.warn('execution skipped', { executionId, reason: result.reason });
      return { status: 'skipped', reason: result.reason };
    }

    if (result.status === 'failed' && attempt >= maxAttempts) {
      this.logger.warn('execution exhausted retries', { executionId, campaignId, contactId, attempt });
      await this.moveToDeadLetter(executionId, campaignId, contactId, tenantId, result.error, payload);
      return { status: 'dead_letter', error: result.error };
    }

    this.logger.warn('execution failed, will retry', { executionId, error: result.error, attempt });
    return { status: 'failed', error: result.error };
  }

  async completeExecution(executionId, result) {
    if (!this.pool) return;

    const client = await this.pool.connect();
    try {
      if (result.status === 'completed') {
        await client.query(
          `UPDATE campaign_executions
           SET status = 'completed', executed_at = now(), completed_at = now(), updated_at = now(), metadata = metadata || $3::jsonb
           WHERE id = $1`,
          [executionId, result.status, JSON.stringify({ result: result.result || {} })]
        );
      } else if (result.status === 'skipped') {
        await client.query(
          `UPDATE campaign_executions
           SET status = 'skipped', last_error = $2, executed_at = now(), updated_at = now()
           WHERE id = $1`,
          [executionId, result.reason || 'skipped']
        );
      } else {
        await client.query(
          `UPDATE campaign_executions
           SET status = 'pending', last_error = $2, scheduled_at = now() + interval '1 minute' * (attempt + 1), updated_at = now()
           WHERE id = $1`,
          [executionId, result.error]
        );
      }
    } finally {
      client.release();
    }
  }

  async failExecution(executionId, errorMessage) {
    if (!this.pool) return;

    const client = await this.pool.connect();
    try {
      await client.query(
        `UPDATE campaign_executions
         SET status = 'pending', last_error = $2, scheduled_at = now() + interval '1 minute' * LEAST(attempt + 1, 10), updated_at = now()
         WHERE id = $1`,
        [executionId, errorMessage]
      );
    } finally {
      client.release();
    }
  }

  async moveToDeadLetter(executionId, campaignId, contactId, tenantId, error, payload) {
    if (!this.pool) return;

    const client = await this.pool.connect();
    try {
      await client.query(
        `INSERT INTO dead_letter_queue (tenant_id, campaign_id, contact_id, reason, payload, retry_count, last_error)
         SELECT tenant_id, campaign_id, contact_id, 'max_retries_exceeded', payload, attempt, $2
         FROM campaign_executions
         WHERE id = $1
         ON CONFLICT DO NOTHING`,
        [executionId, error]
      );

      await client.query(
        `UPDATE campaign_executions
         SET status = 'failed', last_error = $2, completed_at = now(), updated_at = now()
         WHERE id = $1`,
        [executionId, error]
      );
    } finally {
      client.release();
    }
  }

  async checkHealth() {
    if (!this.running) return;

    let dbHealthy = true;
    if (this.pool) {
      try {
        const client = await this.pool.connect();
        await client.query('SELECT 1');
        client.release();
      } catch {
        dbHealthy = false;
      }
    }

    this.healthy = dbHealthy;
    if (!dbHealthy) {
      this.logger.warn('campaign worker health check failed - database unreachable');
    }
  }

  async requeueDeadLetter(tenantId, campaignId, contactId) {
    if (!this.pool) return false;

    const client = await this.pool.connect();
    try {
      const dead = await client.query(
        `SELECT id FROM dead_letter_queue
         WHERE tenant_id = $1 AND campaign_id = $2 AND contact_id = $3
         LIMIT 1`,
        [tenantId, campaignId, contactId]
      );

      if (dead.rows.length === 0) return false;

      await client.query('DELETE FROM dead_letter_queue WHERE id = $1', [dead.rows[0].id]);

      await client.query(
        `INSERT INTO campaign_executions (tenant_id, campaign_id, contact_id, action_type, payload, status, scheduled_at)
         SELECT tenant_id, campaign_id, contact_id, action_type, payload, 'pending', now()
         FROM dead_letter_queue
         WHERE id = $1`,
        [dead.rows[0].id]
      );

      return true;
    } finally {
      client.release();
    }
  }
}

export function createCampaignWorker(options = {}) {
  return new CampaignWorker(options);
}
