#!/usr/bin/env node
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createPostgresPool, createPostgresStorage } from '../server/storage/postgres-storage.js';
import { preflightLegacyChatCutover } from '../server/storage/postgres/chat-cutover-rehearsal.js';
import { importLegacyChats } from '../server/storage/postgres/legacy-chat-import.js';
import { createCampaignsRepository } from '../server/storage/postgres/campaigns-repository.js';
import { createIntegrationsRepository } from '../server/storage/postgres/integrations-repository.js';
import { createAiConfigRepository } from '../server/storage/postgres/ai-config-repository.js';
import { createFlowNodesRepository } from '../server/storage/postgres/flow-nodes-repository.js';
import { createHash } from 'node:crypto';

const COLLECTIONS = ['chats', 'campaigns', 'integrations', 'aiConfig', 'flowNodes', 'syncLogs'];

function parseArgs(argv) {
  const args = new Map();
  const booleanFlags = new Set(['--apply']);
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith('--')) throw new TypeError(`Unexpected argument: ${token}`);
    if (booleanFlags.has(token)) {
      args.set(token, true);
      continue;
    }
    const value = argv[index + 1];
    if (!value || value.startsWith('--')) throw new TypeError(`Missing value for ${token}`);
    args.set(token, value);
    index += 1;
  }
  return args;
}

function required(value, name) {
  if (typeof value !== 'string' || !value.trim()) throw new TypeError(`${name} is required`);
  return value.trim();
}

function normaliseChat(chat) {
  if (!chat || typeof chat !== 'object') return null;
  return {
    id: typeof chat.id === 'number' ? chat.id : null,
    name: typeof chat.name === 'string' ? chat.name : null,
    channel: typeof chat.channel === 'string' ? chat.channel : null,
    messages: Array.isArray(chat.messages) ? chat.messages.map(m => ({
      sender: typeof m.sender === 'string' ? m.sender : null,
      text: typeof m.text === 'string' ? m.text : null,
    })) : [],
  };
}

function normaliseCampaign(campaign) {
  if (!campaign || typeof campaign !== 'object') return null;
  return {
    name: typeof campaign.name === 'string' ? campaign.name : null,
    status: typeof campaign.status === 'string' ? campaign.status : null,
    channel: typeof campaign.channel === 'string' ? campaign.channel : null,
    target: typeof campaign.target === 'string' ? campaign.target : null,
    recipients: typeof campaign.recipients === 'number' ? campaign.recipients : null,
    delivered: typeof campaign.delivered === 'string' ? campaign.delivered : null,
    opened: typeof campaign.opened === 'string' ? campaign.opened : null,
    converted: typeof campaign.converted === 'string' ? campaign.converted : null,
    date: typeof campaign.date === 'string' ? campaign.date : null,
  };
}

function normaliseIntegration(integration) {
  if (!integration || typeof integration !== 'object') return null;
  return {
    id: typeof integration.id === 'string' ? integration.id : null,
    name: typeof integration.name === 'string' ? integration.name : null,
    description: typeof integration.description === 'string' ? integration.description : null,
    status: typeof integration.status === 'string' ? integration.status : null,
    category: typeof integration.category === 'string' ? integration.category : null,
    logo: typeof integration.logo === 'string' ? integration.logo : null,
  };
}

function normaliseAiConfig(config) {
  if (!config || typeof config !== 'object' || Array.isArray(config)) return null;
  return {
    agentName: typeof config.agentName === 'string' ? config.agentName : null,
    persona: typeof config.persona === 'string' ? config.persona : null,
    knowledgeBase: typeof config.knowledgeBase === 'string' ? config.knowledgeBase : null,
    qaPairs: Array.isArray(config.qaPairs)
      ? config.qaPairs.map(pair => ({
          q: typeof pair?.q === 'string' ? pair.q : '',
          a: typeof pair?.a === 'string' ? pair.a : '',
        }))
      : [],
  };
}

function normaliseFlowNode(node) {
  if (!node || typeof node !== 'object') return null;
  return {
    id: typeof node.id === 'string' ? node.id : null,
    type: typeof node.type === 'string' ? node.type : null,
    title: typeof node.title === 'string' ? node.title : null,
    description: typeof node.description === 'string' ? node.description : null,
    x: typeof node.x === 'number' ? node.x : null,
    y: typeof node.y === 'number' ? node.y : null,
    details: node.details && typeof node.details === 'object' && !Array.isArray(node.details) ? node.details : {},
  };
}

