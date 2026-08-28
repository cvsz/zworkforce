import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import {
  randomBytes,
  randomUUID,
  timingSafeEqual,
} from 'node:crypto';
import { createJsonStorage } from './server/storage/json-storage.js';
import { verifyPassword } from './server/utils/password.js';
import {
  createChatRouteGate,
  overlayPostgresMessages,
} from './server/storage/postgres/chat-route-gate.js';
import { createCampaignsRepository } from './server/storage/postgres/campaigns-repository.js';
import { createCampaignWorker } from './server/campaigns/campaign-worker.js';
import { createCampaignScheduler as _createCampaignScheduler } from './server/campaigns/campaign-scheduler.js';
import { createCampaignExecutor as _createCampaignExecutor } from './server/campaigns/campaign-executor.js';
import { createIntegrationsRepository } from './server/storage/postgres/integrations-repository.js';
import { createAiConfigRepository } from './server/storage/postgres/ai-config-repository.js';
import { createFlowNodesRepository } from './server/storage/postgres/flow-nodes-repository.js';
import { createUsersRepository } from './server/storage/postgres/users-repository.js';
import { createRbacMiddleware, requirePermission } from './server/storage/postgres/rbac-middleware.js';
import { createAuditService } from './server/storage/postgres/audit-service.js';
import { createAuditMiddleware } from './server/storage/postgres/audit-middleware.js';
import { createApiKeyManager } from './server/security/api-key-manager.js';
import { createApiKeyMiddleware } from './server/security/api-key-middleware.js';
import { createSecretsVault } from './server/security/secrets-vault.js';
import { createIdempotencyStore } from './server/channels/idempotency-store.js';
import { createConsentChecker } from './server/channels/consent-checker.js';
import { verifyWebhookSignature, getExpectedSignatureHeader } from './server/channels/webhook-verifier.js';
import { validateInboundEvent, buildIdempotencyKey, INBOUND_EVENT_TYPES } from './server/channels/channel-contracts.js';
import { createAdapterFactory } from './server/channels/adapter-factory.js';
import { hashToken } from './server/storage/postgres/session-store.js';
import { createRateLimitStore } from './server/storage/postgres/rate-limit-store.js';
import { createLogger } from './server/observability/logger.js';
import { configureMetrics, renderPrometheusMetrics, incrementCounter, setGauge, recordLatency } from './server/observability/metrics.js';
import { configureTracing, createTraceMiddleware } from './server/observability/tracing.js';
import { createGovernedAIService } from './server/ai/governed-ai-service.js';
import { createAiTelemetry } from './server/ai/ai-telemetry.js';
import { createAiApproval } from './server/ai/ai-approval.js';
import { createDataExport } from './server/privacy/data-export.js';
import { createDataDeletion } from './server/privacy/data-deletion.js';
import { createRetentionPolicy } from './server/privacy/retention-policy.js';
import { createAttributionEngine } from './server/commerce/attribution-engine.js';
import { createReconciliationEngine } from './server/commerce/reconciliation.js';
import { createShopifyAdapter } from './server/commerce/adapters/shopify-adapter.js';
import { createTikTokShopAdapter } from './server/commerce/adapters/tiktok-shop-adapter.js';
import { createSecureCookieConfig } from './server/edge/secure-cookies.js';
import { createReverseProxyConfig } from './server/edge/reverse-proxy.js';
import { createHealthCheck } from './server/edge/health-check.js';
import { createRollbackManager } from './server/edge/rollback.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3005;
const DB_FILE = process.env.ZOK_DB_FILE || path.join(__dirname, 'server', 'db.json');
const NODE_ENV = process.env.NODE_ENV || 'development';
const IS_PRODUCTION = NODE_ENV === 'production';
const secureCookieConfig = createSecureCookieConfig();
const reverseProxyConfig = createReverseProxyConfig();
reverseProxyConfig.apply(app);
const CHAT_STORAGE_MODE = (process.env.ZOK_CHAT_STORAGE || 'json').trim().toLowerCase();
const CHAT_POSTGRES_URL = (process.env.ZOK_POSTGRES_URL || '').trim();
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SESSION_STORE_MODE = (process.env.ZOK_SESSION_STORE || 'memory').trim().toLowerCase();
const RATE_LIMIT_STORE = (process.env.ZOK_RATE_LIMIT_STORE || 'memory').trim().toLowerCase();

function boundedInteger(value, fallback, minimum, maximum) {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= minimum && parsed <= maximum
    ? parsed
    : fallback;
}

const SESSION_TTL_MS = boundedInteger(
  process.env.ZOK_SESSION_TTL_MS,
  8 * 60 * 60 * 1000,
  5 * 60 * 1000,
  7 * 24 * 60 * 60 * 1000,
);
const ADMIN_EMAIL = (process.env.ZOK_ADMIN_EMAIL || '').trim().toLowerCase();
const ADMIN_PASSWORD_HASH = process.env.ZOK_ADMIN_PASSWORD_HASH || '';
const ADMIN_TENANT_ID = (process.env.ZOK_ADMIN_TENANT_ID || '').trim();
if (ADMIN_TENANT_ID && !UUID_PATTERN.test(ADMIN_TENANT_ID)) {
  throw new Error('ZOK_ADMIN_TENANT_ID must be a UUID');
}
const AUTH_CONFIGURED = Boolean(ADMIN_EMAIL && ADMIN_PASSWORD_HASH);
const DEFAULT_ALLOWED_ORIGINS = IS_PRODUCTION
  ? ['https://zok.zeaz.dev']
  : [
      'http://127.0.0.1:5175',
      'http://localhost:5175',
      'http://127.0.0.1:3000',
      'http://localhost:3000',
      'https://zok.zeaz.dev',
    ];
const ALLOWED_ORIGINS = new Set(
  (process.env.ZOK_ALLOWED_ORIGINS || DEFAULT_ALLOWED_ORIGINS.join(','))
    .split(',')
    .map(origin => origin.trim())
    .filter(Boolean),
);
if (ALLOWED_ORIGINS.has('*')) {
  throw new Error('ZOK_ALLOWED_ORIGINS must not contain a wildcard');
}
const sessions = new Map();
const rateLimitBuckets = new Map();
const invitations = new Map();

function parseCookies(req) {
  const header = req.headers.cookie || '';
  const cookies = {};

  for (const part of header.split(';')) {
    const [name, ...valueParts] = part.trim().split('=');
    if (!name || valueParts.length === 0) continue;
    try {
      cookies[name] = decodeURIComponent(valueParts.join('='));
    } catch {
      // Ignore malformed cookies and let authentication fail closed.
    }
  }

  return cookies;
}

function cookieHeader(name, value, options = {}) {
  return secureCookieConfig.buildCookie(name, value, options);
}

function setAuthCookies(res, session) {
  res.setHeader('Set-Cookie', [
    cookieHeader('zok_session', session.token, { httpOnly: true, maxAge: Math.floor(SESSION_TTL_MS / 1000) }),
    cookieHeader('zok_csrf', session.csrfToken, { maxAge: Math.floor(SESSION_TTL_MS / 1000) }),
  ]);
}

function clearAuthCookies(res) {
  res.setHeader('Set-Cookie', [
    cookieHeader('zok_session', '', { httpOnly: true, maxAge: 0 }),
    cookieHeader('zok_csrf', '', { maxAge: 0 }),
  ]);
}

async function getSession(token) {
  if (sessionStore) {
    return sessionStore.get(token);
  }
  return sessions.get(token) || null;
}

async function deleteSession(token) {
  if (sessionStore) {
    return sessionStore.delete(token);
  }
  sessions.delete(token);
}

async function pruneExpiredSessions() {
  if (sessionStore) {
    return sessionStore.pruneExpired();
  }
  const now = Date.now();
  for (const [token, session] of sessions) {
    if (session.expiresAt <= now) sessions.delete(token);
  }
}

async function sessionFromRequest(req) {
  await pruneExpiredSessions();
  const cookies = parseCookies(req);
  const token = cookies.zok_session;
  if (!token) return null;

  let session;
  try {
    session = await getSession(token);
  } catch {
    return null;
  }
  if (!session || session.expiresAt <= Date.now()) {
    if (session) {
      try { await deleteSession(token); } catch {}
    }
    return null;
  }

  if (sessionStore) {
    const csrfToken = cookies.zok_csrf;
    if (!csrfToken) return null;
    try {
      if (hashToken(csrfToken) !== session.csrfTokenHash) {
        await deleteSession(token);
        return null;
      }
    } catch {
      return null;
    }
    return { ...session, csrfToken };
  }

  return session;
}

function rateLimit({ windowMs, max }) {
  return async (req, res, next) => {
    const key = `${req.ip || 'unknown'}:${req.path}`;
    const now = Date.now();
    let allowed = true;
    let remaining = max;
    let retryAfter = 0;

    if (rateLimitStore) {
      try {
        const result = await rateLimitStore.check(key, windowMs, max);
        allowed = result.allowed;
        remaining = result.remaining;
        retryAfter = result.retryAfter;
      } catch (error) {
        appLogger.warn('rate-limit store error', { error: error.message });
      }
    } else {
      const existing = rateLimitBuckets.get(key);
      const bucket = existing && existing.expiresAt > now
        ? existing
        : { count: 0, expiresAt: now + windowMs };

      bucket.count += 1;
      rateLimitBuckets.set(key, bucket);
      if (rateLimitBuckets.size > 10000) {
        for (const [bucketKey, bucketValue] of rateLimitBuckets) {
          if (bucketValue.expiresAt <= now) rateLimitBuckets.delete(bucketKey);
        }
      }
      remaining = Math.max(0, max - bucket.count);
      retryAfter = bucket.count > max ? Math.ceil((bucket.expiresAt - now) / 1000) : 0;
      allowed = bucket.count <= max;
    }

    res.setHeader('RateLimit-Limit', max);
    res.setHeader('RateLimit-Remaining', remaining);

    if (!allowed) {
      res.setHeader('Retry-After', retryAfter);
      return res.status(429).json({ error: 'Too many requests' });
    }

    return next();
  };
}

function parseChatId(value) {
  if (!/^\d+$/.test(String(value))) return null;
  const id = Number(value);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

function requiredText(value, field, maxLength = 4000) {
  if (typeof value !== 'string') {
    return { error: `${field} must be a string` };
  }
  const text = value.trim();
  if (!text) return { error: `${field} is required` };
  if (text.length > maxLength) return { error: `${field} exceeds the ${maxLength}-character limit` };
  return { value: text };
}

function validateTags(tags) {
  if (!Array.isArray(tags) || tags.length > 32) return 'Tags must be an array of at most 32 items';
  if (tags.some(tag => typeof tag !== 'string' || !tag.trim() || tag.trim().length > 80)) {
    return 'Each tag must be a non-empty string of at most 80 characters';
  }
  return null;
}

function sameOriginOrAllowed(req) {
  const origin = req.get('origin');
  return !origin || ALLOWED_ORIGINS.has(origin);
}

async function requireAuth(req, res, next) {
  const publicPaths = ['/health', '/auth/config'];
  const publicMethods = {
    '/auth/login': 'POST',
    '/auth/accept-invite': 'POST',
  };

  if (publicPaths.includes(req.path)) return next();
  const method = publicMethods[req.path];
  if (method && req.method === method) return next();

  if (req.user && req.user.authMethod === 'api-key') {
    return next();
  }

  if (!AUTH_CONFIGURED) {
    return res.status(503).json({ error: 'Authentication is not configured' });
  }

  const session = await sessionFromRequest(req);
  if (!session) return res.status(401).json({ error: 'Authentication required' });
  req.session = session;
  req.user = session.user;
  req.tenantId = session.user.tenantId || null;
  req.userId = session.user.id || null;
  return next();
}

function rbacGuard(permission) {
  if (rbacMiddlewareInstance && permission) {
    return [requirePermission(permission), rbacMiddlewareInstance];
  }
  return [];
}

function requireCsrf(req, res, next) {
  if (['GET', 'HEAD', 'OPTIONS'].includes(req.method) || req.path === '/auth/login') return next();
  if (req.user && req.user.authMethod === 'api-key') return next();
  if (!sameOriginOrAllowed(req)) return res.status(403).json({ error: 'Origin is not allowed' });

  const expected = req.session?.csrfToken;
  const received = req.get('x-csrf-token');
  if (!expected || !received) return res.status(403).json({ error: 'CSRF token is required' });

  const expectedBuffer = Buffer.from(expected);
  const receivedBuffer = Buffer.from(received);
  if (
    expectedBuffer.length !== receivedBuffer.length ||
    !timingSafeEqual(expectedBuffer, receivedBuffer)
  ) {
    return res.status(403).json({ error: 'Invalid CSRF token' });
  }

  return next();
}

app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  if (IS_PRODUCTION) res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
  next();
});

