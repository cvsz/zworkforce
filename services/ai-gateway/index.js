import express from 'express';
import { Readable } from 'stream';
import { fileURLToPath } from 'node:url';
import Redis from 'ioredis';
import helmet from 'helmet';
import cors from 'cors';
import pino from 'pino';
import pinoHttp from 'pino-http';
import dotenv from 'dotenv';
import { rateLimit } from 'express-rate-limit';
import { corsConfig, rateLimitConfig } from './security-config.mjs';

dotenv.config();

// Structured logger with strict secret redaction
const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  redact: {
    paths: ['req.headers.authorization', 'req.headers["x-api-key"]'],
    censor: '[REDACTED]'
  }
});

async function seedProviderKeys(redisClient, appLogger = logger) {
  const raw = process.env.AI_PROVIDER_KEYS_JSON || '{}';
  let configured;
  try {
    configured = JSON.parse(raw);
  } catch (error) {
    appLogger.error({ err: error }, 'Invalid AI_PROVIDER_KEYS_JSON');
    return;
  }
  if (!configured || typeof configured !== 'object') return;
  for (const [provider, values] of Object.entries(configured)) {
    const keys = Array.isArray(values) ? values : [values];
    const usable = keys.filter((value) => typeof value === 'string' && value.trim());
    if (usable.length) await redisClient.sadd(`provider:${provider}:active_keys`, ...usable);
  }
}

export function createGatewayApp({ redis, fetchImpl = globalThis.fetch, logger: appLogger = logger } = {}) {
  if (typeof fetchImpl !== 'function') {
    throw new Error('fetch implementation is unavailable');
  }

  const app = express();
  const redisClient = redis || new Redis(process.env.REDIS_URL || 'redis://localhost:6379');

  redisClient.on('error', (err) => appLogger.error({ err }, 'Redis connection error'));

  // Enterprise security and middleware
  app.use(helmet());
  app.use(cors(corsConfig()));
  app.use(express.json({ limit: '10mb' }));
  app.use(pinoHttp({ logger: appLogger }));
  app.use('/v1', rateLimit(rateLimitConfig()));

  // Authentication Middleware
  const requireAuth = (req, res, next) => {
    const token = req.headers.authorization?.split(' ')[1];
    if (!token || token !== process.env.Z_PLATFORM_SERVICE_TOKEN) {
      appLogger.warn({ ip: req.ip }, 'Unauthorized access attempt');
      return res.status(401).json({ error: { code: 'UNAUTHORIZED', message: 'Invalid or missing service token' } });
    }
    next();
  };

  // Health & Metrics
  app.get('/health', (req, res) => {
    const releaseSha = /^[0-9a-f]{40}$/.test(process.env.Z_PLATFORM_RELEASE_SHA || '')
      ? process.env.Z_PLATFORM_RELEASE_SHA
      : 'unknown';
    res.status(200).json({ status: 'ok', service: 'ai-gateway', release_sha: releaseSha });
  });

  app.get('/v1/models', requireAuth, (req, res) => {
    let models = [];
    try {
      models = JSON.parse(process.env.AI_MODELS_JSON || '[]');
    } catch {
      return res.status(500).json({ error: { code: 'INVALID_MODEL_CONFIG', message: 'AI_MODELS_JSON is invalid' } });
    }
    const fallback = process.env.AI_MODEL || 'default';
    const data = Array.isArray(models) && models.length
      ? models.map((id) => ({ id: String(id), object: 'model', owned_by: 'z-platform' }))
      : [{ id: fallback, object: 'model', owned_by: 'z-platform' }];
    return res.json({ object: 'list', data });
  });

  // Primary Gateway Route
  app.post('/v1/chat/completions', requireAuth, async (req, res) => {
    const provider = req.headers['x-provider'] || process.env.AI_DEFAULT_PROVIDER || 'openai-compatible';
    const modelId = req.body.model;

    if (!modelId) {
      return res.status(400).json({ error: { code: 'BAD_REQUEST', message: 'Model ID is required' } });
    }

    const controller = new AbortController();
    const abortUpstream = () => controller.abort();
    req.once('aborted', abortUpstream);
    res.once('close', () => {
      if (!res.writableEnded) {
        abortUpstream();
      }
    });

    const maxRetries = 3;
    let lastError = null;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      if (controller.signal.aborted) {
        appLogger.info({ provider, attempt }, 'Client disconnected before upstream completion');
        return;
      }

      const key = await redisClient.srandmember(`provider:${provider}:active_keys`);

      if (!key) {
        appLogger.error({ provider }, 'No active keys available in pool');
        return res.status(503).json({ error: { code: 'SERVICE_UNAVAILABLE', message: 'No upstream provider keys available' } });
      }

      try {
        const upstreamUrl = process.env.UPSTREAM_BASE_URL || 'https://api.openai.com/v1';

        const response = await fetchImpl(`${upstreamUrl}/chat/completions`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${key}`
          },
          body: JSON.stringify(req.body),
          signal: controller.signal
        });

        if (response.ok) {
          if (req.body.stream) {
            if (!response.body) {
              return res.status(502).json({ error: { code: 'BAD_GATEWAY', message: 'Streaming response body is unavailable' } });
            }

            const upstreamStream = Readable.fromWeb(response.body);
            res.setHeader('Content-Type', 'text/event-stream');
            res.setHeader('Cache-Control', 'no-cache');
            res.setHeader('Connection', 'keep-alive');
            res.once('close', () => upstreamStream.destroy());
            return upstreamStream.pipe(res);
          } else {
            const data = await response.json();
            return res.status(200).json(data);
          }
        } else if (response.status === 429) {
          await redisClient.srem(`provider:${provider}:active_keys`, key);
          await redisClient.set(`provider:${provider}:cooldown_keys:${key}`, 'cooldown', 'EX', 3600);
          appLogger.warn({ provider, attempt }, 'Rate limit hit (429). Key rotated to cooldown.');
          lastError = { status: 429, message: 'Upstream rate limit' };
          continue;
        } else if (response.status === 401 || response.status === 403) {
          await redisClient.srem(`provider:${provider}:active_keys`, key);
          await redisClient.sadd(`provider:${provider}:invalid_keys`, key);
          appLogger.warn({ provider, attempt, status: response.status }, 'Key invalid. Permanently removed.');
          lastError = { status: response.status, message: 'Upstream authentication failed' };
          continue;
        } else {
          const errText = await response.text();
          appLogger.error({ status: response.status, body: errText }, 'Upstream error');
          return res.status(502).json({ error: { code: 'BAD_GATEWAY', message: 'Upstream provider error' } });
        }
      } catch (error) {
        if (controller.signal.aborted) {
          appLogger.info({ provider, attempt }, 'Client disconnected while upstream request was in flight');
          return;
        }

        appLogger.error({ err: error }, 'Internal fetch error');
        lastError = { status: 500, message: 'Internal network error' };
      }
    }

    appLogger.error({ provider, lastError }, 'Exhausted all retry attempts');
    return res.status(502).json({ error: { code: 'EXHAUSTED', message: 'Provider routing failed after retries' } });
  });

  return { app, logger: appLogger, redis: redisClient };
}

export async function startGateway(options = {}) {
  const { app, logger: appLogger, redis } = createGatewayApp(options);
  await seedProviderKeys(redis, appLogger);
  const PORT = process.env.PORT || 8080;
  return app.listen(PORT, () => {
    appLogger.info(`AI Gateway running on port ${PORT}`);
  });
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  startGateway();
}
