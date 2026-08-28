import { randomUUID } from 'node:crypto';
import { createLogger } from '../observability/logger.js';

const TIMEZONE_OFFSETS = {
  'UTC': 0,
  'Asia/Bangkok': 7,
  'Asia/Singapore': 8,
  'America/New_York': -5,
  'America/Los_Angeles': -8,
  'Europe/London': 0,
  'Europe/Paris': 1,
};

class CampaignScheduler {
  constructor(options = {}) {
    this.pool = options.pool || null;
    this.logger = createLogger({ component: 'campaign-scheduler' });
  }

  async getClient() {
    if (!this.pool) {
      throw new Error('PostgreSQL pool is required for campaign scheduler');
    }
    return this.pool.connect();
  }

  async listSchedules(tenantId) {
    if (!tenantId || typeof tenantId !== 'string') {
      throw new TypeError('tenantId is required');
    }

    const client = await this.getClient();
    try {
      const result = await client.query(
        `SELECT id, campaign_id AS "campaignId", rule_type AS "ruleType", cron_expression AS "cronExpression",
          timezone, next_run_at AS "nextRunAt", paused, metadata, created_at AS "createdAt", updated_at AS "updatedAt"
         FROM campaign_schedules
         WHERE tenant_id = $1
         ORDER BY next_run_at ASC`,
        [tenantId]
      );
      return result.rows;
    } finally {
      client.release();
    }
  }

  async getSchedule(tenantId, scheduleId) {
    if (!tenantId || typeof tenantId !== 'string') {
      throw new TypeError('tenantId is required');
    }

    const client = await this.getClient();
    try {
      const result = await client.query(
        `SELECT id, campaign_id AS "campaignId", rule_type AS "ruleType", cron_expression AS "cronExpression",
          timezone, next_run_at AS "nextRunAt", paused, metadata, created_at AS "createdAt", updated_at AS "updatedAt"
         FROM campaign_schedules
         WHERE id = $1 AND tenant_id = $2
         LIMIT 1`,
        [scheduleId, tenantId]
      );
      return result.rows[0] || null;
    } finally {
      client.release();
    }
  }

  async createSchedule(tenantId, input = {}) {
    const campaignId = typeof input.campaignId === 'string' ? input.campaignId.trim() : '';
    if (!campaignId) throw new TypeError('campaignId is required');

    const ruleType = typeof input.ruleType === 'string' ? input.ruleType.trim().toLowerCase() : '';
    if (!['once', 'cron', 'event'].includes(ruleType)) {
      throw new TypeError('ruleType must be once, cron, or event');
    }

    const timezone = typeof input.timezone === 'string' && input.timezone.trim() ? input.timezone.trim() : 'UTC';
    if (!(timezone in TIMEZONE_OFFSETS) && !/^[A-Za-z_]+\/[A-Za-z_]+$/.test(timezone)) {
      throw new TypeError('Invalid timezone');
    }

    const cronExpression = input.cronExpression && typeof input.cronExpression === 'string'
      ? input.cronExpression.trim()
      : null;

    if (ruleType === 'cron' && !cronExpression) {
      throw new TypeError('cronExpression is required for cron ruleType');
    }

    const nextRunAt = input.nextRunAt ? new Date(input.nextRunAt) : new Date();
    if (Number.isNaN(nextRunAt.getTime())) {
      throw new TypeError('nextRunAt must be a valid ISO date');
    }

    const client = await this.getClient();
    try {
      const result = await client.query(
        `INSERT INTO campaign_schedules (tenant_id, campaign_id, rule_type, cron_expression, timezone, next_run_at, metadata)
         VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
         RETURNING id, campaign_id AS "campaignId", rule_type AS "ruleType", cron_expression AS "cronExpression",
           timezone, next_run_at AS "nextRunAt", paused, metadata, created_at AS "createdAt", updated_at AS "updatedAt"`,
        [tenantId, campaignId, ruleType, cronExpression, timezone, nextRunAt, JSON.stringify(input.metadata || {})]
      );
      return result.rows[0];
    } finally {
      client.release();
    }
  }