app.use(reverseProxyConfig.middleware);

app.use('/api', (req, res, next) => {
  res.setHeader('Cache-Control', 'no-store');
  return next();
});
app.use(cors({
  credentials: true,
  origin(origin, callback) {
    if (!origin || ALLOWED_ORIGINS.has(origin)) return callback(null, true);
    return callback(new Error('Origin is not allowed by CORS'));
  },
}));
app.use('/api', rateLimit({ windowMs: 60_000, max: 180 }));
app.use('/api/webhooks', express.raw({ type: 'application/json', limit: '64kb' }));
app.use(express.json({ limit: '64kb' }));

app.post('/api/webhooks/whatsapp', async (req, res) => {
  const secret = process.env.ZOK_WHATSAPP_WEBHOOK_SECRET || 'dev-whatsapp-secret';
  return handleWebhook('whatsapp', secret, req, res);
});

app.post('/api/webhooks/line', async (req, res) => {
  const secret = process.env.ZOK_LINE_WEBHOOK_SECRET || 'dev-line-secret';
  return handleWebhook('line', secret, req, res);
});

app.post('/api/webhooks/messenger', async (req, res) => {
  const secret = process.env.ZOK_MESSENGER_WEBHOOK_SECRET || 'dev-messenger-secret';
  return handleWebhook('messenger', secret, req, res);
});

app.post('/api/webhooks/tiktok', async (req, res) => {
  const secret = process.env.ZOK_TIKTOK_WEBHOOK_SECRET || 'dev-tiktok-secret';
  return handleWebhook('tiktok', secret, req, res);
});

app.post('/api/webhooks/shopify', async (req, res) => {
  const secret = process.env.ZOK_SHOPIFY_WEBHOOK_SECRET || 'dev-shopify-secret';
  return handleWebhook('shopify', secret, req, res);
});

app.post('/api/webhooks/tiktok-shop', async (req, res) => {
  const secret = process.env.ZOK_TIKTOK_SHOP_WEBHOOK_SECRET || 'dev-tiktok-shop-secret';
  return handleWebhook('tiktok-shop', secret, req, res);
});

let apiKeyValueImpl = (req, res, next) => next();
app.use('/api', (req, res, next) => apiKeyValueImpl(req, res, next));
app.use('/api', requireAuth);
app.use('/api', requireCsrf);

const DEFAULT_DB = {
  chats: [
    {
      id: 1,
      name: 'Panacee Medical Centre',
      avatar: 'PMC',
      channel: 'line',
      unread: 2,
      time: '10:24 AM',
      messages: [
        { sender: 'customer', text: 'Hello, what are your clinic hours for tomorrow?', time: '10:20 AM' },
        { sender: 'customer', text: 'I would like to book a general checkup.', time: '10:21 AM' }
      ],
      details: {
        phone: '+66 2 712 0333',
        email: 'info@panacee.com',
        assigned: 'Sarah Connor',
        tags: ['New Lead', 'LINE OA', 'Medical Service'],
        orders: [
          { id: 'ORD-8812', date: '2026-08-01', total: '$149.00', status: 'Delivered' }
        ]
      }
    },
    {
      id: 2,
      name: 'Karmart Customer Support',
      avatar: 'KM',
      channel: 'whatsapp',
      unread: 0,
      time: '9:15 AM',
      messages: [
        { sender: 'customer', text: 'Hi, is my order #5512 shipped yet?', time: '9:10 AM' },
        { sender: 'agent', text: 'Hello! Yes, it was dispatched yesterday. Your tracking link is: kmt.express/38821', time: '9:12 AM' },
        { sender: 'customer', text: 'Awesome, thank you!', time: '9:15 AM' }
      ],
      details: {
        phone: '+65 9123 4567',
        email: 'support@karmart.com.sg',
        assigned: 'Alex Rivera',
        tags: ['Shopify Buyer', 'WhatsApp', 'VIP'],
        orders: [
          { id: 'ORD-5512', date: '2026-08-09', total: '$48.50', status: 'Shipped' },
          { id: 'ORD-4390', date: '2026-07-15', total: '$112.00', status: 'Delivered' }
        ]
      }
    },
    {
      id: 3,
      name: 'Wilfried Buiron',
      avatar: 'WB',
      channel: 'messenger',
      unread: 1,
      time: 'Yesterday',
      messages: [
        { sender: 'customer', text: 'Do you offer custom API endpoints for Shopify syncing?', time: 'Yesterday' }
      ],
      details: {
        phone: '+1 650 882 1190',
        email: 'wilfried@zok.zeaz.dev',
        assigned: 'Sarah Connor',
        tags: ['Enterprise', 'Messenger', 'Developer'],
        orders: []
      }
    },
    {
      id: 4,
      name: 'Nattapong (TikTok Seller)',
      avatar: 'NT',
      channel: 'tiktok',
      unread: 0,
      time: 'Yesterday',
      messages: [
        { sender: 'customer', text: 'Thanks for the quick response. Will test the AI automation feature tonight.', time: 'Yesterday' }
      ],
      details: {
        phone: '+66 89 123 4567',
        email: 'nattapong.tkt@gmail.com',
        assigned: 'Automated Bot',
        tags: ['TikTok Shop', 'Active Demo'],
        orders: [
          { id: 'TKT-9912', date: '2026-08-05', total: '$29.90', status: 'Delivered' }
        ]
      }
    },
    {
      id: 5,
      name: 'Emily Davis',
      avatar: 'ED',
      channel: 'shopify',
      unread: 0,
      time: '2 days ago',
      messages: [
        { sender: 'customer', text: 'I received a damaged package. Can I get a replacement?', time: '2 days ago' },
        { sender: 'agent', text: 'We are very sorry to hear that. I have triggered a replacement shipment. Your new order code is ORD-9011.', time: '2 days ago' }
      ],
      details: {
        phone: '+44 7700 900077',
        email: 'emily.davis@gmail.com',
        assigned: 'Alex Rivera',
        tags: ['Shopify Buyer', 'Support Ticket'],
        orders: [
          { id: 'ORD-9011', date: '2026-08-08', total: '$0.00', status: 'Processing' },
          { id: 'ORD-8321', date: '2026-07-28', total: '$85.00', status: 'Delivered' }
        ]
      }
    }
  ],
  aiConfig: {
    agentName: 'Zok AI Sales Agent',
    persona: 'sales',
    knowledgeBase: 'Zok is an e-commerce brand offering lifestyle accessories. Standard delivery takes 3-5 days. All products have a 1-year product warranty. Customers earn 5% cashback on loyalty purchases.',
    qaPairs: [
      { q: 'What is your return policy?', a: 'We offer a 14-day free return policy for all unused products. Returns are processed within 3 business days.' },
      { q: 'Do you offer free shipping?', a: 'Yes! We offer free shipping on all orders over $100. Standard shipping for smaller orders is $5.99.' },
      { q: 'Where are you located?', a: 'Our corporate headquarters are located in Singapore and Bangkok, Thailand. We ship globally!' }
    ]
  },
  flowNodes: [
    {
      id: 'node-1',
      type: 'trigger',
      title: 'Trigger: Keyword Message',
      description: 'When message contains "price" or "catalog"',
      x: 50,
      y: 120,
      details: { keywords: 'price, catalog' }
    },
    {
      id: 'node-2',
      type: 'action',
      title: 'Send WhatsApp Template',
      description: 'Send Catalog Link Template message',
      x: 320,
      y: 80,
      details: { template: 'WhatsApp Catalog Link', variable: 'customer_name' }
    },
    {
      id: 'node-3',
      type: 'condition',
      title: 'Check Customer Tag',
      description: 'Verify if tag matches "Shopify Buyer"',
      x: 320,
      y: 240,
      details: { tag: 'Shopify Buyer' }
    },
    {
      id: 'node-4',
      type: 'action',
      title: 'Send Discount Code',
      description: 'Send discount coupon code "VIP10"',
      x: 600,
      y: 200,
      details: { text: 'Here is your 10% discount code: VIP10!' }
    }
  ],
  campaigns: [
    {
      id: 1,
      name: 'August VIP Discount Promo',
      status: 'completed',
      channel: 'whatsapp',
      target: 'VIP Customers',
      recipients: 1450,
      delivered: '100%',
      opened: '84.2%',
      converted: '12.8%',
      date: '2026-08-05'
    },
    {
      id: 2,
      name: 'LINE OA Welcome Voucher Push',
      status: 'completed',
      channel: 'line',
      target: 'New Leads',
      recipients: 890,
      delivered: '98.5%',
      opened: '92.1%',
      converted: '15.4%',
      date: '2026-08-01'
    },
    {
      id: 3,
      name: 'Abandon Cart Recovery Followup',
      status: 'scheduled',
      channel: 'whatsapp',
      target: 'Shopify Buyer',
      recipients: 320,
      delivered: '--',
      opened: '--',
      converted: '--',
      date: '2026-08-15 (10:00 AM)'
    }
  ],
  integrations: [
    {
      id: 'shopify',
      name: 'Shopify Store Sync',
      description: 'Pull order history, client tags, and catalog details inside unified chat sidebar.',
      status: 'disconnected',
      category: 'E-commerce',
      logo: 'S'
    },
    {
      id: 'tiktok',
      name: 'TikTok Shop DM Integration',
      description: 'Consolidate TikTok seller chats and order statuses into Zok helpdesk.',
      status: 'disconnected',
      category: 'Social Commerce',
      logo: 'T'
    },
    {
      id: 'lazada',
      name: 'Lazada Messaging',
      description: 'Sync customer chats from Lazada Seller Center directly to your agents.',
      status: 'disconnected',
      category: 'Marketplace',
      logo: 'L'
    },
    {
      id: 'shopee',
      name: 'Shopee Seller Chat',
      description: 'Automate customer support for Shopee inquiries using Zok AI bot flow.',
      status: 'disconnected',
      category: 'Marketplace',
      logo: 'Sh'
    },
    {
      id: 'hubspot',
      name: 'HubSpot CRM Sync',
      description: 'Export customer details, active tickets, and chat history into HubSpot CRM leads.',
      status: 'disconnected',
      category: 'CRM',
      logo: 'H'
    }
  ],
  syncLogs: [
    `[10:20:00 AM] Sandbox integration data loaded; no provider credentials configured.`,
    `[10:20:01 AM] External channel delivery is disabled until account verification.`
  ]
};

function validateDatabase(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new Error('Database is unavailable');
  }

  const requiredCollections = ['chats', 'flowNodes', 'campaigns', 'integrations', 'syncLogs'];
  if (requiredCollections.some(collection => !Array.isArray(data[collection]))) {
    throw new Error('Database is unavailable');
  }

  if (!data.aiConfig || typeof data.aiConfig !== 'object' || Array.isArray(data.aiConfig)) {
    throw new Error('Database is unavailable');
  }

  if (data.chats.some(chat => (
    !chat ||
    !Number.isSafeInteger(chat.id) ||
    chat.id < 1 ||
    !Array.isArray(chat.messages) ||
    !chat.details ||
    typeof chat.details !== 'object' ||
    !Array.isArray(chat.details.tags)
  ))) {
    throw new Error('Database is unavailable');
  }

  return data;
}

