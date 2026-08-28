import { readFile, rename, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createPostgresPool, createPostgresStorage } from '../server/storage/postgres-storage.js';
import {
  createLegacyChatImportCheckpoint,
  importLegacyChats,
} from '../server/storage/postgres/legacy-chat-import.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '..');

function parseArgs(argv) {
  const options = {
    dryRun: false,
    resume: false,
    checkpointFile: '',
    file: process.env.ZOK_DB_FILE || path.join(repoRoot, 'server', 'db.json'),
    tenantId: process.env.ZOK_ADMIN_TENANT_ID || '',
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--dry-run') {
      options.dryRun = true;
      continue;
    }
    if (arg === '--resume') {
      options.resume = true;
      continue;
    }
    if (arg === '--file' || arg === '--tenant-id' || arg === '--checkpoint') {
      const value = argv[index + 1];
      if (!value || value.startsWith('--')) throw new Error(`${arg} requires a value`);
      index += 1;
      if (arg === '--file') options.file = path.resolve(value);
      else if (arg === '--tenant-id') options.tenantId = value;
      else options.checkpointFile = path.resolve(value);
      continue;
    }
    throw new Error(`Unknown argument: ${arg}`);
  }
  if (options.resume && !options.checkpointFile) {
    throw new Error('--resume requires --checkpoint <file>');
  }
  return options;
}

async function readCheckpoint(file) {
  try {
    const parsed = JSON.parse(await readFile(file, 'utf8'));
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new TypeError('Import checkpoint must contain a JSON object');
    }
    return parsed;
  } catch (error) {
    if (error && typeof error === 'object' && error.code === 'ENOENT') return null;
    throw error;
  }
}

async function writeCheckpoint(file, checkpoint) {
  const temporary = `${file}.tmp-${process.pid}`;
  await writeFile(temporary, `${JSON.stringify(checkpoint, null, 2)}\n`, { encoding: 'utf8', flag: 'w' });
  await rename(temporary, file);
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const source = JSON.parse(await readFile(options.file, 'utf8'));
  if (!source || typeof source !== 'object' || Array.isArray(source) || !Array.isArray(source.chats)) {
    throw new TypeError('Legacy JSON source must contain a chats array');
  }

  if (options.dryRun) {
    const result = await importLegacyChats({
      chats: source.chats,
      tenantId: options.tenantId,
      dryRun: true,
    });
    console.log(JSON.stringify(result, null, 2));
    return;
  }

  const connectionString = (process.env.ZOK_POSTGRES_URL || '').trim();
  if (!connectionString) throw new Error('ZOK_POSTGRES_URL is required unless --dry-run is used');

  let checkpoint;
  if (options.checkpointFile) {
    const existing = await readCheckpoint(options.checkpointFile);
    if (options.resume) {
      if (!existing) throw new Error('Checkpoint file does not exist for --resume');
      checkpoint = existing;
    } else {
      if (existing) throw new Error('Checkpoint file already exists; use --resume or choose another file');
      checkpoint = createLegacyChatImportCheckpoint({
        chats: source.chats,
        tenantId: options.tenantId,
      });
      await writeCheckpoint(options.checkpointFile, checkpoint);
    }
  }

  const pool = createPostgresPool({ connectionString });
  const storage = createPostgresStorage({ pool });
  try {
    const result = await importLegacyChats({
      chats: source.chats,
      tenantId: options.tenantId,
      storage,
      checkpoint,
      onCheckpoint: options.checkpointFile
        ? nextCheckpoint => writeCheckpoint(options.checkpointFile, nextCheckpoint)
        : undefined,
    });
    console.log(JSON.stringify(result, null, 2));
  } finally {
    await storage.close();
  }
}

main().catch(error => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
