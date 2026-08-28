import { randomUUID } from 'node:crypto';
import { createAuditService } from './audit-service.js';

export function createAuditMiddleware(postgresPool) {
  const enforced =
    (process.env.ZOK_AUDIT_ENFORCEMENT || 'disabled').trim().toLowerCase() === 'enabled';

  if (!enforced || !postgresPool) {
    return (req, res, next) => next();
  }

  const auditService = createAuditService(postgresPool);

  return async function auditMiddleware(req, res, next) {
    req.requestId = req.headers['x-request-id'] || randomUUID();

    if (!['POST', 'PUT', 'DELETE'].includes(req.method)) {
      return next();
    }

    if (req.path.startsWith('/auth/')) {
      return next();
    }

    const actor = req.user || {};
    const tenantId = actor.tenantId;

    if (!tenantId) {
      return next();
    }

    const pathParts = req.path.split('/');
    const resourceType = pathParts[1] || 'unknown';
    const resourceId = req.params.id || null;

    const event = {
      tenant_id: tenantId,
      actor_user_id: actor.id || null,
      action: req.method.toLowerCase(),
      resource_type: resourceType,
      resource_id: resourceId,
      request_id: req.requestId,
      occurred_at: new Date().toISOString(),
      metadata: {
        method: req.method,
        path: req.path,
        url: req.originalUrl,
        userAgent: req.get('user-agent'),
        ip: req.ip || req.socket?.remoteAddress || null,
      },
    };

    try {
      await auditService.emit(event);
    } catch {
      console.error('[audit] middleware emission failed');
    }

    return next();
  };
}
