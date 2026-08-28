import assert from 'node:assert/strict';
import { once } from 'node:events';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import {
  IdempotencyConflictError,
  inferGitHubRepositoryTarget,
  UnsupportedIntentError,
  ValidationError,
} from '../src/contracts.mjs';
import {
  executeGitHubRepositoryStatus,
  GitHubStatusToolError,
} from '../src/github-status-tool.mjs';
import { ZarvisOrchestrator } from '../src/orchestrator.mjs';
import { FileSessionStore, createMemorySessionStore } from '../src/session-store.mjs';
import {
  createZarvisServer,
  ZARVIS_OWNER_GITHUB_ID,
} from '../src/server.mjs';

const SERVICE_TOKEN = 'service-token-0123456789-0123456789';

const repositoryPayload = {
  full_name: 'cvsz/z-platform',
  visibility: 'public',
  private: false,
  archived: false,
  disabled: false,
  fork: false,
  default_branch: 'main',
  open_issues_count: 12,
  stargazers_count: 7,
  watchers_count: 7,
  forks_count: 2,
  updated_at: '2026-08-06T00:00:00Z',
  pushed_at: '2026-08-05T23:00:00Z',
  html_url: 'https://github.com/cvsz/z-platform',
};

function command(overrides = {}) {
  return {
    schema_version: 'zarvis.command.requested.v1',
    command_id: 'command-1',
    session_id: 'session-1',
    input: {
      modality: 'voice',
      text: 'ตรวจสถานะ GitHub cvsz/z-platform',
      locale: 'th-TH',
    },
    ...overrides,
  };
}

function ownerHeaders(extra = {}) {
  return {
    'x-zarvis-owner-id': ZARVIS_OWNER_GITHUB_ID,
    'x-zarvis-service-token': SERVICE_TOKEN,
    ...extra,
  };
}

async function listen(server) {
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const address = server.address();
  return `http://127.0.0.1:${address.port}`;
}

function sequentialIds() {
  let value = 0;
  return () => `event-${++value}`;
}

test('infers a GitHub repository target from Thai voice text', () => {
  assert.deepEqual(
    inferGitHubRepositoryTarget('ช่วยตรวจสถานะ GitHub cvsz/z-platform ให้หน่อย'),
    { owner: 'cvsz', repo: 'z-platform' },
  );
});

test('orchestrator emits durable session events and a redacted audit event', async () => {
  const audits = [];
  const sessionStore = createMemorySessionStore();
  const orchestrator = new ZarvisOrchestrator({
    githubStatusExecutor: async ({ owner, repo }) => {
      assert.deepEqual({ owner, repo }, { owner: 'cvsz', repo: 'z-platform' });
      return repositoryPayload;
    },
    auditSink: async (event) => audits.push(event),
    sessionStore,
    now: () => new Date('2026-08-06T00:30:00Z'),
    idFactory: sequentialIds(),
  });

  const result = await orchestrator.execute(command(), {
    tenantId: 'tenant-1',
    userId: 'user-1',
    requestId: 'request-1',
  });

  assert.equal(result.status, 'completed');
  assert.equal(result.replayed, false);
  assert.equal(result.intent.name, 'github.repository.status');
  assert.match(result.speech.text, /cvsz\/z-platform/);
  assert.equal(audits.length, 1);
  assert.equal(audits[0].tool.access, 'read_only');
  assert.equal(audits[0].outcome, 'succeeded');
  assert.equal(JSON.stringify(audits).includes('Bearer'), false);

  const session = await orchestrator.getSession('session-1');
  assert.deepEqual(session.events.map((event) => event.event_type), [
    'command.accepted',
    'command.completed',
  ]);
  assert.equal(session.events[0].payload.input.text, command().input.text);
});

test('command_id makes read-only execution idempotent', async () => {
  let calls = 0;
  const sessionStore = createMemorySessionStore();
  const orchestrator = new ZarvisOrchestrator({
    githubStatusExecutor: async () => {
      calls += 1;
      return repositoryPayload;
    },
    sessionStore,
    idFactory: sequentialIds(),
  });

  const first = await orchestrator.execute(command());
  const replay = await orchestrator.execute(command());

  assert.equal(calls, 1);
  assert.equal(first.replayed, false);
  assert.equal(replay.replayed, true);
  assert.equal(replay.audit.event_id, first.audit.event_id);
  assert.equal((await orchestrator.getSession('session-1')).events.length, 2);
});

test('reusing command_id with a different payload fails closed', async () => {
  const orchestrator = new ZarvisOrchestrator({
    githubStatusExecutor: async () => repositoryPayload,
    idFactory: sequentialIds(),
  });
  await orchestrator.execute(command());
  await assert.rejects(
    orchestrator.execute(command({
      input: { modality: 'voice', text: 'สถานะ GitHub cvsz/other', locale: 'th-TH' },
    })),
    IdempotencyConflictError,
  );
});

test('unsupported commands fail closed', async () => {
  const orchestrator = new ZarvisOrchestrator();
  await assert.rejects(
    orchestrator.execute(command({
      input: { modality: 'text', text: 'ลบฐานข้อมูลทั้งหมด', locale: 'th-TH' },
    })),
    UnsupportedIntentError,
  );
});

test('explicit mutating tools are rejected during validation', async () => {
  const orchestrator = new ZarvisOrchestrator();
  await assert.rejects(
    orchestrator.execute(command({
      tool: { name: 'github.repository.delete', arguments: { owner: 'cvsz', repo: 'z-platform' } },
    })),
    ValidationError,
  );
});