async function readJsonDatabase(filePath) {
  const raw = await readFile(filePath);
  const parsed = JSON.parse(raw.toString('utf8'));
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new TypeError('JSON database must be an object');
  }
  for (const collection of COLLECTIONS) {
    if (collection === 'aiConfig') {
      if (!parsed.aiConfig || typeof parsed.aiConfig !== 'object' || Array.isArray(parsed.aiConfig)) {
        throw new TypeError(`JSON database missing ${collection}`);
      }
    } else if (!Array.isArray(parsed[collection])) {
      throw new TypeError(`JSON database missing ${collection}`);
    }
  }
  return parsed;
}

function stableStringify(value) {
  const seen = new Set();
  const helper = (input) => {
    if (input && typeof input === 'object' && !Array.isArray(input)) {
      if (seen.has(input)) return '"[Circular]"';
      seen.add(input);
    }
    if (Array.isArray(input)) {
      return `[${input.map(helper).join(',')}]`;
    }
    if (input && typeof input === 'object') {
      const keys = Object.keys(input).sort();
      return `{${keys.map(key => `${JSON.stringify(key)}:${helper(input[key])}`).join(',')}}`;
    }
    return JSON.stringify(input);
  };
  return helper(value);
}

async function compareCampaigns(jsonCampaigns, storage, tenantId) {
  const result = await storage.withTenantTransaction(tenantId, async tx => {
    const repo = createCampaignsRepository(tx);
    const pgCampaigns = await repo.list();

    const pgByName = new Map();
    for (const row of pgCampaigns) {
      pgByName.set(row.name, row);
    }

    const drift = [];
    for (const campaign of jsonCampaigns) {
      const normalised = normaliseCampaign(campaign);
      if (!normalised || !normalised.name) {
        drift.push({ collection: 'campaigns', reason: 'invalid JSON record', record: campaign });
        continue;
      }
      const existing = pgByName.get(normalised.name);
      if (!existing) {
        drift.push({ collection: 'campaigns', reason: 'missing in PostgreSQL', record: normalised });
        continue;
      }
      let pgTarget = existing.target;
      if (typeof pgTarget === 'string') {
        try { pgTarget = JSON.parse(pgTarget); } catch { /* keep as-is */ }
      }
      const expectedTarget = typeof normalised.target === 'string' ? normalised.target : (normalised.target && typeof normalised.target === 'object' ? normalised.target : {});
      if (
        existing.status !== normalised.status ||
        existing.channel !== normalised.channel ||
        pgTarget !== expectedTarget
      ) {
        drift.push({ collection: 'campaigns', reason: 'content differs from JSON', record: normalised });
      }
    }
    return drift;
  });
  return result;
}

async function compareIntegrations(jsonIntegrations, storage, tenantId) {
  const result = await storage.withTenantTransaction(tenantId, async tx => {
    const repo = createIntegrationsRepository(tx);
    const pgIntegrations = await repo.list();

    const pgByProvider = new Map();
    for (const row of pgIntegrations) {
      pgByProvider.set(row.provider, row);
    }

    const drift = [];
    for (const integration of jsonIntegrations) {
      const normalised = normaliseIntegration(integration);
      if (!normalised || !normalised.id) {
        drift.push({ collection: 'integrations', reason: 'invalid JSON record', record: integration });
        continue;
      }
      const existing = pgByProvider.get(normalised.id);
      if (!existing) {
        drift.push({ collection: 'integrations', reason: 'missing in PostgreSQL', record: normalised });
        continue;
      }
      const config = existing.config && typeof existing.config === 'object' ? existing.config : {};
      if (
        existing.status !== normalised.status ||
        (config.name ?? null) !== normalised.name ||
        (config.description ?? null) !== normalised.description ||
        (config.category ?? null) !== normalised.category ||
        (config.logo ?? null) !== normalised.logo
      ) {
        drift.push({ collection: 'integrations', reason: 'content differs from JSON', record: normalised });
      }
    }
    return drift;
  });
  return result;
}

async function compareAiConfig(jsonConfig, storage, tenantId) {
  const result = await storage.withTenantTransaction(tenantId, async tx => {
    const repo = createAiConfigRepository(tx);
    const pgRow = await repo.get();
    const drift = [];
    if (!pgRow) {
      drift.push({ collection: 'aiConfig', reason: 'missing in PostgreSQL', record: jsonConfig });
      return drift;
    }
    const normalised = normaliseAiConfig(jsonConfig);
    if (
      pgRow.agentName !== normalised.agentName ||
      pgRow.persona !== normalised.persona ||
      pgRow.knowledgeBase !== normalised.knowledgeBase ||
      stableStringify(pgRow.qaPairs ?? []) !== stableStringify(normalised.qaPairs)
    ) {
      drift.push({ collection: 'aiConfig', reason: 'content differs from JSON', record: normalised });
    }
    return drift;
  });
  return result;
}

