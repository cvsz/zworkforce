#!/usr/bin/env node
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createPostgresPool, createPostgresStorage } from '../server/storage/postgres-storage.js';
import { preflightLegacyChatCutover } from '../server/storage/postgres/chat-cutover-rehearsal.js';

function parseArgs(argv) {
  const args = new Map();
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith('--')) throw new TypeError(`Unexpected argument: ${token}`);
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

export async function rehearseChatCutover({ sourceFile, tenantId, postgresUrl } = {}) {
  const resolvedSource = path.resolve(required(sourceFile, 'sourceFile'));
  const resolvedTenant = required(tenantId, 'tenantId');
  const resolvedPostgresUrl = required(postgresUrl, 'postgresUrl');

  const before = await readFile(resolvedSource);
  const parsed = JSON.parse(before.toString('utf8'));
  if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.chats)) {
    throw new TypeError('Legacy source must contain a chats array');
  }

  const storage = createPostgresStorage({
    pool: createPostgresPool({ connectionString: resolvedPostgresUrl }),
  });

  let preflight;
  try {
    preflight = await preflightLegacyChatCutover({
      chats: parsed.chats,
      tenantId: resolvedTenant,
      storage,
    });
  } finally {
    await storage.close();
  }

  const after = await readFile(resolvedSource);
  if (!before.equals(after)) {
    throw new Error('Chat cutover rehearsal failed: rollback JSON snapshot changed during preflight');
  }

  return Object.freeze({
    ...preflight,
    rollbackSnapshotPreserved: true,
    sourceFile: resolvedSource,
  });
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const result = await rehearseChatCutover({
    sourceFile: args.get('--source') || process.env.ZOK_DB_FILE,
    tenantId: args.get('--tenant') || process.env.ZOK_ADMIN_TENANT_ID,
    postgresUrl: args.get('--postgres-url') || process.env.ZOK_POSTGRES_URL,
  });
  process.stdout.write(`${JSON.stringify(result)}\n`);
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1]);
if (isMain) {
  main().catch(error => {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  });
}