  async updateNextRun(tenantId, scheduleId, nextRunAt) {
    const client = await this.getClient();
    try {
      const result = await client.query(
        `UPDATE campaign_schedules
         SET next_run_at = $3, updated_at = now()
         WHERE id = $1 AND tenant_id = $2
         RETURNING id, campaign_id AS "campaignId", rule_type AS "ruleType", cron_expression AS "cronExpression",
           timezone, next_run_at AS "nextRunAt", paused, metadata, created_at AS "createdAt", updated_at AS "updatedAt"`,
        [scheduleId, tenantId, nextRunAt]
      );
      return result.rows[0] || null;
    } finally {
      client.release();
    }
  }

  async pauseSchedule(tenantId, scheduleId) {
    if (!tenantId || typeof tenantId !== 'string') {
      throw new TypeError('tenantId is required');
    }

    const client = await this.getClient();
    try {
      const result = await client.query(
        `UPDATE campaign_schedules
         SET paused = true, updated_at = now()
         WHERE id = $1 AND tenant_id = $2
         RETURNING id, campaign_id AS "campaignId", rule_type AS "ruleType", cron_expression AS "cronExpression",
           timezone, next_run_at AS "nextRunAt", paused, metadata, created_at AS "createdAt", updated_at AS "updatedAt"`,
        [scheduleId, tenantId]
      );
      return result.rows[0] || null;
    } finally {
      client.release();
    }
  }

  async resumeSchedule(tenantId, scheduleId) {
    if (!tenantId || typeof tenantId !== 'string') {
      throw new TypeError('tenantId is required');
    }

    const client = await this.getClient();
    try {
      const result = await client.query(
        `UPDATE campaign_schedules
         SET paused = false, updated_at = now()
         WHERE id = $1 AND tenant_id = $2
         RETURNING id, campaign_id AS "campaignId", rule_type AS "ruleType", cron_expression AS "cronExpression",
           timezone, next_run_at AS "nextRunAt", paused, metadata, created_at AS "createdAt", updated_at AS "updatedAt"`,
        [scheduleId, tenantId]
      );
      return result.rows[0] || null;
    } finally {
      client.release();
    }
  }

  async deleteSchedule(tenantId, scheduleId) {
    if (!tenantId || typeof tenantId !== 'string') {
      throw new TypeError('tenantId is required');
    }

    const client = await this.getClient();
    try {
      const result = await client.query(
        'DELETE FROM campaign_schedules WHERE id = $1 AND tenant_id = $2 RETURNING id',
        [scheduleId, tenantId]
      );
      return result.rows.length > 0;
    } finally {
      client.release();
    }
  }

  async getDueSchedules(tenantId) {
    if (!tenantId || typeof tenantId !== 'string') {
      throw new TypeError('tenantId is required');
    }

    const client = await this.getClient();
    try {
      const result = await client.query(
        `SELECT id, campaign_id AS "campaignId", rule_type AS "ruleType", cron_expression AS "cronExpression",
          timezone, next_run_at AS "nextRunAt", paused, metadata, created_at AS "createdAt", updated_at AS "updatedAt"
         FROM campaign_schedules
         WHERE tenant_id = $1 AND paused = false AND next_run_at <= now()
         ORDER BY next_run_at ASC`,
        [tenantId]
      );
      return result.rows;
    } finally {
      client.release();
    }
  }

  convertToUtc(localTime, timezone) {
    const offsetHours = TIMEZONE_OFFSETS[timezone] || 0;
    const [hours, minutes] = localTime.split(':').map(Number);
    const utcHours = ((hours - offsetHours) + 24) % 24;
    return `${String(Math.floor(utcHours)).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
  }

  calculateNextRun(ruleType, cronExpression, timezone, fromDate = new Date()) {
    const base = new Date(fromDate);

    if (ruleType === 'once') {
      return base;
    }

    if (ruleType === 'cron' && cronExpression) {
      const parts = cronExpression.split(' ');
      if (parts.length >= 5) {
        const minute = parts[0] || '0';
        const hour = parts[1] || '0';
        const next = new Date(base);
        next.setHours(Number(hour), Number(minute), 0, 0);
        if (next <= base) {
          next.setDate(next.getDate() + 1);
        }
        return next;
      }
    }

    const next = new Date(base);
    next.setHours(next.getHours() + 1);
    return next;
  }
}

export function createCampaignScheduler(options = {}) {
  return new CampaignScheduler(options);
}