async function compareFlowNodes(jsonNodes, storage, tenantId) {
  const result = await storage.withTenantTransaction(tenantId, async tx => {
    const repo = createFlowNodesRepository(tx);
    const pgNodes = await repo.list();

    const pgById = new Map();
    for (const row of pgNodes) {
      pgById.set(row.id, row);
    }

    const drift = [];
    for (const node of jsonNodes) {
      const normalised = normaliseFlowNode(node);
      if (!normalised || !normalised.id) {
        drift.push({ collection: 'flowNodes', reason: 'invalid JSON record', record: node });
        continue;
      }
      const existing = pgById.get(normalised.id);
      if (!existing) {
        drift.push({ collection: 'flowNodes', reason: 'missing in PostgreSQL', record: normalised });
        continue;
      }
      const expectedDetails = normalised.details && typeof normalised.details === 'object' && !Array.isArray(normalised.details)
        ? normalised.details
        : {};
      if (
        existing.type !== normalised.type ||
        existing.title !== normalised.title ||
        (existing.description ?? null) !== normalised.description ||
        (existing.x ?? 0) !== (normalised.x ?? 0) ||
        (existing.y ?? 0) !== (normalised.y ?? 0) ||
        stableStringify(existing.details ?? {}) !== stableStringify(expectedDetails)
      ) {
        drift.push({ collection: 'flowNodes', reason: 'content differs from JSON', record: normalised });
      }
    }
    return drift;
  });
  return result;
}

async function compareSyncLogs(jsonLogs, storage, tenantId) {
  const result = await storage.withTenantTransaction(tenantId, async tx => {
    const pgLogs = await tx.query(`
      SELECT log_text AS "logText"
      FROM sync_logs
      WHERE tenant_id = $1
      ORDER BY created_at ASC, id ASC
    `, [tenantId]);

    const drift = [];
    if (pgLogs.rows.length !== jsonLogs.length) {
      drift.push({
        collection: 'syncLogs',
        reason: `count differs (JSON=${jsonLogs.length}, PostgreSQL=${pgLogs.rows.length})`,
        record: null,
      });
      return drift;
    }
    for (let index = 0; index < jsonLogs.length; index += 1) {
      if (pgLogs.rows[index]?.logText !== jsonLogs[index]) {
        drift.push({
          collection: 'syncLogs',
          reason: `entry at index ${index} differs from JSON`,
          record: { index, json: jsonLogs[index], postgres: pgLogs.rows[index]?.logText ?? null },
        });
      }
    }
    return drift;
  });
  return result;
}

async function migrateCampaigns(jsonCampaigns, storage, tenantId) {
  const summary = { created: 0, reused: 0 };
  await storage.withTenantTransaction(tenantId, async tx => {
    const repo = createCampaignsRepository(tx);
    const existing = await repo.list();
    const existingNames = new Set(existing.map(row => row.name));

    for (const campaign of jsonCampaigns) {
      const normalised = normaliseCampaign(campaign);
      if (!normalised || !normalised.name) continue;
      const externalId = `campaign:${normalised.name}`;
      if (existingNames.has(normalised.name)) {
        summary.reused += 1;
        continue;
      }
      const target = typeof normalised.target === 'string' ? normalised.target : '';
      const scheduledAt = normalised.date && /^\d{4}-\d{2}-\d{2}/.test(normalised.date)
        ? `${normalised.date} 00:00:00+00`
        : null;
      await tx.query(`
        INSERT INTO campaigns (tenant_id, name, status, channel, target, scheduled_at)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6)
      `, [tenantId, normalised.name, normalised.status, normalised.channel, JSON.stringify(target), scheduledAt]);
      await tx.query(`
        INSERT INTO zok_cutover_idempotency (collection, external_id)
        VALUES ($1, $2)
        ON CONFLICT (collection, external_id) DO UPDATE SET migrated_at = now()
      `, ['campaigns', externalId]);
      summary.created += 1;
    }
  });
  return summary;
}