const storage = createJsonStorage({
  filePath: DB_FILE,
  defaultData: DEFAULT_DB,
  validate: validateDatabase,
});
const chatRouteGate = createChatRouteGate({
  mode: CHAT_STORAGE_MODE,
  connectionString: CHAT_POSTGRES_URL,
});

let postgresStorage = null;
let postgresPool = null;
let rbacMiddlewareInstance = null;

if (CHAT_STORAGE_MODE === 'postgres' && CHAT_POSTGRES_URL) {
  try {
    const { createPostgresPool, createPostgresStorage } = await import('./server/storage/postgres-storage.js');
    postgresPool = createPostgresPool({ connectionString: CHAT_POSTGRES_URL });
    postgresStorage = createPostgresStorage({ pool: postgresPool });
    rbacMiddlewareInstance = createRbacMiddleware(postgresStorage);
  } catch (error) {
    appLogger.error('Failed to initialize PostgreSQL RBAC storage', { error: error.message });
  }
}

let sessionStore = null;
let sessionPool = null;

if (SESSION_STORE_MODE === 'postgres') {
  try {
    const { createSessionStore } = await import('./server/storage/postgres/session-store.js');
    if (postgresPool) {
      sessionStore = createSessionStore(postgresPool);
    } else if (CHAT_POSTGRES_URL) {
      const { createPostgresPool } = await import('./server/storage/postgres-storage.js');
      sessionPool = createPostgresPool({ connectionString: CHAT_POSTGRES_URL });
      sessionStore = createSessionStore(sessionPool);
    } else {
      appLogger.error('PostgreSQL session store requires ZOK_POSTGRES_URL');
    }
  } catch (error) {
    appLogger.error('Failed to initialize PostgreSQL session store', { error: error.message });
  }
}

let rateLimitStore = null;

if (RATE_LIMIT_STORE === 'postgres' && postgresPool) {
  try {
    rateLimitStore = createRateLimitStore(postgresPool);
    rateLimitStore.startCleanup();
  } catch (error) {
    appLogger.error('Failed to initialize PostgreSQL rate-limit store', { error: error.message });
  }
}

let auditService = null;
if (postgresPool) {
  try {
    auditService = createAuditService(postgresPool);
  } catch (error) {
    appLogger.error('Failed to initialize audit service', { error: error.message });
  }
}
const auditMiddleware = createAuditMiddleware(postgresPool);
app.use('/api', auditMiddleware);
apiKeyValueImpl = createApiKeyMiddleware(postgresPool);

let securityMasterKey = process.env.ZOK_SECRETS_MASTER_KEY || null;
let securityServicesEnabled = Boolean(postgresPool);

const dataExport = createDataExport({ jsonStorage: storage, postgresPool, auditService });
const dataDeletion = createDataDeletion({ jsonStorage: storage, postgresPool, auditService });

const appLogger = createLogger({ component: 'server' });
configureTracing({ sampleRate: process.env.ZOK_TRACE_SAMPLE_RATE || 'always' });
if (postgresPool) {
  configureMetrics(postgresPool);
}

let retentionPolicy = null;
try {
  retentionPolicy = createRetentionPolicy({ postgresPool, auditService });
} catch (error) {
  appLogger.warn('Failed to initialize retention policy', { error: error.message });
}

let campaignWorker = null;
if (postgresPool) {
  try {
    campaignWorker = createCampaignWorker({ pool: postgresPool, concurrency: 4 });
  } catch (error) {
    appLogger.warn('Failed to initialize campaign worker', { error: error.message });
  }
}

app.use((req, res, next) => {
  req.requestId = randomUUID();
  req.tenantId = null;
  req.userId = null;
  next();
});

app.use(createTraceMiddleware());

app.use((req, res, next) => {
  const start = Date.now();
  res.setHeader('X-Request-Id', req.requestId);
  res.on('finish', () => {
    const duration = Date.now() - start;
    const labels = {
      method: req.method,
      route: req.path,
      status: res.statusCode,
    };
    incrementCounter('api_requests', labels);
    recordLatency(duration, { method: req.method, route: req.path });
    if (res.statusCode >= 400) {
      incrementCounter('api_errors', labels);
    }
  });
  next();
});

let idempotencyStore = null;
let consentChecker = null;
let adapterFactory = null;
let aiTelemetry = null;
let aiApproval = null;
let governedAIService = null;
if (postgresPool) {
  idempotencyStore = createIdempotencyStore(postgresPool);
  consentChecker = createConsentChecker(postgresPool);
  try {
    adapterFactory = createAdapterFactory();
  } catch (error) {
    appLogger.error('Failed to initialize adapter factory', { error: error.message });
  }
  try {
    aiTelemetry = createAiTelemetry(postgresPool);
    aiApproval = createAiApproval(postgresPool);
    governedAIService = createGovernedAIService({ telemetry: aiTelemetry, approval: aiApproval, pool: postgresPool });
  } catch (error) {
    appLogger.error('Failed to initialize governed AI services', { error: error.message });
  }
} else {
  idempotencyStore = createIdempotencyStore(null);
  consentChecker = createConsentChecker(null);
  try {
    adapterFactory = createAdapterFactory();
  } catch (error) {
    appLogger.error('Failed to initialize adapter factory', { error: error.message });
  }
}

let attributionEngine = null;
let reconciliationEngine = null;
let shopifyAdapter = null;
let tiktokAdapter = null;

if (postgresPool) {
  try {
    attributionEngine = createAttributionEngine({
      postgresPool,
      jsonStorage: storage,
      logger: appLogger,
    });
  } catch (error) {
    appLogger.error('Failed to initialize attribution engine', { error: error.message });
  }
  try {
    reconciliationEngine = createReconciliationEngine({
      postgresPool,
      jsonStorage: storage,
      logger: appLogger,
    });
  } catch (error) {
    appLogger.error('Failed to initialize reconciliation engine', { error: error.message });
  }
  try {
    shopifyAdapter = createShopifyAdapter({
      postgresPool,
      jsonStorage: storage,
      logger: appLogger,
    });
  } catch (error) {
    appLogger.error('Failed to initialize Shopify adapter', { error: error.message });
  }
  try {
    tiktokAdapter = createTikTokShopAdapter({
      postgresPool,
      jsonStorage: storage,
      logger: appLogger,
    });
  } catch (error) {
    appLogger.error('Failed to initialize TikTok Shop adapter', { error: error.message });
  }
}

const healthCheck = createHealthCheck({
  jsonStorage: storage,
  postgresPool,
  sessionStore,
  rateLimitStore,
  auditService,
  adapterFactory,
  campaignWorker,
});

const rollbackManager = createRollbackManager({
  pool: postgresPool,
  logger: appLogger,
  tenantId: 'global',
});

async function readDB() {
  return storage.read();
}

function updateDB(mutator) {
  return storage.update(mutator);
}

async function postgresBackedChat(request, chat) {
  const state = await chatRouteGate.runtime.read(request, chat.id);
  if (!state) {
    const error = new Error('PostgreSQL chat import is incomplete');
    error.status = 503;
    throw error;
  }
  return overlayPostgresMessages(chat, state);
}

async function processWebhookEvent(provider, eventType, payload, idempotencyKey, tenantId) {
  const normalizedEventType = typeof eventType === 'string' ? eventType.trim().toLowerCase() : 'unknown';
  if (!INBOUND_EVENT_TYPES.includes(normalizedEventType)) {
    return { status: 'ignored', reason: 'unsupported_event_type' };
  }

  if (idempotencyStore) {
    const alreadyProcessed = await idempotencyStore.check(idempotencyKey);
    if (alreadyProcessed) {
      return { status: 'duplicate' };
    }
    await idempotencyStore.mark(idempotencyKey, 86400, {
      provider,
      eventType: normalizedEventType,
      contactId: payload?.contactId || '',
      payload,
    });
  }

  if (consentChecker && tenantId) {
    const contactId = payload?.contactId || payload?.from || '';
    if (contactId) {
      const allowed = await consentChecker.isAllowed(contactId, provider, tenantId);
      if (!allowed) {
        return { status: 'rejected', reason: 'consent_required' };
      }
    }
  }

  return { status: 'accepted', eventType: normalizedEventType };
}

function extractWebhookExternalId(provider, payload) {
  if (!payload || typeof payload !== 'object') return `${Date.now()}`;

  switch (provider) {
    case 'whatsapp':
    case 'messenger': {
      const entries = payload.entry;
      if (Array.isArray(entries) && entries[0]?.changes?.[0]?.value?.messages?.[0]?.id) {
        return entries[0].changes[0].value.messages[0].id;
      }
      if (Array.isArray(entries) && entries[0]?.changes?.[0]?.value?.reads?.[0]?.id) {
        return entries[0].changes[0].value.reads[0].id;
      }
      break;
    }
    case 'line': {
      const events = payload.events;
      if (Array.isArray(events) && events[0]?.message?.id) {
        return events[0].message.id;
      }
      if (Array.isArray(events) && events[0]?.id) {
        return events[0].id;
      }
      break;
    }
    case 'tiktok': {
      if (payload.data?.id) {
        return payload.data.id;
      }
      break;
    }
    default:
      break;
  }

  return `${Date.now()}`;
}

async function handleWebhook(provider, secret, req, res) {
  try {
    const signatureHeader = req.get(getExpectedSignatureHeader(provider));
    if (!signatureHeader) {
      return res.status(401).json({ error: 'Missing webhook signature' });
    }

    const verification = verifyWebhookSignature(provider, secret, req.body, signatureHeader);
    if (!verification.valid) {
      return res.status(401).json({ error: verification.error || 'Invalid webhook signature' });
    }

    const externalId = extractWebhookExternalId(provider, verification.payload);
    const idempotencyKey = buildIdempotencyKey(provider, verification.eventType, externalId);

    const tenantId = req.user?.tenantId || null;
    const result = await processWebhookEvent(provider, verification.eventType, verification.payload, idempotencyKey, tenantId);

    if (result.status === 'rejected') {
      return res.status(403).json({ error: 'Consent required', reason: result.reason });
    }
    if (result.status === 'duplicate') {
      incrementCounter('webhook_events', { provider, eventType: result.eventType, status: 'duplicate' });
      return res.status(200).json({ status: 'duplicate', eventType: result.eventType });
    }
    incrementCounter('webhook_events', { provider, eventType: result.eventType, status: 'accepted' });
    return res.status(202).json({ status: 'accepted', eventType: result.eventType });
  } catch (error) {
    appLogger.error('webhook error', { method: req.method, url: req.originalUrl, error: error.message });
    incrementCounter('webhook_errors', { provider: req.path.split('/')[3] || 'unknown' });
    return res.status(500).json({ error: 'Webhook processing failed' });
  }
}

app.get('/api/health', async (_req, res) => {
  const dependencies = {
    database: 'unknown',
    postgres: postgresStorage ? 'connected' : 'disabled',
    sessionStore: sessionStore ? 'connected' : 'disabled',
    rateLimitStore: rateLimitStore ? 'connected' : 'disabled',
    auditService: auditService ? 'connected' : 'disabled',
    channelAdapters: adapterFactory ? (adapterFactory.mode === 'real' ? 'real' : 'simulated') : 'disabled',
  };
  try {
    await readDB();
    dependencies.database = 'ok';

    if (adapterFactory) {
      try {
        const adapterHealth = await adapterFactory.healthChecks();
        dependencies.adapterHealth = adapterHealth;
      } catch (adapterError) {
        appLogger.error('adapter health check failed', { error: adapterError.message });
        dependencies.adapterHealth = { error: adapterError.message };
      }
    }

    return res.json({ status: 'ok', service: 'zok-api', environment: NODE_ENV, dependencies });
  } catch (error) {
    appLogger.error('health check failed', { error: error.message });
    dependencies.database = 'error';
    return res.status(503).json({ status: 'degraded', service: 'zok-api', environment: NODE_ENV, dependencies });
  }
});

app.get('/health/live', async (_req, res) => {
  const result = await healthCheck.liveness();
  const statusCode = result.status === 'healthy' ? 200 : 503;
  res.status(statusCode).json(result);
});

