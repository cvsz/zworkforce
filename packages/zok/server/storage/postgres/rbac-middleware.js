import { createRbacEvaluator } from './rbac-evaluator.js';

export function createRbacMiddleware(storage) {
  if (!storage || typeof storage.withTenantTransaction !== 'function') {
    throw new TypeError('PostgreSQL storage is required');
  }

  const enforced = (process.env.ZOK_RBAC_ENFORCEMENT || 'disabled').trim().toLowerCase() === 'enabled';

  if (!enforced) {
    return (req, res, next) => next();
  }

  return async function rbacMiddleware(req, res, next) {
    if (!req.user) {
      return res.status(403).json({ error: 'Permission denied' });
    }

    const requiredPermission = req.rbacRequired;
    if (!requiredPermission) {
      return next();
    }

    try {
      await storage.withTenantTransaction(req.user.tenantId, async (tx) => {
        const evaluator = createRbacEvaluator(tx);
        const cache = typeof req.rbacCache === 'object' && req.rbacCache && req.rbacCache.tenantId === req.user.tenantId
          ? req.rbacCache
          : undefined;

        const granted = await evaluator.evaluate(req.user.id, requiredPermission, cache);
        if (!granted) {
          throw new Error('Forbidden');
        }
      });
      return next();
    } catch (error) {
      if (error.message === 'Forbidden') {
        return res.status(403).json({ error: 'Permission denied' });
      }
      console.error(`[${req.method} ${req.originalUrl}] RBAC error:`, error.message);
      return res.status(500).json({ error: 'Internal server error' });
    }
  };
}

export function requirePermission(permission) {
  if (typeof permission !== 'string' || !permission.trim()) {
    throw new TypeError('Permission string is required');
  }
  return (req, res, next) => {
    req.rbacRequired = permission.trim();
    return next();
  };
}
