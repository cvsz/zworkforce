import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

import { createJsonStorage } from '../server/storage/json-storage.js';

const validDatabase = () => ({
  chats: [],
  aiConfig: {},
  flowNodes: [],
  campaigns: [],
  integrations: [],
  syncLogs: [],
});

function validateDatabase(data) {
  assert.ok(data && typeof data === 'object' && !Array.isArray(data));
  for (const collection of ['chats', 'flowNodes', 'campaigns', 'integrations', 'syncLogs']) {
    assert.ok(Array.isArray(data[collection]));
  }
  assert.ok(data.aiConfig && typeof data.aiConfig === 'object' && !Array.isArray(data.aiConfig));
  return data;
}

test('JSON storage initializes, serializes concurrent mutations, and preserves corrupt state', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'zok-storage-'));
  const filePath = path.join(directory, 'db.json');
  const storage = createJsonStorage({
    filePath,
    defaultData: validDatabase(),
    validate: validateDatabase,
  });

  try {
    assert.deepEqual(await storage.read(), validDatabase());

    await Promise.all(Array.from({ length: 20 }, (_, index) => storage.update(db => {
      db.campaigns.push({ id: index + 1 });
      return db.campaigns.length;
    })));

    const persisted = JSON.parse(await readFile(filePath, 'utf8'));
    assert.equal(persisted.campaigns.length, 20);
    assert.equal((await readdir(directory)).filter(name => name.endsWith('.tmp')).length, 0);

    await writeFile(filePath, '{"broken": true', 'utf8');
    await assert.rejects(storage.read(), /Database is unavailable/);
    assert.equal(await readFile(filePath, 'utf8'), '{"broken": true');
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
