import { randomUUID, timingSafeEqual } from 'node:crypto';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import {
  IdempotencyConflictError,
  UnsupportedIntentError,
  ValidationError,
} from './contracts.mjs';
import { GitHubStatusToolError } from './github-status-tool.mjs';
import { AVAILABLE_TOOLS, ZarvisOrchestrator } from './orchestrator.mjs';
import { FileSessionStore } from './session-store.mjs';

export const ZARVIS_OWNER_GITHUB_ID = '4076926';

const MAX_BODY_BYTES = 32 * 1024;
const MIN_SECRET_BYTES = 32;
const SESSION_PATH_PATTERN = /^\/v1\/sessions\/([A-Za-z0-9._:-]{1,128})$/;

class OwnerAccessError extends Error {
  constructor() {
    super('This private Z.A.R.V.I.S. instance is restricted to its owner.');
    this.name = 'OwnerAccessError';
    this.code = 'owner_access_denied';
    this.status = 403;
  }
}

class ConfirmationRequiredError extends Error {
  constructor(sessionId) {
    super(`Set x-zarvis-confirm-delete to ${sessionId} to delete this session.`);
    this.name = 'ConfirmationRequiredError';
    this.code = 'confirmation_required';
    this.status = 428;
  }
}

function requireSecret(value, name) {
  if (typeof value !== 'string' || Buffer.byteLength(value.trim()) < MIN_SECRET_BYTES) {
    throw new Error(`${name} must contain at least ${MIN_SECRET_BYTES} bytes.`);
  }
  return value.trim();
}

function secretsMatch(actual, expected) {
  if (typeof actual !== 'string') return false;
  const actualBuffer = Buffer.from(actual);
  const expectedBuffer = Buffer.from(expected);
  return actualBuffer.length === expectedBuffer.length && timingSafeEqual(actualBuffer, expectedBuffer);
}

function assertOwnerServiceRequest(request, serviceToken) {
  const ownerId = request.headers['x-zarvis-owner-id']?.toString();
  const presentedToken = request.headers['x-zarvis-service-token']?.toString();
  if (ownerId !== ZARVIS_OWNER_GITHUB_ID || !secretsMatch(presentedToken, serviceToken)) {
    throw new OwnerAccessError();
  }
}

function writeJson(response, statusCode, payload) {
  const body = JSON.stringify(payload);
  response.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
  });
  response.end(body);
}

async function readJsonBody(request) {
  const contentType = request.headers['content-type'] ?? '';
  if (!contentType.toLowerCase().startsWith('application/json')) {
    throw new ValidationError('Content-Type must be application/json.');
  }

  const chunks = [];
  let total = 0;
  for await (const chunk of request) {
    total += chunk.length;
    if (total > MAX_BODY_BYTES) {
      const error = new ValidationError(`Request body exceeds ${MAX_BODY_BYTES} bytes.`);
      error.status = 413;
      throw error;
    }
    chunks.push(chunk);
  }

  if (chunks.length === 0) throw new ValidationError('Request body is required.');

  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch {
    throw new ValidationError('Request body must contain valid JSON.');
  }
}

export function createStdoutAuditSink({ logger = console } = {}) {
  return async (event) => {
    logger.info(JSON.stringify({ channel: 'audit', event }));
  };
}

export function createZarvisServer({
  orchestrator,
  sessionStore,
  dataDir = process.env.ZARVIS_DATA_DIR ?? './data/zarvis',
  serviceToken = process.env.ZARVIS_ORCHESTRATOR_SERVICE_TOKEN,
  logger = console,
} = {}) {
  const trustedServiceToken = requireSecret(
    serviceToken,
    'ZARVIS_ORCHESTRATOR_SERVICE_TOKEN',
  );
  const durableStore = sessionStore ?? new FileSessionStore({ rootDir: dataDir });
  const runtime = orchestrator ?? new ZarvisOrchestrator({
    auditSink: createStdoutAuditSink({ logger }),
    sessionStore: durableStore,
  });

  return createServer(async (request, response) => {
    const requestId = request.headers['x-request-id']?.toString().slice(0, 160) || randomUUID();
    response.setHeader('X-Request-Id', requestId);

    try {
      const url = new URL(request.url ?? '/', 'http://localhost');

      if (request.method === 'GET' && url.pathname === '/healthz') {
        writeJson(response, 200, {
          status: 'ok',
          service: 'zarvis-orchestrator',
          version: '0.2.0',
          durable_sessions: true,
        });
        return;
      }

      assertOwnerServiceRequest(request, trustedServiceToken);

      if (request.method === 'GET' && url.pathname === '/v1/tools') {
        writeJson(response, 200, { tools: AVAILABLE_TOOLS });
        return;
      }

      if (request.method === 'POST' && url.pathname === '/v1/commands') {
        const command = await readJsonBody(request);
        const result = await runtime.execute(command, {
          requestId,
          tenantId: `owner-${ZARVIS_OWNER_GITHUB_ID}`,
          userId: `github:${ZARVIS_OWNER_GITHUB_ID}`,
        });
        writeJson(response, 200, result);
        return;
      }

      const sessionMatch = url.pathname.match(SESSION_PATH_PATTERN);
      if (sessionMatch && request.method === 'GET') {
        const limit = url.searchParams.has('limit') ? Number(url.searchParams.get('limit')) : 100;
        const snapshot = await runtime.getSession(sessionMatch[1], { limit });
        writeJson(response, 200, snapshot);
        return;
      }

      if (sessionMatch && request.method === 'DELETE') {
        const sessionId = sessionMatch[1];
        if (request.headers['x-zarvis-confirm-delete']?.toString() !== sessionId) {
          throw new ConfirmationRequiredError(sessionId);
        }
        const result = await runtime.deleteSession(sessionId);
        writeJson(response, 200, result);
        return;
      }

      writeJson(response, 404, {
        error: {
          code: 'route_not_found',
          message: 'Route not found.',
          request_id: requestId,
        },
      });
    } catch (error) {
      let statusCode = 500;
      if (error instanceof ValidationError) {
        statusCode = error.status ?? 400;
      } else if (error instanceof UnsupportedIntentError) {
        statusCode = 422;
      } else if (
        error instanceof GitHubStatusToolError
        || error instanceof OwnerAccessError
        || error instanceof ConfirmationRequiredError
        || error instanceof IdempotencyConflictError
      ) {
        statusCode = error.status;
      }

      if (statusCode >= 500) {
        logger.error('zarvis request failed', {
          request_id: requestId,
          code: error?.code ?? 'internal_error',
          message: error?.message,
        });
      }

      writeJson(response, statusCode, {
        error: {
          code: error?.code ?? 'internal_error',
          message: statusCode >= 500 ? 'The request could not be completed.' : error.message,
          request_id: requestId,
          ...(error?.details ? { details: error.details } : {}),
        },
      });
    }
  });
}

const isEntrypoint = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];
if (isEntrypoint) {
  const port = Number(process.env.PORT ?? 8094);
  const host = process.env.HOST ?? '0.0.0.0';
  const server = createZarvisServer();
  server.listen(port, host, () => {
    console.info(`zarvis-orchestrator listening on http://${host}:${port}`);
  });
}
