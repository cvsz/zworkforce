const rootLogger = await import('./logger.js').then(m => m.rootLogger);

const COUNTERS = {
  messages_sent: 0,
  messages_received: 0,
  messages_failed: 0,
  api_requests: 0,
  api_errors: 0,
  webhook_events: 0,
  webhook_errors: 0,
};

const GAUGES = {
  active_sessions: 0,
  active_contacts: 0,
};

const LATENCY_SAMPLES = [];
const MAX_LATENCY_SAMPLES = 1000;
const LATENCY_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10];

let postgresPool = null;

export function configureMetrics(pool) {
  postgresPool = pool;
}

function ensureLabels(labels = {}) {
  return Object.entries(labels)
    .filter(([, value]) => value !== undefined && value !== null)
    .reduce((acc, [key, value]) => ({ ...acc, [key]: String(value) }), {});
}

async function persistMetric(metricName, value, labels = {}) {
  if (!postgresPool) return;
  try {
    await postgresPool.query(
      `INSERT INTO metrics (metric_name, metric_value, labels) VALUES ($1, $2, $3::jsonb)`,
      [metricName, value, JSON.stringify(ensureLabels(labels))],
    );
  } catch (error) {
    // Persistence failure must not break the request path.
    rootLogger.warn('metrics persistence failed', { metricName, error: error.message });
  }
}

export function incrementCounter(metricName, labels = {}, amount = 1) {
  if (!Object.prototype.hasOwnProperty.call(COUNTERS, metricName)) {
    throw new Error(`Unknown counter metric: ${metricName}`);
  }
  COUNTERS[metricName] += amount;
  void persistMetric(metricName, COUNTERS[metricName], labels);
}

export function setGauge(metricName, value, labels = {}) {
  if (!Object.prototype.hasOwnProperty.call(GAUGES, metricName)) {
    throw new Error(`Unknown gauge metric: ${metricName}`);
  }
  GAUGES[metricName] = value;
  void persistMetric(metricName, value, labels);
}

export function recordLatency(durationMs, labels = {}) {
  LATENCY_SAMPLES.push(durationMs);
  if (LATENCY_SAMPLES.length > MAX_LATENCY_SAMPLES) {
    LATENCY_SAMPLES.shift();
  }
  void persistMetric('api_latency', durationMs, labels);
}

export function getMetrics() {
  return {
    counters: { ...COUNTERS },
    gauges: { ...GAUGES },
    latency: [...LATENCY_SAMPLES],
  };
}

function percentile(sorted, p) {
  if (sorted.length === 0) return 0;
  const pos = (sorted.length - 1) * p;
  const base = Math.floor(pos);
  const rest = pos - base;
  if (sorted[base + 1] !== undefined) {
    return sorted[base] + rest * (sorted[base + 1] - sorted[base]);
  }
  return sorted[base];
}

export function renderPrometheusMetrics() {
  const metrics = getMetrics();
  const lines = [];

  lines.push('# HELP messages_sent Total number of messages sent');
  lines.push('# TYPE messages_sent counter');
  lines.push(`messages_sent ${metrics.counters.messages_sent}`);

  lines.push('# HELP messages_received Total number of messages received');
  lines.push('# TYPE messages_received counter');
  lines.push(`messages_received ${metrics.counters.messages_received}`);

  lines.push('# HELP messages_failed Total number of failed messages');
  lines.push('# TYPE messages_failed counter');
  lines.push(`messages_failed ${metrics.counters.messages_failed}`);

  lines.push('# HELP api_requests Total number of API requests');
  lines.push('# TYPE api_requests counter');
  lines.push(`api_requests ${metrics.counters.api_requests}`);

  lines.push('# HELP api_errors Total number of API errors');
  lines.push('# TYPE api_errors counter');
  lines.push(`api_errors ${metrics.counters.api_errors}`);

  lines.push('# HELP active_sessions Current number of active sessions');
  lines.push('# TYPE active_sessions gauge');
  lines.push(`active_sessions ${metrics.gauges.active_sessions}`);

  lines.push('# HELP active_contacts Current number of active contacts');
  lines.push('# TYPE active_contacts gauge');
  lines.push(`active_contacts ${metrics.gauges.active_contacts}`);

  lines.push('# HELP webhook_events Total number of webhook events');
  lines.push('# TYPE webhook_events counter');
  lines.push(`webhook_events ${metrics.counters.webhook_events}`);

  lines.push('# HELP webhook_errors Total number of webhook errors');
  lines.push('# TYPE webhook_errors counter');
  lines.push(`webhook_errors ${metrics.counters.webhook_errors}`);

  const sortedLatencies = metrics.latency.sort((a, b) => a - b);
  lines.push('# HELP api_latency API request latency in seconds');
  lines.push('# TYPE api_latency histogram');
  for (const bucket of LATENCY_BUCKETS) {
    const count = sortedLatencies.filter(v => v <= bucket * 1000).length;
    lines.push(`api_latency_bucket{le="${bucket}"} ${count}`);
  }
  lines.push(`api_latency_bucket{le="+Inf"} ${sortedLatencies.length}`);
  lines.push(`api_latency_sum ${sortedLatencies.reduce((sum, v) => sum + v, 0) / 1000}`);
  lines.push(`api_latency_count ${sortedLatencies.length}`);

  return lines.join('\n') + '\n';
}