async function migrateIntegrations(jsonIntegrations, storage, tenantId) {
  const summary = { created: 0, reused: 0 };
  await storage.withTenantTransaction(tenantId, async tx => {
    const repo = createIntegrationsRepository(tx);
    const existing = await repo.list();
    const existingProviders = new Set(existing.map(row => row.provider));

    for (const integration of jsonIntegrations) {
      const normalised = normaliseIntegration(integration);
      if (!normalised || !normalised.id) continue;
      const externalId = `integration:${normalised.id}`;
      if (existingProviders.has(normalised.id)) {
        summary.reused += 1;
        continue;
      }
      const config = {
        name: normalised.name,
        description: normalised.description,
        category: normalised.category,
        logo: normalised.logo,
      };
      await tx.query(`
        INSERT INTO integrations (tenant_id, provider, external_id, status, config)
        VALUES ($1, $2, $3, $4, $5::jsonb)
        ON CONFLICT (tenant_id, provider, external_id) DO UPDATE SET
          status = EXCLUDED.status,
          config = EXCLUDED.config,
          updated_at = now()
      `, [tenantId, normalised.id, normalised.id, normalised.status, JSON.stringify(config)]);
      await tx.query(`
        INSERT INTO zok_cutover_idempotency (collection, external_id)
        VALUES ($1, $2)
        ON CONFLICT (collection, external_id) DO UPDATE SET migrated_at = now()
      `, ['integrations', externalId]);
      summary.created += 1;
    }
  });
  return summary;
}

async function migrateAiConfig(jsonConfig, storage, tenantId) {
  const summary = { created: 0, reused: 0 };
  await storage.withTenantTransaction(tenantId, async tx => {
    const repo = createAiConfigRepository(tx);
    const externalId = 'ai_config:singleton';
    const existing = await repo.get();
    if (existing) {
      summary.reused += 1;
      return;
    }
    const normalised = normaliseAiConfig(jsonConfig);
    await repo.replace({
      agentName: normalised.agentName,
      persona: normalised.persona,
      knowledgeBase: normalised.knowledgeBase,
      qaPairs: normalised.qaPairs,
    });
    await tx.query(`
      INSERT INTO zok_cutover_idempotency (collection, external_id)
      VALUES ($1, $2)
      ON CONFLICT (collection, external_id) DO UPDATE SET migrated_at = now()
    `, ['aiConfig', externalId]);
    summary.created += 1;
  });
  return summary;
}

async function migrateFlowNodes(jsonNodes, storage, tenantId) {
  const summary = { created: 0, reused: 0 };
  await storage.withTenantTransaction(tenantId, async tx => {
    const repo = createFlowNodesRepository(tx);
    const externalId = 'flow_nodes:batch';
    const existing = await repo.list();
    if (existing.length > 0) {
      summary.reused += 1;
      return;
    }
    const nodes = jsonNodes.map(node => {
      const normalised = normaliseFlowNode(node);
      return {
        id: normalised.id,
        type: normalised.type,
        title: normalised.title,
        description: normalised.description,
        x: normalised.x ?? 0,
        y: normalised.y ?? 0,
        details: normalised.details,
      };
    });
    await repo.replace(nodes);
    await tx.query(`
      INSERT INTO zok_cutover_idempotency (collection, external_id)
      VALUES ($1, $2)
      ON CONFLICT (collection, external_id) DO UPDATE SET migrated_at = now()
    `, ['flowNodes', externalId]);
    summary.created += 1;
  });
  return summary;
}

async function migrateSyncLogs(jsonLogs, storage, tenantId) {
  const summary = { created: 0, reused: 0 };
  await storage.withTenantTransaction(tenantId, async tx => {
    const pgLogs = await tx.query('SELECT count(*) FROM sync_logs WHERE tenant_id = $1', [tenantId]);
    if (Number(pgLogs.rows[0].count) >= jsonLogs.length) {
      summary.reused = jsonLogs.length;
      return;
    }
    for (let index = Number(pgLogs.rows[0].count); index < jsonLogs.length; index += 1) {
      const logText = typeof jsonLogs[index] === 'string' ? jsonLogs[index] : String(jsonLogs[index]);
      const externalId = `sync_log:${index}:${createHash('sha256').update(logText).digest('hex')}`;
      await tx.query(`
        INSERT INTO sync_logs (tenant_id, log_text)
        VALUES ($1, $2)
      `, [tenantId, logText]);
      await tx.query(`
        INSERT INTO zok_cutover_idempotency (collection, external_id)
        VALUES ($1, $2)
        ON CONFLICT (collection, external_id) DO UPDATE SET migrated_at = now()
      `, ['syncLogs', externalId]);
      summary.created += 1;
    }
  });
  return summary;
}

