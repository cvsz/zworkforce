const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function createRbacEvaluator(tx) {
  if (
    !tx ||
    typeof tx.query !== 'function' ||
    typeof tx.tenantId !== 'string' ||
    !UUID_PATTERN.test(tx.tenantId)
  ) {
    throw new TypeError('Tenant transaction context is required');
  }

  async function loadUserRoles(userId) {
    if (typeof userId !== 'string' || !UUID_PATTERN.test(userId)) {
      throw new TypeError('Valid user id is required');
    }

    const result = await tx.query(`
      SELECT r.permissions
      FROM user_roles ur
      JOIN roles r ON r.id = ur.role_id AND r.tenant_id = ur.tenant_id
      WHERE ur.tenant_id = $1 AND ur.user_id = $2
    `, [tx.tenantId, userId]);
    return result.rows.map(row => row.permissions || {});
  }

  function matchesPermission(permissions, requiredPermission) {
    if (!permissions || typeof permissions !== 'object' || Array.isArray(permissions)) {
      return false;
    }

    const requiredParts = String(requiredPermission).split(':');
    if (requiredParts.length !== 2) return false;

    const [resource, action] = requiredParts;
    if (!resource || !action) return false;

    const pattern = `${resource}:*`;
    if (permissions[pattern] === true) return true;

    const exact = `${resource}:${action}`;
    if (permissions[exact] === true) return true;

    const all = 'admin:*';
    if (permissions[all] === true) return true;

    return false;
  }

  async function evaluate(userId, requiredPermission, cache) {
    if (typeof requiredPermission !== 'string' || !requiredPermission.trim()) {
      return false;
    }

    if (cache && cache.tenantId === tx.tenantId) {
      const cacheKey = `${userId}:${requiredPermission}`;
      const cached = cache.entries.get(cacheKey);
      if (cached !== undefined) return cached;
    }

    const roles = await loadUserRoles(userId);
    const granted = roles.some(permissions => matchesPermission(permissions, requiredPermission));

    if (cache && cache.tenantId === tx.tenantId) {
      const cacheKey = `${userId}:${requiredPermission}`;
      cache.entries.set(cacheKey, granted);
    }

    return granted;
  }

  return Object.freeze({ loadUserRoles, evaluate });
}

export function createRbacCache(tenantId) {
  if (typeof tenantId !== 'string' || !tenantId.trim()) {
    throw new TypeError('tenantId is required for RBAC cache');
  }
  const entries = new Map();
  return Object.freeze({
    tenantId,
    entries,
  });
}
