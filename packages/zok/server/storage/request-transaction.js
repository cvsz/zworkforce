const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export async function withRequestTransaction(storage, request, operation) {
  if (!storage || typeof storage.withIdentityTransaction !== 'function') {
    throw new TypeError('storage with withIdentityTransaction() is required');
  }
  if (typeof operation !== 'function') {
    throw new TypeError('operation must be a function');
  }

  const identity = request?.user;
  if (
    !identity ||
    typeof identity !== 'object' ||
    typeof identity.tenantId !== 'string' ||
    !UUID_PATTERN.test(identity.tenantId)
  ) {
    throw new Error('Authenticated tenant identity is required');
  }

  return storage.withIdentityTransaction(identity, operation);
}