app.get('/health/ready', async (_req, res) => {
  const result = await healthCheck.readiness();
  const statusCode = result.status === 'ready' || result.status === 'degraded' ? 200 : 503;
  res.status(statusCode).json(result);
});

app.post('/admin/rollback', requireAuth, requireOwner, async (req, res) => {
  const { flagName, percentage, reason } = req.body || {};

  if (!flagName || typeof flagName !== 'string') {
    return res.status(400).json({ error: 'flagName is required' });
  }

  const parsedPercentage = Number(percentage);
  if (!Number.isSafeInteger(parsedPercentage) || parsedPercentage < 0 || parsedPercentage > 100) {
    return res.status(400).json({ error: 'percentage must be an integer between 0 and 100' });
  }

  try {
    const record = await rollbackManager.rollbackFeature(flagName, parsedPercentage, reason || 'manual rollback');
    return res.status(201).json(record);
  } catch (error) {
    appLogger.error('rollback failed', { method: req.method, url: req.originalUrl, error: error.message });
    return res.status(500).json({ error: 'Rollback failed' });
  }
});

app.get('/admin/rollback', requireAuth, requireOwner, async (_req, res) => {
  try {
    const statuses = await rollbackManager.getAllStatuses();
    return res.json(statuses);
  } catch (error) {
    appLogger.error('rollback list failed', { error: error.message });
    return res.status(500).json({ error: 'Failed to list rollback statuses' });
  }
});

app.get('/admin/rollback/:flagName', requireAuth, requireOwner, async (req, res) => {
  try {
    const status = await rollbackManager.getStatus(req.params.flagName);
    return res.json(status);
  } catch (error) {
    appLogger.error('rollback status failed', { error: error.message });
    return res.status(500).json({ error: 'Failed to get rollback status' });
  }
});

app.post('/admin/rollback/:flagName/emergency', requireAuth, requireOwner, async (req, res) => {
  try {
    const record = await rollbackManager.emergencyRollback(req.params.flagName, req.body?.reason || 'emergency rollback');
    return res.status(201).json(record);
  } catch (error) {
    appLogger.error('emergency rollback failed', { method: req.method, url: req.originalUrl, error: error.message });
    return res.status(500).json({ error: 'Emergency rollback failed' });
  }
});

app.get('/metrics', (_req, res) => {
  res.setHeader('Content-Type', 'text/plain; version=0.0.4; charset=utf-8');
  res.send(renderPrometheusMetrics());
});

app.get('/api/auth/config', (req, res) => {
  res.json({ configured: AUTH_CONFIGURED, registrationEnabled: false });
});

app.post('/api/auth/login', rateLimit({ windowMs: 15 * 60_000, max: 10 }), async (req, res) => {
  const emailResult = requiredText(req.body?.email, 'Email', 254);
  const passwordResult = requiredText(req.body?.password, 'Password', 256);

  if (emailResult.error || passwordResult.error) {
    return res.status(400).json({ error: emailResult.error || passwordResult.error });
  }
  if (!AUTH_CONFIGURED) {
    return res.status(503).json({ error: 'Authentication is not configured' });
  }

  const email = emailResult.value.toLowerCase();
  if (email !== ADMIN_EMAIL || !verifyPassword(passwordResult.value, ADMIN_PASSWORD_HASH)) {
    return res.status(401).json({ error: 'Invalid email or password' });
  }

  await pruneExpiredSessions();

  const session = {
    token: randomBytes(32).toString('base64url'),
    csrfToken: randomBytes(32).toString('base64url'),
    expiresAt: Date.now() + SESSION_TTL_MS,
    user: {
      email,
      role: 'owner',
      ...(ADMIN_TENANT_ID ? { tenantId: ADMIN_TENANT_ID } : {}),
    },
  };

  if (sessionStore && session.user.tenantId) {
    const client = await (sessionPool || postgresPool).connect();
    try {
      const userResult = await client.query(
        'SELECT id FROM users WHERE tenant_id = $1 AND email = $2 LIMIT 1',
        [session.user.tenantId, email],
      );
      if (userResult.rows.length === 0) {
        await client.query(
          `INSERT INTO users (tenant_id, email, display_name, status)
           VALUES ($1, $2, $3, 'active')`,
          [session.user.tenantId, email, email.split('@')[0]],
        );
      }
    } finally {
      client.release();
    }
  }

  try {
    if (sessionStore) {
      await sessionStore.create(session);
    } else {
      sessions.set(session.token, session);
    }
  } catch (error) {
    appLogger.error('session creation failed', { method: req.method, url: req.originalUrl, error: error.message });
    return res.status(500).json({ error: 'Internal server error' });
  }

  setAuthCookies(res, session);

  setGauge('active_sessions', sessions.size + (sessionStore ? 1 : 0));

  if (auditService) {
    auditService.emit({
      tenant_id: session.user.tenantId,
      actor_user_id: session.user.id || null,
      action: 'auth.login',
      resource_type: 'auth',
      resource_id: session.user.tenantId,
      request_id: req.requestId || randomUUID(),
      occurred_at: new Date().toISOString(),
      metadata: {
        email: session.user.email,
        method: 'POST',
        path: '/api/auth/login',
      },
    }).catch(() => {});
  }

  return res.json({ user: session.user });
});

app.get('/api/auth/me', (req, res) => {
  res.json({ user: req.user });
});

function generateInviteToken() {
  return randomBytes(32).toString('base64url');
}

app.post('/api/auth/invite', rateLimit({ windowMs: 60_000, max: 20 }), async (req, res) => {
  if (!postgresStorage || !req.user?.tenantId) {
    return res.status(503).json({ error: 'PostgreSQL storage is required for invitations' });
  }

  const emailResult = requiredText(req.body?.email, 'Email', 254);
  const roleResult = requiredText(req.body?.role, 'Role', 120);

  if (emailResult.error || roleResult.error) {
    return res.status(400).json({ error: emailResult.error || roleResult.error });
  }

  const email = emailResult.value.toLowerCase();
  const roleName = roleResult.value.trim();
  const tenantId = req.user.tenantId;

  try {
    const normalizedEmail = email.toLowerCase();
    await postgresStorage.withTenantTransaction(tenantId, async (tx) => {
      const usersRepo = createUsersRepository(tx);
      const existing = await usersRepo.findByEmail(normalizedEmail);
      if (existing) {
        const error = new Error('User already exists');
        error.status = 409;
        throw error;
      }

      const roleResult = await tx.query(
        `SELECT id, permissions FROM roles WHERE tenant_id = $1 AND name = $2 LIMIT 1`,
        [tenantId, roleName]
      );
      if (roleResult.rows.length === 0) {
        const error = new Error('Role not found');
        error.status = 404;
        throw error;
      }

      const token = generateInviteToken();
      const expiresAt = Date.now() + 7 * 24 * 60 * 60 * 1000;
      invitations.set(token, {
        tenantId,
        email: normalizedEmail,
        roleId: roleResult.rows[0].id,
        roleName,
        permissions: roleResult.rows[0].permissions,
        createdAt: Date.now(),
        expiresAt,
      });
    });

    res.status(201).json({
      message: 'Invitation created',
      inviteToken: invitations.has(generateInviteToken()) ? undefined : undefined,
    });
  } catch (error) {
    if (error.status) return res.status(error.status).json({ error: error.message });
    appLogger.error('invite endpoint error', { method: req.method, url: req.originalUrl, error: error.message });
    return res.status(500).json({ error: 'Internal server error' });
  }
});

app.post('/api/auth/accept-invite', rateLimit({ windowMs: 60_000, max: 10 }), async (req, res) => {
  if (!postgresStorage) {
    return res.status(503).json({ error: 'PostgreSQL storage is required for invitations' });
  }

  const tokenResult = requiredText(req.body?.token, 'Token', 255);
  const passwordResult = requiredText(req.body?.password, 'Password', 256);
  const displayNameResult = requiredText(req.body?.displayName, 'Display name', 240);

  if (tokenResult.error || passwordResult.error || displayNameResult.error) {
    return res.status(400).json({ error: tokenResult.error || passwordResult.error || displayNameResult.error });
  }

  const token = tokenResult.value;
  const invitation = invitations.get(token);

  if (!invitation || invitation.expiresAt <= Date.now()) {
    invitations.delete(token);
    return res.status(410).json({ error: 'Invitation token is invalid or expired' });
  }

  if (invitation.email !== displayNameResult.value.trim().toLowerCase()) {
    return res.status(400).json({ error: 'Display name does not match invitation' });
  }

  try {
    let newUserId = null;
    await postgresStorage.withTenantTransaction(invitation.tenantId, async (tx) => {
      const usersRepo = createUsersRepository(tx);
      const existing = await usersRepo.findByEmail(invitation.email);
      if (existing) {
        const error = new Error('User already exists');
        error.status = 409;
        throw error;
      }

      const user = await usersRepo.create({
        email: invitation.email,
        displayName: displayNameResult.value,
        password: passwordResult.value,
        status: 'active',
      });
      newUserId = user.id;

      await tx.query(
        `INSERT INTO user_roles (tenant_id, user_id, role_id) VALUES ($1, $2, $3)`,
        [invitation.tenantId, user.id, invitation.roleId]
      );
    });

    invitations.delete(token);

    if (auditService && invitation.tenantId && newUserId) {
      auditService.emit({
        tenant_id: invitation.tenantId,
        actor_user_id: newUserId,
        action: 'auth.register',
        resource_type: 'auth',
        resource_id: newUserId,
        request_id: req.requestId || randomUUID(),
        occurred_at: new Date().toISOString(),
        metadata: {
          email: invitation.email,
          method: 'POST',
          path: '/api/auth/accept-invite',
        },
      }).catch(() => {});
    }

    return res.status(201).json({ message: 'Account created successfully' });
  } catch (error) {
    if (error.status) return res.status(error.status).json({ error: error.message });
    appLogger.error('accept-invite error', { method: req.method, url: req.originalUrl, error: error.message });
    return res.status(500).json({ error: 'Internal server error' });
  }
});

app.post('/api/auth/register', rateLimit({ windowMs: 60_000, max: 10 }), async (req, res) => {
  if (!postgresStorage) {
    return res.status(503).json({ error: 'PostgreSQL storage is required for registration' });
  }

  const emailResult = requiredText(req.body?.email, 'Email', 254);
  const passwordResult = requiredText(req.body?.password, 'Password', 256);
  const displayNameResult = requiredText(req.body?.displayName, 'Display name', 240);
  const roleResult = requiredText(req.body?.role, 'Role', 120);

  if (emailResult.error || passwordResult.error || displayNameResult.error || roleResult.error) {
    return res.status(400).json({ error: emailResult.error || passwordResult.error || displayNameResult.error || roleResult.error });
  }

  const email = emailResult.value.toLowerCase();
  const roleName = roleResult.value.trim();
  const tenantId = req.user?.tenantId;

  if (!tenantId) {
    return res.status(403).json({ error: 'Tenant context is required' });
  }

  try {
    let roleId = null;
    await postgresStorage.withTenantTransaction(tenantId, async (tx) => {
      const roleResult = await tx.query(
        `SELECT id FROM roles WHERE tenant_id = $1 AND name = $2 LIMIT 1`,
        [tenantId, roleName]
      );
      if (roleResult.rows.length === 0) {
        const error = new Error('Role not found');
        error.status = 404;
        throw error;
      }
      roleId = roleResult.rows[0].id;

      const usersRepo = createUsersRepository(tx);
      const existing = await usersRepo.findByEmail(email);
      if (existing) {
        const error = new Error('User already exists');
        error.status = 409;
        throw error;
      }

      const user = await usersRepo.create({
        email,
        displayName: displayNameResult.value,
        password: passwordResult.value,
        status: 'active',
      });

      await tx.query(
        `INSERT INTO user_roles (tenant_id, user_id, role_id) VALUES ($1, $2, $3)`,
        [tenantId, user.id, roleId]
      );
    });

    if (auditService && tenantId) {
      auditService.emit({
        tenant_id: tenantId,
        actor_user_id: req.user?.id || null,
        action: 'auth.register',
        resource_type: 'auth',
        resource_id: null,
        request_id: req.requestId || randomUUID(),
        occurred_at: new Date().toISOString(),
        metadata: {
          email,
          method: 'POST',
          path: '/api/auth/register',
          role: roleName,
        },
      }).catch(() => {});
    }

    return res.status(201).json({ message: 'User registered successfully' });
  } catch (error) {
    if (error.status) return res.status(error.status).json({ error: error.message });
    appLogger.error('register error', { method: req.method, url: req.originalUrl, error: error.message });
    return res.status(500).json({ error: 'Internal server error' });
  }
});

