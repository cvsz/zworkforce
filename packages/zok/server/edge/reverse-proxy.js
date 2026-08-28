const NODE_ENV = process.env.NODE_ENV || 'development';
const IS_PRODUCTION = NODE_ENV === 'production';

const DEFAULT_TRUST_PROXY = IS_PRODUCTION
  ? ['loopback', 'linklocal', 'uniquelocal']
  : ['loopback', 'linklocal', 'uniquelocal'];

const ALLOWED_PROXY_NETWORKS = new Set(
  (process.env.ZOK_TRUSTED_PROXIES || '')
    .split(',')
    .map(network => network.trim())
    .filter(Boolean),
);

function isTrustedProxy(req) {
  if (ALLOWED_PROXY_NETWORKS.size === 0) {
    return true;
  }

  const clientIp = req.ip || req.connection?.remoteAddress || '';
  if (!clientIp) return false;

  for (const network of ALLOWED_PROXY_NETWORKS) {
    if (clientIp === network || clientIp.endsWith(`.${network}`)) {
      return true;
    }
  }

  return false;
}

function validateForwardedHeaders(req) {
  const errors = [];

  const forwardedProto = req.get('x-forwarded-proto');
  if (forwardedProto && !['http', 'https'].includes(forwardedProto)) {
    errors.push('x-forwarded-proto must be http or https');
  }

  const forwardedHost = req.get('x-forwarded-host');
  if (forwardedHost && !/^[a-zA-Z0-9.-]+(:[0-9]+)?$/.test(forwardedHost)) {
    errors.push('x-forwarded-host has an invalid format');
  }

  const forwardedPort = req.get('x-forwarded-port');
  if (forwardedPort && !/^[0-9]+$/.test(forwardedPort)) {
    errors.push('x-forwarded-port must be numeric');
  }

  const forwardedFor = req.get('x-forwarded-for');
  if (forwardedFor) {
    const ips = forwardedFor.split(',').map(ip => ip.trim());
    for (const ip of ips) {
      if (!/^[0-9a-fA-F:.]+$/.test(ip)) {
        errors.push('x-forwarded-for contains invalid IP');
        break;
      }
    }
  }

  return errors;
}

export function createReverseProxyConfig(options = {}) {
  const trustProxy = options.trustProxy || DEFAULT_TRUST_PROXY;

  function apply(app) {
    app.set('trust proxy', trustProxy);
  }

  function middleware(req, res, next) {
    const validationErrors = validateForwardedHeaders(req);
    if (validationErrors.length > 0) {
      return res.status(400).json({ error: 'Invalid proxy headers', details: validationErrors });
    }

    if (!isTrustedProxy(req)) {
      return res.status(400).json({ error: 'Untrusted proxy' });
    }

    const forwardedProto = req.get('x-forwarded-proto');
    if (forwardedProto === 'https' && !req.secure) {
      req.secure = true;
    }

    const originalSocket = req.socket;
    if (originalSocket && !req.secure && forwardedProto === 'https') {
      Object.defineProperty(req, 'connection', {
        value: { ...originalSocket, encrypted: true },
        writable: true,
      });
    }

    if (req.get('upgrade') === 'websocket') {
      res.setHeader('Connection', 'upgrade');
      res.setHeader('Upgrade', 'websocket');
    }

    next();
  }

  return Object.freeze({
    apply,
    middleware,
    isTrustedProxy,
    validateForwardedHeaders,
  });
}