export async function rehearseApplicationCutover({ sourceFile, tenantId, postgresUrl, apply = false } = {}) {
  const resolvedSource = path.resolve(required(sourceFile, 'sourceFile'));
  const resolvedTenant = required(tenantId, 'tenantId');
  const resolvedPostgresUrl = required(postgresUrl, 'postgresUrl');

  const jsonDb = await readJsonDatabase(resolvedSource);

  const pool = createPostgresPool({ connectionString: resolvedPostgresUrl });
  const storage = createPostgresStorage({ pool });

  let chatPreflight;
  try {
    chatPreflight = await preflightLegacyChatCutover({
      chats: jsonDb.chats,
      tenantId: resolvedTenant,
      storage,
    });
  } catch (error) {
    await storage.close();
    throw error;
  }

  const drift = [];
  const migrationSummary = {
    chats: null,
    campaigns: null,
    integrations: null,
    aiConfig: null,
    flowNodes: null,
    syncLogs: null,
  };

  try {
    const campaignsDrift = await compareCampaigns(jsonDb.campaigns, storage, resolvedTenant);
    drift.push(...campaignsDrift);

    const integrationsDrift = await compareIntegrations(jsonDb.integrations, storage, resolvedTenant);
    drift.push(...integrationsDrift);

    const aiConfigDrift = await compareAiConfig(jsonDb.aiConfig, storage, resolvedTenant);
    drift.push(...aiConfigDrift);

    const flowNodesDrift = await compareFlowNodes(jsonDb.flowNodes, storage, resolvedTenant);
    drift.push(...flowNodesDrift);

    const syncLogsDrift = await compareSyncLogs(jsonDb.syncLogs, storage, resolvedTenant);
    drift.push(...syncLogsDrift);
  } catch (error) {
    await storage.close();
    throw error;
  }

  if (apply) {
    migrationSummary.chats = await importLegacyChats({
      chats: jsonDb.chats,
      tenantId: resolvedTenant,
      storage,
    });
    migrationSummary.campaigns = await migrateCampaigns(jsonDb.campaigns, storage, resolvedTenant);
    migrationSummary.integrations = await migrateIntegrations(jsonDb.integrations, storage, resolvedTenant);
    migrationSummary.aiConfig = await migrateAiConfig(jsonDb.aiConfig, storage, resolvedTenant);
    migrationSummary.flowNodes = await migrateFlowNodes(jsonDb.flowNodes, storage, resolvedTenant);
    migrationSummary.syncLogs = await migrateSyncLogs(jsonDb.syncLogs, storage, resolvedTenant);

    drift.length = 0;
    const postMigrateCampaignsDrift = await compareCampaigns(jsonDb.campaigns, storage, resolvedTenant);
    drift.push(...postMigrateCampaignsDrift);
    const postMigrateIntegrationsDrift = await compareIntegrations(jsonDb.integrations, storage, resolvedTenant);
    drift.push(...postMigrateIntegrationsDrift);
    const postMigrateAiConfigDrift = await compareAiConfig(jsonDb.aiConfig, storage, resolvedTenant);
    drift.push(...postMigrateAiConfigDrift);
    const postMigrateFlowNodesDrift = await compareFlowNodes(jsonDb.flowNodes, storage, resolvedTenant);
    drift.push(...postMigrateFlowNodesDrift);
    const postMigrateSyncLogsDrift = await compareSyncLogs(jsonDb.syncLogs, storage, resolvedTenant);
    drift.push(...postMigrateSyncLogsDrift);
  }

  await storage.close();

  const sampleDrifted = drift.slice(0, 10).map(item => ({
    collection: item.collection,
    reason: item.reason,
    record: item.record,
  }));

  return Object.freeze({
    ready: drift.length === 0,
    driftCount: drift.length,
    sampleDriftedRecords: sampleDrifted,
    chatPreflight,
    migrationSummary: apply ? migrationSummary : null,
  });
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const dryRun = !args.has('--apply');
  const result = await rehearseApplicationCutover({
    sourceFile: args.get('--source') || process.env.ZOK_DB_FILE,
    tenantId: args.get('--tenant') || process.env.ZOK_ADMIN_TENANT_ID,
    postgresUrl: args.get('--postgres-url') || process.env.ZOK_POSTGRES_URL,
    apply: !dryRun,
  });
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (!result.ready && dryRun) {
    process.exitCode = 2;
  }
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1]);
if (isMain) {
  main().catch(error => {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  });
}