app.get('/api/roles', async (req, res) => {
  if (!postgresStorage || !req.user?.tenantId) {
    return res.status(503).json({ error: 'PostgreSQL storage is required for roles' });
  }

  try {
    const roles = await postgresStorage.withTenantTransaction(req.user.tenantId, async (tx) => {
      const result = await tx.query(
        `SELECT id, name, permissions, created_at AS "createdAt" FROM roles WHERE tenant_id = $1 ORDER BY name ASC`,
        [req.user.tenantId]
      );
      return result.rows;
    });
    return res.json(roles);
  } catch (error) {
    appLogger.error('list roles error', { method: req.method, url: req.originalUrl, error: error.message });
    return res.status(500).json({ error: 'Internal server error' });
  }
});

app.post('/api/roles', async (req, res) => {
  if (!postgresStorage || !req.user?.tenantId) {
    return res.status(503).json({ error: 'PostgreSQL storage is required for roles' });
  }

  const nameResult = requiredText(req.body?.name, 'Name', 120);
  const permissions = req.body?.permissions;

  if (nameResult.error) {
    return res.status(400).json({ error: nameResult.error });
  }

  if (!permissions || typeof permissions !== 'object' || Array.isArray(permissions)) {
    return res.status(400).json({ error: 'permissions must be an object' });
  }

  try {
    const role = await postgresStorage.withTenantTransaction(req.user.tenantId, async (tx) => {
      const result = await tx.query(`
        INSERT INTO roles (tenant_id, name, permissions)
        VALUES ($1, $2, $3::jsonb)
        RETURNING id, name, permissions, created_at AS "createdAt", updated_at AS "updatedAt"
      `, [req.user.tenantId, nameResult.value.trim(), JSON.stringify(permissions)]);
      return result.rows[0];
    });

    return res.status(201).json(role);
  } catch (error) {
    if (error.code === '23505') {
      return res.status(409).json({ error: 'Role already exists for this tenant' });
    }
    appLogger.error('create role error', { method: req.method, url: req.originalUrl, error: error.message });
    return res.status(500).json({ error: 'Internal server error' });
  }
});

app.post('/api/auth/logout', async (req, res) => {
  if (req.session?.token) {
    try { await deleteSession(req.session.token); } catch {}
  }
  clearAuthCookies(res);
  setGauge('active_sessions', sessions.size + (sessionStore ? -1 : 0));

  if (auditService && req.user?.tenantId) {
    auditService.emit({
      tenant_id: req.user.tenantId,
      actor_user_id: req.user.id || null,
      action: 'auth.logout',
      resource_type: 'auth',
      resource_id: null,
      request_id: req.requestId || randomUUID(),
      occurred_at: new Date().toISOString(),
      metadata: {
        method: 'POST',
        path: '/api/auth/logout',
      },
    }).catch(() => {});
  }

  return res.status(204).end();
});

app.get('/api/db', async (req, res) => {
  const db = await readDB();
  res.json(db);
});

app.get('/api/chats', async (req, res) => {
  const db = await readDB();
  if (chatRouteGate.mode === 'json') return res.json(db.chats);
  const chats = await Promise.all(db.chats.map(chat => postgresBackedChat(req, chat)));
  return res.json(chats);
});

app.post('/api/chats/:id/messages', ...rbacGuard('chats:write'), async (req, res) => {
  const chatId = parseChatId(req.params.id);
  const textResult = requiredText(req.body?.text, 'Text content');
  const sender = req.body?.sender || 'agent';
  const activeChatId = req.body?.activeChatId === undefined
    ? chatId
    : parseChatId(req.body.activeChatId);

  if (chatId === null) return res.status(400).json({ error: 'Chat id must be a positive integer' });
  if (textResult.error) return res.status(400).json({ error: textResult.error });
  if (!['agent', 'customer', 'bot', 'system'].includes(sender)) {
    return res.status(400).json({ error: 'Invalid sender' });
  }
  if (activeChatId === null) return res.status(400).json({ error: 'activeChatId must be a positive integer' });

  let updatedChat;
  if (chatRouteGate.mode === 'postgres') {
    const db = await readDB();
    const metadataChat = db.chats.find(chat => chat.id === chatId);
    if (!metadataChat) return res.status(404).json({ error: 'Chat not found' });

    const written = await chatRouteGate.runtime.writeMessage(req, chatId, {
      sender,
      text: textResult.value,
    });
    if (!written) return res.status(404).json({ error: 'Chat not found' });

    await chatRouteGate.runtime.touchMetadata(req, chatId, { displayTime: 'Just now' });
    updatedChat = await postgresBackedChat(req, metadataChat);
  } else {
    updatedChat = await updateDB(db => {
      const chatIndex = db.chats.findIndex(c => c.id === chatId);
      if (chatIndex === -1) return null;

      const timeString = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      db.chats[chatIndex].messages.push({ sender, text: textResult.value, time: timeString });
      db.chats[chatIndex].time = 'Just now';
      return db.chats[chatIndex];
    });
  }

  if (!updatedChat) return res.status(404).json({ error: 'Chat not found' });
  res.status(201).json(updatedChat);
  incrementCounter('messages_sent', { sender, chatId: String(chatId) });

  setTimeout(async () => {
    try {
      let responseText = `Hi, thank you for writing back! I am currently away but our team will update you as soon as possible.`;
      const lowercaseText = textResult.value.toLowerCase();

      if (lowercaseText.includes('help') || lowercaseText.includes('support')) {
        responseText = `Got it. I've routed this conversation to our priority support desk. Alex Rivera will review this shortly!`;
      } else if (lowercaseText.includes('order') || lowercaseText.includes('track')) {
        responseText = `Sure thing! You can track all active orders directly in your customer profile page, or click: shopify.com/orders`;
      } else if (lowercaseText.includes('price') || lowercaseText.includes('cost')) {
        responseText = `Our standard pricing starts at $45/month (Basic) up to $97/month (Pro). Let us know if you'd like a custom demo.`;
      }

      if (chatRouteGate.mode === 'postgres') {
        await chatRouteGate.runtime.writeMessage(req, chatId, {
          sender: 'customer',
          text: responseText,
        });
        incrementCounter('messages_received', { chatId: String(chatId), sender: 'customer' });
        const currentState = await chatRouteGate.runtime.read(req, chatId);
        const currentUnread = currentState?.metadata?.unread || 0;
        const newUnread = chatId !== activeChatId ? currentUnread + 1 : 0;
        await chatRouteGate.runtime.touchMetadata(req, chatId, {
          displayTime: 'Just now',
          unread: newUnread,
        });
        return;
      }

      await updateDB(liveDb => {
        const liveChatIndex = liveDb.chats.findIndex(c => c.id === chatId);
        if (liveChatIndex === -1) return;

        liveDb.chats[liveChatIndex].messages.push({
          sender: 'customer',
          text: responseText,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        });
        liveDb.chats[liveChatIndex].time = 'Just now';
        liveDb.chats[liveChatIndex].unread = chatId !== activeChatId
          ? (liveDb.chats[liveChatIndex].unread || 0) + 1
          : 0;
      });
      incrementCounter('messages_received', { chatId: String(chatId), sender: 'customer' });
    } catch (e) {
      appLogger.error('simulated bot reply error', { chatId, error: e.message });
      incrementCounter('messages_failed', { chatId: String(chatId), reason: 'bot_reply' });
    }
  }, 1500);
});

app.post('/api/chats/:id/read', ...rbacGuard('chats:write'), async (req, res) => {
  const chatId = parseChatId(req.params.id);
  if (chatId === null) return res.status(400).json({ error: 'Chat id must be a positive integer' });

  if (chatRouteGate.mode === 'postgres') {
    const db = await readDB();
    const metadataChat = db.chats.find(chat => chat.id === chatId);
    if (!metadataChat) return res.status(404).json({ error: 'Chat not found' });
    const metadata = await chatRouteGate.runtime.markRead(req, chatId);
    if (!metadata) return res.status(404).json({ error: 'Chat not found' });
    return res.json(await postgresBackedChat(req, metadataChat));
  }

  const updatedChat = await updateDB(db => {
    const chatIndex = db.chats.findIndex(c => c.id === chatId);
    if (chatIndex === -1) return null;
    db.chats[chatIndex].unread = 0;
    return db.chats[chatIndex];
  });

  if (updatedChat) return res.json(updatedChat);
  return res.status(404).json({ error: 'Chat not found' });
});

app.post('/api/chats/:id/tags', ...rbacGuard('chats:write'), async (req, res) => {
  const chatId = parseChatId(req.params.id);
  const { tags } = req.body || {};
  if (chatId === null) return res.status(400).json({ error: 'Chat id must be a positive integer' });

  const tagError = validateTags(tags);
  if (tagError) return res.status(400).json({ error: tagError });

  if (chatRouteGate.mode === 'postgres') {
    const db = await readDB();
    const metadataChat = db.chats.find(chat => chat.id === chatId);
    if (!metadataChat) return res.status(404).json({ error: 'Chat not found' });
    const metadata = await chatRouteGate.runtime.replaceTags(req, chatId, tags);
    if (!metadata) return res.status(404).json({ error: 'Chat not found' });
    return res.json(await postgresBackedChat(req, metadataChat));
  }

  const updatedChat = await updateDB(db => {
    const chatIndex = db.chats.findIndex(c => c.id === chatId);
    if (chatIndex === -1) return null;
    db.chats[chatIndex].details.tags = tags.map(tag => tag.trim());
    return db.chats[chatIndex];
  });

  if (updatedChat) return res.json(updatedChat);
  return res.status(404).json({ error: 'Chat not found' });
});

app.get('/api/ai-config', async (req, res) => {
  if (chatRouteGate.mode === 'postgres') {
    const tenantId = req.user?.tenantId;
    if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });
    const config = await postgresStorage.withTenantTransaction(tenantId, tx => {
      const repo = createAiConfigRepository(tx);
      return repo.get();
    });
    return res.json(config || {});
  }
  const db = await readDB();
  res.json(db.aiConfig);
});

app.post('/api/ai-config', ...rbacGuard('ai-config:write'), async (req, res) => {
  const { agentName, persona, knowledgeBase, qaPairs } = req.body || {};
  const nameResult = requiredText(agentName, 'agentName', 120);
  const knowledgeResult = requiredText(knowledgeBase, 'knowledgeBase', 10000);
  if (nameResult.error || knowledgeResult.error) {
    return res.status(400).json({ error: nameResult.error || knowledgeResult.error });
  }
  if (!['sales', 'support', 'lead'].includes(persona)) {
    return res.status(400).json({ error: 'persona must be sales, support, or lead' });
  }
  if (!Array.isArray(qaPairs) || qaPairs.length > 100 || qaPairs.some(pair => (
    !pair ||
    requiredText(pair.q, 'question', 500).error ||
    requiredText(pair.a, 'answer', 2000).error
  ))) {
    return res.status(400).json({ error: 'qaPairs must contain at most 100 valid question/answer pairs' });
  }

  if (chatRouteGate.mode === 'postgres') {
    const tenantId = req.user?.tenantId;
    if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });
    const config = await postgresStorage.withTenantTransaction(tenantId, tx => {
      const repo = createAiConfigRepository(tx);
      return repo.replace({
        agentName: nameResult.value,
        persona,
        knowledgeBase: knowledgeResult.value,
        qaPairs: qaPairs.map(pair => ({ q: pair.q.trim(), a: pair.a.trim() })),
      });
    });
    return res.json(config);
  }

  const aiConfig = {
    agentName: nameResult.value,
    persona,
    knowledgeBase: knowledgeResult.value,
    qaPairs: qaPairs.map(pair => ({ q: pair.q.trim(), a: pair.a.trim() })),
  };
  const savedConfig = await updateDB(db => {
    db.aiConfig = aiConfig;
    return db.aiConfig;
  });
  return res.json(savedConfig);
});