test('GitHub adapter uses a fixed HTTPS host and never returns the token', async () => {
  let observed;
  const result = await executeGitHubRepositoryStatus(
    { owner: 'cvsz', repo: 'z-platform' },
    {
      token: 'secret-token-value',
      fetchImpl: async (url, init) => {
        observed = { url, init };
        return new Response(JSON.stringify(repositoryPayload), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        });
      },
    },
  );

  assert.equal(observed.url.origin, 'https://api.github.com');
  assert.equal(observed.url.pathname, '/repos/cvsz/z-platform');
  assert.equal(observed.init.method, 'GET');
  assert.equal(observed.init.headers.Authorization, 'Bearer secret-token-value');
  assert.equal(JSON.stringify(result).includes('secret-token-value'), false);
});

test('GitHub adapter maps not-found responses without leaking upstream bodies', async () => {
  await assert.rejects(
    executeGitHubRepositoryStatus(
      { owner: 'cvsz', repo: 'missing' },
      { fetchImpl: async () => new Response('sensitive upstream detail', { status: 404 }) },
    ),
    (error) => error instanceof GitHubStatusToolError
      && error.code === 'repository_not_found'
      && !error.message.includes('sensitive upstream detail'),
  );
});

test('file session store survives process-level reconstruction and supports deletion', async (t) => {
  const rootDir = await mkdtemp(join(tmpdir(), 'zarvis-store-'));
  t.after(() => rm(rootDir, { recursive: true, force: true }));

  const firstStore = new FileSessionStore({ rootDir });
  const orchestrator = new ZarvisOrchestrator({
    githubStatusExecutor: async () => repositoryPayload,
    sessionStore: firstStore,
    idFactory: sequentialIds(),
  });
  await orchestrator.execute(command());

  const reconstructed = new FileSessionStore({ rootDir });
  const snapshot = await reconstructed.readSession('session-1');
  assert.equal(snapshot.events.length, 2);
  assert.equal((await reconstructed.getCommandResult('command-1')).result.status, 'completed');

  const deleted = await reconstructed.deleteSession('session-1');
  assert.equal(deleted.deleted, true);
  assert.equal(deleted.command_results_deleted, 1);
  assert.deepEqual((await reconstructed.readSession('session-1')).events, []);
  assert.equal(await reconstructed.getCommandResult('command-1'), null);
});

test('HTTP service fails closed when the console service token is absent', () => {
  assert.throws(
    () => createZarvisServer({ serviceToken: undefined }),
    /ZARVIS_ORCHESTRATOR_SERVICE_TOKEN/,
  );
});

test('HTTP service rejects requests without the owner service identity', async (t) => {
  const server = createZarvisServer({
    serviceToken: SERVICE_TOKEN,
    logger: { info() {}, error() {} },
  });
  const baseUrl = await listen(server);
  t.after(() => server.close());

  const response = await fetch(`${baseUrl}/v1/tools`);
  assert.equal(response.status, 403);
  assert.equal((await response.json()).error.code, 'owner_access_denied');
});

test('HTTP service exposes owner-only session history and confirmation-gated deletion', async (t) => {
  const sessionStore = createMemorySessionStore();
  const audits = [];
  const orchestrator = new ZarvisOrchestrator({
    githubStatusExecutor: async () => repositoryPayload,
    auditSink: async (event) => audits.push(event),
    sessionStore,
    now: () => new Date('2026-08-06T00:30:00Z'),
    idFactory: sequentialIds(),
  });
  const server = createZarvisServer({
    orchestrator,
    sessionStore,
    serviceToken: SERVICE_TOKEN,
    logger: { info() {}, error() {} },
  });
  const baseUrl = await listen(server);
  t.after(() => server.close());

  const executeResponse = await fetch(`${baseUrl}/v1/commands`, {
    method: 'POST',
    headers: ownerHeaders({
      'content-type': 'application/json',
      'x-tenant-id': 'attacker',
      'x-user-id': 'attacker',
    }),
    body: JSON.stringify(command()),
  });
  assert.equal(executeResponse.status, 200);
  const result = await executeResponse.json();
  assert.equal(result.schema_version, 'zarvis.command.completed.v1');
  assert.equal(result.result.default_branch, 'main');
  assert.equal(audits[0].tenant_id, `owner-${ZARVIS_OWNER_GITHUB_ID}`);
  assert.equal(audits[0].user_id, `github:${ZARVIS_OWNER_GITHUB_ID}`);

  const historyResponse = await fetch(`${baseUrl}/v1/sessions/session-1`, {
    headers: ownerHeaders(),
  });
  assert.equal(historyResponse.status, 200);
  assert.equal((await historyResponse.json()).events.length, 2);

  const unconfirmedDelete = await fetch(`${baseUrl}/v1/sessions/session-1`, {
    method: 'DELETE',
    headers: ownerHeaders(),
  });
  assert.equal(unconfirmedDelete.status, 428);
  assert.equal((await unconfirmedDelete.json()).error.code, 'confirmation_required');

  const confirmedDelete = await fetch(`${baseUrl}/v1/sessions/session-1`, {
    method: 'DELETE',
    headers: ownerHeaders({ 'x-zarvis-confirm-delete': 'session-1' }),
  });
  assert.equal(confirmedDelete.status, 200);
  assert.equal((await confirmedDelete.json()).deleted, true);
});
