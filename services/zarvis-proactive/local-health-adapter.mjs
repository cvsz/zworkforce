const LOOPBACK_HOSTS = new Set(['127.0.0.1', '::1', '[::1]']);
const TARGET_NAME_PATTERN = /^[a-z][a-z0-9-]{0,63}$/;

export function validateHealthUrl(value) {
  const url = new URL(value);
  if (url.protocol !== 'http:' || !LOOPBACK_HOSTS.has(url.hostname) || url.pathname !== '/healthz') {
    throw new Error('Local health URL must be an HTTP literal-loopback /healthz endpoint');
  }
  if (url.username || url.password || url.search || url.hash) {
    throw new Error('Local health URL cannot contain credentials, query, or fragment');
  }
  return url.toString();
}

export function createLocalHealthAdapter({
  fetchImpl = fetch,
  targets = {
    'zarvis-action-gateway': process.env.ZARVIS_ACTION_HEALTH_URL ?? 'http://127.0.0.1:8098/healthz',
  },
  timeoutMs = Number(process.env.ZARVIS_PROACTIVE_CHECK_TIMEOUT_MS ?? 3000),
} = {}) {
  const entries = Object.entries(targets);
  if (entries.length < 1 || entries.length > 8) throw new Error('Local health target registry must contain 1 to 8 entries');
  const registry = Object.fromEntries(entries.map(([name, url]) => {
    if (!TARGET_NAME_PATTERN.test(name)) throw new Error('Local health target name is invalid');
    return [name, validateHealthUrl(url)];
  }));
  if (!Number.isInteger(timeoutMs) || timeoutMs < 250 || timeoutMs > 15000) {
    throw new Error('ZARVIS_PROACTIVE_CHECK_TIMEOUT_MS must be between 250 and 15000');
  }

  return {
    allowedTargets: Object.freeze(Object.keys(registry)),
    async evaluate(subscription, checkedAt) {
      const endpoint = registry[subscription.target];
      if (!endpoint) throw new Error('Target is not allowlisted');

      let response;
      try {
        response = await fetchImpl(endpoint, {
          method: 'GET',
          redirect: 'error',
          signal: AbortSignal.timeout(timeoutMs),
          headers: { accept: 'application/json' },
        });
      } catch {
        return {
          signal_key: `health:${subscription.target}`,
          status: 'unhealthy',
          severity: 'high',
          confidence: 1,
          summary: `${subscription.target} health check failed`,
          source_url: endpoint,
          evidence: { reachable: false, http_status: null, checked_at: checkedAt },
          proposed_action: {
            capability: 'sandbox.preference.set',
            key: 'assistant.proactive_attention',
            value: `unhealthy:${subscription.target}`,
          },
        };
      }

      let body = {};
      try {
        body = await response.json();
      } catch {
        body = {};
      }
      const healthy = response.ok && body?.status === 'ok';
      return {
        signal_key: `health:${subscription.target}`,
        status: healthy ? 'healthy' : 'unhealthy',
        severity: healthy ? 'info' : 'high',
        confidence: 1,
        summary: healthy
          ? `${subscription.target} is healthy`
          : `${subscription.target} returned an unhealthy response`,
        source_url: endpoint,
        evidence: {
          reachable: true,
          http_status: response.status,
          checked_at: checkedAt,
          local_only: body?.local_only === true,
        },
        proposed_action: healthy ? null : {
          capability: 'sandbox.preference.set',
          key: 'assistant.proactive_attention',
          value: `unhealthy:${subscription.target}`,
        },
      };
    },
  };
}