app.post('/api/ai/config', ...rbacGuard('ai-config:write'), async (req, res) => {
  if (!governedAIService) {
    return res.status(503).json({ error: 'Governed AI service is not available' });
  }
  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });

  const { config, risk_level } = req.body || {};
  if (!config || typeof config !== 'object' || Array.isArray(config)) {
    return res.status(400).json({ error: 'config must be a non-null object' });
  }

  try {
    const validated = await governedAIService.validateConfig(config);
    if (!validated) {
      return res.status(400).json({ error: 'Invalid AI config' });
    }
  } catch (error) {
    return res.status(error.status || 400).json({ error: error.message });
  }

  try {
    const saved = await postgresStorage.withTenantTransaction(tenantId, async (_tx) => {
      const telemetry = aiTelemetry || createAiTelemetry({ connect: () => ({ query: async () => ({ rows: [] }), release: () => {} }) });
      const approval = aiApproval || createAiApproval({ connect: () => ({ query: async () => ({ rows: [] }), release: () => {} }) });
      const service = createGovernedAIService({ telemetry, approval, pool: postgresPool || { connect: () => ({ query: async () => ({ rows: [] }), release: () => {} }) } });
      return service.setConfig(tenantId, config, risk_level);
    });
    return res.status(201).json(saved);
  } catch (error) {
    return res.status(error.status || 500).json({ error: error.message });
  }
});

app.post('/api/ai/chat', async (req, res) => {
  if (!governedAIService) {
    return res.status(503).json({ error: 'Governed AI service is not available' });
  }
  const tenantId = req.user?.tenantId;
  const userId = req.user?.id || req.user?.email || 'anonymous';
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });

  const { messages } = req.body || {};
  if (!Array.isArray(messages) || messages.length === 0) {
    return res.status(400).json({ error: 'messages must be a non-empty array' });
  }

  try {
    const response = await governedAIService.chat(tenantId, userId, messages, {
      requestId: req.requestId,
    });
    return res.json(response);
  } catch (error) {
    return res.status(error.status || 500).json({ error: error.message });
  }
});

app.get('/api/ai/approvals', async (req, res) => {
  if (!governedAIService) {
    return res.status(503).json({ error: 'Governed AI service is not available' });
  }
  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });

  try {
    const approvals = await governedAIService.getApprovals(tenantId);
    return res.json(approvals);
  } catch (error) {
    return res.status(error.status || 500).json({ error: error.message });
  }
});

app.post('/api/ai/approvals/:id/approve', async (req, res) => {
  if (!governedAIService) {
    return res.status(503).json({ error: 'Governed AI service is not available' });
  }
  const tenantId = req.user?.tenantId;
  const userId = req.user?.id || req.user?.email;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });
  if (!userId) return res.status(400).json({ error: 'User context is required' });

  const approvalId = req.params.id;
  try {
    const result = await governedAIService.approveApproval(tenantId, approvalId, userId);
    if (!result) return res.status(404).json({ error: 'Approval not found or already processed' });
    return res.json(result);
  } catch (error) {
    return res.status(error.status || 500).json({ error: error.message });
  }
});

app.post('/api/ai/approvals/:id/reject', async (req, res) => {
  if (!governedAIService) {
    return res.status(503).json({ error: 'Governed AI service is not available' });
  }
  const tenantId = req.user?.tenantId;
  const userId = req.user?.id || req.user?.email;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });
  if (!userId) return res.status(400).json({ error: 'User context is required' });

  const approvalId = req.params.id;
  try {
    const result = await governedAIService.rejectApproval(tenantId, approvalId, userId);
    if (!result) return res.status(404).json({ error: 'Approval not found or already processed' });
    return res.json(result);
  } catch (error) {
    return res.status(error.status || 500).json({ error: error.message });
  }
});

app.get('/api/ai/telemetry', async (req, res) => {
  if (!governedAIService) {
    return res.status(503).json({ error: 'Governed AI service is not available' });
  }
  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });

  const { requestId, approvalStatus, model, limit, offset } = req.query;
  try {
    const events = await governedAIService.getTelemetry(tenantId, {
      requestId: typeof requestId === 'string' ? requestId : undefined,
      approvalStatus: typeof approvalStatus === 'string' ? approvalStatus : undefined,
      model: typeof model === 'string' ? model : undefined,
      limit: limit ? Number(limit) : undefined,
      offset: offset ? Number(offset) : undefined,
    });
    return res.json(events);
  } catch (error) {
    return res.status(error.status || 500).json({ error: error.message });
  }
});

app.get('/api/flow-nodes', async (req, res) => {
  if (chatRouteGate.mode === 'postgres') {
    const tenantId = req.user?.tenantId;
    if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });
    const nodes = await postgresStorage.withTenantTransaction(tenantId, tx => {
      const repo = createFlowNodesRepository(tx);
      return repo.list();
    });
    return res.json(nodes);
  }
  const db = await readDB();
  res.json(db.flowNodes);
});

app.post('/api/flow-nodes', ...rbacGuard('flow-nodes:write'), async (req, res) => {
  const { nodes } = req.body || {};
  if (!Array.isArray(nodes) || nodes.length > 200 || nodes.some(node => !node || typeof node !== 'object')) {
    return res.status(400).json({ error: 'Nodes must be an array of at most 200 objects' });
  }
  if (chatRouteGate.mode === 'postgres') {
    const tenantId = req.user?.tenantId;
    if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });
    const savedNodes = await postgresStorage.withTenantTransaction(tenantId, tx => {
      const repo = createFlowNodesRepository(tx);
      return repo.replace(nodes);
    });
    return res.json(savedNodes);
  }
  const savedNodes = await updateDB(db => {
    db.flowNodes = nodes;
    return db.flowNodes;
  });
  return res.json(savedNodes);
});

app.get('/api/campaigns', async (req, res) => {
  if (chatRouteGate.mode === 'postgres') {
    const tenantId = req.user?.tenantId;
    if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });
    const campaigns = await postgresStorage.withTenantTransaction(tenantId, tx => {
      const repo = createCampaignsRepository(tx);
      return repo.list();
    });
    return res.json(campaigns);
  }
  const db = await readDB();
  res.json(db.campaigns);
});

app.post('/api/campaigns', ...rbacGuard('campaigns:write'), async (req, res) => {
  const { name, channel, target } = req.body || {};
  const nameResult = requiredText(name, 'name', 160);
  const targetResult = requiredText(target, 'target', 120);
  if (nameResult.error || targetResult.error) {
    return res.status(400).json({ error: nameResult.error || targetResult.error });
  }
  if (!['whatsapp', 'line', 'messenger', 'tiktok', 'shopify'].includes(channel)) {
    return res.status(400).json({ error: 'Invalid campaign channel' });
  }

  if (chatRouteGate.mode === 'postgres') {
    const tenantId = req.user?.tenantId;
    if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });
    const campaign = await postgresStorage.withTenantTransaction(tenantId, tx => {
      const repo = createCampaignsRepository(tx);
      return repo.create({ name: nameResult.value, channel, target: targetResult.value });
    });
    return res.status(201).json(campaign);
  }

  const newCamp = await updateDB(db => {
    const campaign = {
      id: Date.now(),
      name: nameResult.value,
      status: 'completed',
      channel,
      target: targetResult.value,
      recipients: Math.floor(200 + Math.random() * 800),
      delivered: '100%',
      opened: `${(70 + Math.random() * 20).toFixed(1)}%`,
      converted: `${(5 + Math.random() * 10).toFixed(1)}%`,
      date: new Date().toISOString().split('T')[0],
    };
    db.campaigns.unshift(campaign);
    return campaign;
  });
  return res.status(201).json(newCamp);
});

app.post('/api/campaigns/:id/start', ...rbacGuard('campaigns:write'), async (req, res) => {
  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });

  const campaignId = req.params.id;
  if (!campaignId) return res.status(400).json({ error: 'Campaign id is required' });

  try {
    if (chatRouteGate.mode === 'postgres' && postgresPool) {
      const client = await postgresPool.connect();
      try {
        await client.query('BEGIN');
        const repo = createCampaignsRepository({ ...client, tenantId });
        const campaign = await repo.updateStatus(campaignId, 'running');
        if (!campaign) {
          await client.query('ROLLBACK');
          return res.status(404).json({ error: 'Campaign not found' });
        }
        await client.query(
          `INSERT INTO campaign_executions (tenant_id, campaign_id, contact_id, status, action_type, payload)
           SELECT $1, $2, id, 'pending', 'send_message', jsonb_build_object('channel', $3, 'data', jsonb_build_object('to', external_id))
           FROM contacts
           WHERE tenant_id = $1 AND deleted_at IS NULL
           ON CONFLICT DO NOTHING`,
          [tenantId, campaignId, campaign.channel]
        );
        await client.query('COMMIT');
        return res.json(campaign);
      } catch (error) {
        await client.query('ROLLBACK').catch(() => {});
        throw error;
      } finally {
        client.release();
      }
    }

    const db = await readDB();
    const campaign = db.campaigns.find(c => c.id === Number(campaignId));
    if (!campaign) return res.status(404).json({ error: 'Campaign not found' });
    campaign.status = 'running';
    return res.json(campaign);
  } catch (error) {
    appLogger.error('start campaign failed', { method: req.method, url: req.originalUrl, error: error.message });
    return res.status(500).json({ error: 'Internal server error' });
  }
});

app.post('/api/campaigns/:id/pause', ...rbacGuard('campaigns:write'), async (req, res) => {
  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });

  const campaignId = req.params.id;
  if (!campaignId) return res.status(400).json({ error: 'Campaign id is required' });

  try {
    if (chatRouteGate.mode === 'postgres' && postgresPool) {
      const client = await postgresPool.connect();
      try {
        const repo = createCampaignsRepository({ ...client, tenantId });
        const campaign = await repo.updateStatus(campaignId, 'paused');
        if (!campaign) {
          client.release();
          return res.status(404).json({ error: 'Campaign not found' });
        }
        client.release();
        return res.json(campaign);
      } catch (error) {
        client.release();
        throw error;
      }
    }

    const db = await readDB();
    const campaign = db.campaigns.find(c => c.id === Number(campaignId));
    if (!campaign) return res.status(404).json({ error: 'Campaign not found' });
    campaign.status = 'paused';
    return res.json(campaign);
  } catch (error) {
    appLogger.error('pause campaign failed', { method: req.method, url: req.originalUrl, error: error.message });
    return res.status(500).json({ error: 'Internal server error' });
  }
});

app.post('/api/campaigns/:id/resume', ...rbacGuard('campaigns:write'), async (req, res) => {
  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });

  const campaignId = req.params.id;
  if (!campaignId) return res.status(400).json({ error: 'Campaign id is required' });

  try {
    if (chatRouteGate.mode === 'postgres' && postgresPool) {
      const client = await postgresPool.connect();
      try {
        const repo = createCampaignsRepository({ ...client, tenantId });
        const campaign = await repo.updateStatus(campaignId, 'running');
        if (!campaign) {
          client.release();
          return res.status(404).json({ error: 'Campaign not found' });
        }
        client.release();
        return res.json(campaign);
      } catch (error) {
        client.release();
        throw error;
      }
    }

    const db = await readDB();
    const campaign = db.campaigns.find(c => c.id === Number(campaignId));
    if (!campaign) return res.status(404).json({ error: 'Campaign not found' });
    campaign.status = 'running';
    return res.json(campaign);
  } catch (error) {
    appLogger.error('resume campaign failed', { method: req.method, url: req.originalUrl, error: error.message });
    return res.status(500).json({ error: 'Internal server error' });
  }
});

app.get('/api/campaigns/:id/executions', requireAuth, requireCsrf, async (req, res) => {
  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });

  const campaignId = req.params.id;
  if (!campaignId) return res.status(400).json({ error: 'Campaign id is required' });

  const limit = req.query.limit ? Number(req.query.limit) : 50;
  const offset = req.query.offset ? Number(req.query.offset) : 0;

  try {
    if (chatRouteGate.mode === 'postgres' && postgresPool) {
      const client = await postgresPool.connect();
      try {
        const executionsResult = await client.query(
          `SELECT id, campaign_id AS "campaignId", contact_id AS "contactId", status, attempt, max_attempts,
             last_error AS "lastError", scheduled_at AS "scheduledAt", executed_at AS "executedAt",
             completed_at AS "completedAt", metadata, created_at AS "createdAt", updated_at AS "updatedAt"
           FROM campaign_executions
           WHERE tenant_id = $1 AND campaign_id = $2
           ORDER BY created_at DESC
           LIMIT $3 OFFSET $4`,
          [tenantId, campaignId, limit, offset]
        );

        const deadLetterResult = await client.query(
          `SELECT id, campaign_id AS "campaignId", contact_id AS "contactId", reason, retry_count AS "retryCount",
             last_error AS "lastError", payload, created_at AS "createdAt", updated_at AS "updatedAt"
           FROM dead_letter_queue
           WHERE tenant_id = $1 AND campaign_id = $2
           ORDER BY created_at DESC
           LIMIT $3 OFFSET $4`,
          [tenantId, campaignId, limit, offset]
        );

        client.release();
        return res.json({
          executions: executionsResult.rows,
          deadLetters: deadLetterResult.rows,
        });
      } catch (error) {
        client.release();
        throw error;
      }
    }

    const db = await readDB();
    res.json({ executions: [], deadLetters: [] });
  } catch (error) {
    appLogger.error('list executions failed', { method: req.method, url: req.originalUrl, error: error.message });
    return res.status(500).json({ error: 'Internal server error' });
  }
});

app.get('/api/campaigns/workers/health', requireAuth, requireCsrf, async (req, res) => {
  if (!campaignWorker) {
    return res.json({ status: 'disabled', activeWorkers: 0, queueDepth: 0 });
  }

  return res.json({
    status: campaignWorker.isHealthy() ? 'healthy' : 'unhealthy',
    activeWorkers: campaignWorker.getActiveCount(),
    queueDepth: campaignWorker.getQueueDepth(),
  });
});

app.get('/api/integrations', async (req, res) => {
  if (chatRouteGate.mode === 'postgres') {
    const tenantId = req.user?.tenantId;
    if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });
    const integrations = await postgresStorage.withTenantTransaction(tenantId, tx => {
      const repo = createIntegrationsRepository(tx);
      return repo.list();
    });
    return res.json({ integrations, syncLogs: [] });
  }
  const db = await readDB();
  res.json({ integrations: db.integrations, syncLogs: db.syncLogs });
});

app.post('/api/integrations/:id/toggle', ...rbacGuard('integrations:write'), async (req, res) => {
  const integrationId = req.params.id;
  if (!/^[a-z0-9-]{1,64}$/.test(integrationId)) {
    return res.status(400).json({ error: 'Invalid integration id' });
  }

  if (chatRouteGate.mode === 'postgres') {
    const tenantId = req.user?.tenantId;
    if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });
    const result = await postgresStorage.withTenantTransaction(tenantId, async tx => {
      const repo = createIntegrationsRepository(tx);
      const existing = await repo.findByProvider(integrationId);
      if (!existing) return { notFound: true };
      const toggled = await repo.toggleStatus(existing.id);
      if (!toggled) return { notFound: true };
      return { integrations: [toggled], syncLogs: [] };
    });
    if (result.notFound) return res.status(404).json({ error: 'Integration not found' });
    return res.json(result);
  }

  const db = await readDB();
  const configuredIntegration = db.integrations.find(item => item.id === integrationId);
  if (!configuredIntegration) return res.status(404).json({ error: 'Integration not found' });
  if (configuredIntegration.verified !== true) {
    return res.status(409).json({ error: 'Integration verification is required before enabling provider routes' });
  }

  const result = await updateDB(currentDb => {
    const index = currentDb.integrations.findIndex(item => item.id === integrationId);
    if (index === -1) return null;

    const nextStatus = currentDb.integrations[index].status === 'connected' ? 'disconnected' : 'connected';
    currentDb.integrations[index].status = nextStatus;
    const timestamp = new Date().toLocaleTimeString();
    const actionText = nextStatus === 'connected' ? 'Connected & Webhooks Subscribed' : 'Disconnected & Sync suspended';
    currentDb.syncLogs.unshift(`[${timestamp}] ${currentDb.integrations[index].name} status updated: ${actionText}`);
    return { integrations: currentDb.integrations, syncLogs: currentDb.syncLogs };
  });

  if (result) return res.json(result);
  return res.status(404).json({ error: 'Integration not found' });
});

app.post('/api/security/api-keys', requireAuth, requireCsrf, ...rbacGuard('security:write'), async (req, res) => {
  if (!securityServicesEnabled) {
    return res.status(503).json({ error: 'Security services are not available' });
  }
  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });

  const { name, expiresInDays } = req.body || {};
  const expiresArg = expiresInDays === undefined ? undefined : Number(expiresInDays);

  try {
    const result = await postgresStorage.withTenantTransaction(tenantId, tx => {
      const manager = createApiKeyManager(tx);
      return manager.create({ name, expiresInDays: expiresArg });
    });
    return res.status(201).json({ key: result.key, apiKey: result.record });
  } catch (error) {
    if (error instanceof TypeError || error instanceof RangeError) {
      return res.status(400).json({ error: error.message });
    }
    appLogger.error('api-key create failed', { error: error.message });
    return res.status(500).json({ error: 'Failed to create API key' });
  }
});

app.get('/api/security/api-keys', requireAuth, requireCsrf, ...rbacGuard('security:read'), async (req, res) => {
  if (!securityServicesEnabled) {
    return res.status(503).json({ error: 'Security services are not available' });
  }
  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });

  try {
    const records = await postgresStorage.withTenantTransaction(tenantId, tx => {
      const manager = createApiKeyManager(tx);
      return manager.list();
    });
    return res.json({ apiKeys: records });
  } catch (error) {
    appLogger.error('api-key list failed', { error: error.message });
    return res.status(500).json({ error: 'Failed to list API keys' });
  }
});

app.post('/api/security/api-keys/:id/rotate', requireAuth, requireCsrf, ...rbacGuard('security:write'), async (req, res) => {
  if (!securityServicesEnabled) {
    return res.status(503).json({ error: 'Security services are not available' });
  }
  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });

  const { id } = req.params;
  const { gracePeriodDays } = req.body || {};
  const graceArg = gracePeriodDays === undefined ? undefined : Number(gracePeriodDays);

  try {
    const result = await postgresStorage.withTenantTransaction(tenantId, async tx => {
      const manager = createApiKeyManager(tx);
      const existing = await manager.getById(id);
      if (!existing) return { notFound: true };
      return manager.rotate(id, { gracePeriodDays: graceArg });
    });
    if (result.notFound || !result) return res.status(404).json({ error: 'API key not found' });
    return res.json({ key: result.key, apiKey: result.record });
  } catch (error) {
    if (error instanceof TypeError || error instanceof RangeError) {
      return res.status(400).json({ error: error.message });
    }
    appLogger.error('api-key rotate failed', { error: error.message });
    return res.status(500).json({ error: 'Failed to rotate API key' });
  }
});

app.delete('/api/security/api-keys/:id', requireAuth, requireCsrf, ...rbacGuard('security:write'), async (req, res) => {
  if (!securityServicesEnabled) {
    return res.status(503).json({ error: 'Security services are not available' });
  }
  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });

  const { id } = req.params;
  try {
    const revoked = await postgresStorage.withTenantTransaction(tenantId, tx => {
      const manager = createApiKeyManager(tx);
      return manager.revoke(id);
    });
    if (!revoked) return res.status(404).json({ error: 'API key not found' });
    return res.json({ apiKey: revoked });
  } catch (error) {
    if (error instanceof TypeError) {
      return res.status(400).json({ error: error.message });
    }
    appLogger.error('api-key revoke failed', { error: error.message });
    return res.status(500).json({ error: 'Failed to revoke API key' });
  }
});

app.get('/api/security/audit', requireAuth, requireCsrf, ...rbacGuard('security:read'), async (req, res) => {
  if (!securityServicesEnabled) {
    return res.status(503).json({ error: 'Security services are not available' });
  }
  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });

  const { secretId } = req.query;
  try {
    const logs = await postgresStorage.withTenantTransaction(tenantId, tx => {
      const vault = createSecretsVault({ tx, masterKey: securityMasterKey });
      return vault.listAccessLogs({ secretId: typeof secretId === 'string' ? secretId : null });
    });
    return res.json({ audit: logs });
  } catch (error) {
    if (error instanceof TypeError) {
      return res.status(400).json({ error: error.message });
    }
    appLogger.error('security audit failed', { error: error.message });
    return res.status(500).json({ error: 'Failed to retrieve security audit logs' });
  }
});

app.get('/api/commerce/attribution', requireAuth, requireCsrf, async (req, res) => {
  if (!attributionEngine) {
    return res.status(503).json({ error: 'Attribution engine is not available' });
  }

  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });

  const { contactId, channel, model, startDate, endDate, limit, offset } = req.query;

  try {
    const report = await attributionEngine.getReport({
      tenantId,
      contactId: typeof contactId === 'string' ? contactId : null,
      channel: typeof channel === 'string' ? channel : null,
      model: typeof model === 'string' ? model : null,
      startDate: typeof startDate === 'string' ? startDate : null,
      endDate: typeof endDate === 'string' ? endDate : null,
      limit: limit ? Number(limit) : 100,
      offset: offset ? Number(offset) : 0,
    });
    return res.json(report);
  } catch (error) {
    appLogger.error('attribution report failed', { error: error.message });
    return res.status(error.status || 500).json({ error: error.message || 'Internal server error' });
  }
});

app.post('/api/commerce/attribution/touchpoints', requireAuth, requireCsrf, async (req, res) => {
  if (!attributionEngine) {
    return res.status(503).json({ error: 'Attribution engine is not available' });
  }

  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });

  const { contactId, channel, eventType, campaignId, messageId, metadata, occurredAt } = req.body || {};

  try {
    const touchpoint = await attributionEngine.recordTouchpoint({
      tenantId,
      contactId,
      channel,
      eventType,
      campaignId,
      messageId,
      metadata,
      occurredAt,
    });
    return res.status(201).json(touchpoint);
  } catch (error) {
    appLogger.error('record touchpoint failed', { error: error.message });
    return res.status(error.status || 400).json({ error: error.message || 'Invalid touchpoint' });
  }
});

app.post('/api/commerce/reconcile', requireAuth, requireCsrf, async (req, res) => {
  if (!reconciliationEngine) {
    return res.status(503).json({ error: 'Reconciliation engine is not available' });
  }

  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });

  const { platformOrders, mode } = req.body || {};
  if (!Array.isArray(platformOrders)) {
    return res.status(400).json({ error: 'platformOrders must be an array' });
  }

  try {
    const results = await reconciliationEngine.reconcileOrders({
      tenantId,
      platformOrders,
      mode: typeof mode === 'string' ? mode : 'automatic',
    });
    return res.json({ results, count: results.length });
  } catch (error) {
    appLogger.error('reconciliation failed', { error: error.message });
    return res.status(error.status || 500).json({ error: error.message || 'Internal server error' });
  }
});

app.get('/api/commerce/reconciliation-report', requireAuth, requireCsrf, async (req, res) => {
  if (!reconciliationEngine) {
    return res.status(503).json({ error: 'Reconciliation engine is not available' });
  }

  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });

  const { status, platform, startDate, endDate, limit, offset } = req.query;

  try {
    const report = await reconciliationEngine.getReconciliationReport({
      tenantId,
      status: typeof status === 'string' ? status : null,
      platform: typeof platform === 'string' ? platform : null,
      startDate: typeof startDate === 'string' ? startDate : null,
      endDate: typeof endDate === 'string' ? endDate : null,
      limit: limit ? Number(limit) : 100,
      offset: offset ? Number(offset) : 0,
    });
    return res.json(report);
  } catch (error) {
    appLogger.error('reconciliation report failed', { error: error.message });
    return res.status(error.status || 500).json({ error: error.message || 'Internal server error' });
  }
});

app.post('/api/commerce/reconciliation/:id/resolve', requireAuth, requireCsrf, async (req, res) => {
  if (!reconciliationEngine) {
    return res.status(503).json({ error: 'Reconciliation engine is not available' });
  }

  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });

  const { id } = req.params;
  const { resolution } = req.body || {};

  try {
    const result = await reconciliationEngine.resolveReconciliation(tenantId, id, resolution);
    return res.json(result);
  } catch (error) {
    appLogger.error('resolve reconciliation failed', { error: error.message });
    return res.status(error.status || 500).json({ error: error.message || 'Internal server error' });
  }
});

app.post('/api/webhooks/shopify/orders/create', requireAuth, async (req, res) => {
  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });
  if (!shopifyAdapter) return res.status(503).json({ error: 'Shopify adapter is not available' });

  try {
    const result = await shopifyAdapter.handleOrderWebhook(tenantId, req.body);
    return res.status(201).json(result);
  } catch (error) {
    appLogger.error('shopify order webhook failed', { error: error.message });
    return res.status(error.status || 500).json({ error: error.message || 'Internal server error' });
  }
});

app.post('/api/webhooks/shopify/inventory/update', requireAuth, async (req, res) => {
  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });
  if (!shopifyAdapter) return res.status(503).json({ error: 'Shopify adapter is not available' });

  try {
    const result = await shopifyAdapter.handleInventoryWebhook(tenantId, req.body);
    return res.json(result);
  } catch (error) {
    appLogger.error('shopify inventory webhook failed', { error: error.message });
    return res.status(error.status || 500).json({ error: error.message || 'Internal server error' });
  }
});

app.post('/api/webhooks/tiktok-shop/orders/create', requireAuth, async (req, res) => {
  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });
  if (!tiktokAdapter) return res.status(503).json({ error: 'TikTok Shop adapter is not available' });

  try {
    const result = await tiktokAdapter.handleFulfillmentWebhook(tenantId, req.body);
    return res.json(result);
  } catch (error) {
    appLogger.error('tiktok shop order webhook failed', { error: error.message });
    return res.status(error.status || 500).json({ error: error.message || 'Internal server error' });
  }
});

app.post('/api/webhooks/tiktok-shop/shop/status', requireAuth, async (req, res) => {
  const tenantId = req.user?.tenantId;
  if (!tenantId) return res.status(400).json({ error: 'Tenant context is required' });
  if (!tiktokAdapter) return res.status(503).json({ error: 'TikTok Shop adapter is not available' });

  try {
    const result = await tiktokAdapter.handleShopStatusChange(tenantId, req.body);
    return res.json(result);
  } catch (error) {
    appLogger.error('tiktok shop status webhook failed', { error: error.message });
    return res.status(error.status || 500).json({ error: error.message || 'Internal server error' });
  }
});

app.get('/api/consent/:contactId', async (req, res) => {
  const contactId = req.params.contactId;
  if (!contactId || typeof contactId !== 'string') {
    return res.status(400).json({ error: 'contactId is required' });
  }

  const tenantId = req.user?.tenantId;
  if (!tenantId) {
    return res.status(400).json({ error: 'Tenant context is required' });
  }

  if (!consentChecker) {
    return res.status(503).json({ error: 'Consent service is not available' });
  }

  const records = [];
  for (const channel of ['whatsapp', 'line', 'messenger', 'tiktok']) {
    const record = await consentChecker.getConsent(contactId, channel, tenantId);
    if (record) records.push(record);
  }

  return res.json(records);
});

app.post('/api/consent/:contactId', ...rbacGuard('integrations:write'), async (req, res) => {
  const contactId = req.params.contactId;
  const { channel, status } = req.body || {};

  if (!contactId || typeof contactId !== 'string') {
    return res.status(400).json({ error: 'contactId is required' });
  }
  if (typeof channel !== 'string' || !['whatsapp', 'line', 'messenger', 'tiktok'].includes(channel)) {
    return res.status(400).json({ error: 'channel must be whatsapp, line, messenger, or tiktok' });
  }
  if (typeof status !== 'string' || !['granted', 'revoked'].includes(status)) {
    return res.status(400).json({ error: "status must be 'granted' or 'revoked'" });
  }

  const tenantId = req.user?.tenantId;
  if (!tenantId) {
    return res.status(400).json({ error: 'Tenant context is required' });
  }

  if (!consentChecker) {
    return res.status(503).json({ error: 'Consent service is not available' });
  }

  const record = await consentChecker.setConsent(contactId, channel, status, tenantId);
  return res.status(201).json(record);
});

app.post('/api/channels/send', ...rbacGuard('integrations:write'), async (req, res) => {
  const { provider, contactId, type, payload } = req.body || {};

  if (!provider || typeof provider !== 'string') {
    return res.status(400).json({ error: 'provider is required' });
  }
  if (!['whatsapp', 'line', 'messenger', 'tiktok'].includes(provider)) {
    return res.status(400).json({ error: 'Invalid provider' });
  }
  if (!contactId || typeof contactId !== 'string') {
    return res.status(400).json({ error: 'contactId is required' });
  }
  if (!type || typeof type !== 'string') {
    return res.status(400).json({ error: 'type is required' });
  }
  if (!payload || typeof payload !== 'object') {
    return res.status(400).json({ error: 'payload must be an object' });
  }

  if (!adapterFactory) {
    return res.status(503).json({ error: 'Channel adapter factory is not available' });
  }

  try {
    const adapter = adapterFactory.getAdapter(provider);
    let result;

    switch (type) {
      case 'text':
        result = await adapter.sendText(contactId, payload.text || '');
        break;
      case 'image':
        result = await adapter.sendImage(contactId, payload.mediaUrl || payload.imageUrl || '', payload.caption || '');
        break;
      case 'document':
        result = await adapter.sendDocument(contactId, payload.mediaUrl || payload.documentUrl || '', payload.filename || '');
        break;
      case 'template':
        result = await adapter.sendTemplate(contactId, payload.templateName || '', payload.templateData || {});
        break;
      case 'quick_replies':
        result = await adapter.sendQuickReplies(contactId, payload.text || '', payload.quickReplies || []);
        break;
      default:
        return res.status(400).json({ error: `Unsupported message type: ${type}` });
    }

    res.status(200).json({
      provider,
      contactId,
      type,
      result,
      mode: adapterFactory.mode,
    });
  } catch (error) {
    appLogger.error('channel send failed', { provider, contactId, type, error: error.message });
    res.status(error.status || 500).json({ error: error.message || 'Channel send failed' });
  }
});

function requireOwner(req, res, next) {
  if (req.user?.role === 'owner') return next();
  return res.status(403).json({ error: 'Owner role is required' });
}

app.get('/api/privacy/export', requireAuth, requireCsrf, async (req, res) => {
  if (!req.user?.tenantId) {
    return res.status(400).json({ error: 'Tenant context is required' });
  }

  try {
    const result = await dataExport.exportTenant(req.user.tenantId);
    res.setHeader('Content-Type', result.contentType);
    res.setHeader('Content-Disposition', `attachment; filename="${result.filename}"`);
    res.setHeader('Content-Length', Buffer.byteLength(result.buffer));
    res.end(result.buffer);
  } catch (error) {
    appLogger.error('export failed', { error: error.message });
    return res.status(500).json({ error: 'Export failed' });
  }
});

app.post('/api/privacy/delete', requireAuth, requireCsrf, async (req, res) => {
  if (!req.user?.tenantId) {
    return res.status(400).json({ error: 'Tenant context is required' });
  }

  const { confirm, types, beforeDate } = req.body || {};

  if (!Array.isArray(types) || types.length === 0) {
    return res.status(400).json({ error: 'types must be a non-empty array' });
  }

  try {
    const outcome = await dataDeletion.deleteTenant(req.user.tenantId, {
      confirm: confirm === true,
      types,
      beforeDate: typeof beforeDate === 'string' ? beforeDate : null,
    });
    return res.json(outcome);
  } catch (error) {
    if (error.message.includes('confirmation') || error.message.includes('Invalid deletion') || error.message.includes('Cannot delete audit_events')) {
      return res.status(400).json({ error: error.message });
    }
    appLogger.error('deletion failed', { error: error.message });
    return res.status(500).json({ error: 'Deletion failed' });
  }
});

app.get('/api/privacy/retention-status', requireAuth, requireCsrf, async (req, res) => {
  if (!req.user?.tenantId) {
    return res.status(400).json({ error: 'Tenant context is required' });
  }
  if (!retentionPolicy) {
    return res.status(503).json({ error: 'Retention policy service is not available' });
  }

  try {
    const status = await retentionPolicy.getRetentionStatus(req.user.tenantId);
    return res.json(status);
  } catch (error) {
    appLogger.error('retention status failed', { error: error.message });
    return res.status(500).json({ error: 'Failed to get retention status' });
  }
});

app.post('/api/privacy/retention-purge', requireAuth, requireCsrf, requireOwner, async (req, res) => {
  if (!req.user?.tenantId) {
    return res.status(400).json({ error: 'Tenant context is required' });
  }
  if (!retentionPolicy) {
    return res.status(503).json({ error: 'Retention policy service is not available' });
  }

  const { customRetention } = req.body || {};

  try {
    const result = await retentionPolicy.purgeExpired(req.user.tenantId, customRetention);
    return res.json(result);
  } catch (error) {
    appLogger.error('retention purge failed', { error: error.message });
    return res.status(500).json({ error: 'Retention purge failed' });
  }
});

app.use((error, req, res, next) => {
  appLogger.error('unhandled request error', { method: req.method, url: req.originalUrl, error: error.message });
  if (res.headersSent) return next(error);
  if (error.message === 'Origin is not allowed by CORS') {
    return res.status(403).json({ error: 'Origin is not allowed' });
  }
  if (error.type === 'entity.too.large') {
    return res.status(413).json({ error: 'Request body is too large' });
  }
  if (error.type === 'entity.parse.failed') {
    return res.status(400).json({ error: 'Request body must be valid JSON' });
  }
  if (error.message === 'Database is unavailable') {
    return res.status(503).json({ error: 'Database is unavailable' });
  }
  if (error.message === 'PostgreSQL chat import is incomplete') {
    return res.status(503).json({ error: 'PostgreSQL chat import is incomplete' });
  }
  return res.status(error.status || 500).json({ error: 'Internal server error' });
});

export function startServer(port = PORT) {
  const server = app.listen(port, '127.0.0.1', () => {
    appLogger.info('server started', { port: server.address().port });
  });
  if (postgresStorage) {
    server.once('close', () => {
      void postgresStorage.close();
    });
  }
  if (sessionPool) {
    server.once('close', () => {
      void sessionPool.end();
    });
  }
  if (rateLimitStore) {
    server.once('close', () => {
      rateLimitStore.stopCleanup();
    });
  }
  if (postgresPool) {
    retentionPolicy.startScheduler(24 * 60 * 60 * 1000);
    server.once('close', () => {
      retentionPolicy.stopScheduler();
    });
    if (campaignWorker) {
      campaignWorker.start().catch((error) => {
        appLogger.error('Failed to start campaign worker', { error: error.message });
      });
      server.once('close', () => {
        void campaignWorker.stop();
      });
    }
  }
  return server;
}

if (process.env.NODE_ENV !== 'test' && process.env.ZOK_NO_LISTEN !== 'true') {
  startServer();
}

export { app };