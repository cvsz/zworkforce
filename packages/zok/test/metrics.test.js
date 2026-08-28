import { test } from 'node:test';
import assert from 'node:assert/strict';

test('metrics expose counters and gauges', async () => {
  const { incrementCounter, setGauge, recordLatency, getMetrics } = await import('../server/observability/metrics.js');

  incrementCounter('messages_sent', { channel: 'whatsapp' }, 5);
  incrementCounter('messages_received', { channel: 'line' }, 3);
  incrementCounter('api_requests', { method: 'POST' }, 10);
  incrementCounter('api_errors', { method: 'GET' }, 2);
  incrementCounter('webhook_events', { provider: 'whatsapp' }, 7);
  incrementCounter('webhook_errors', { provider: 'line' }, 1);

  setGauge('active_sessions', 42);
  setGauge('active_contacts', 128);

  recordLatency(120, { method: 'GET' });
  recordLatency(250, { method: 'POST' });
  recordLatency(80, { method: 'GET' });

  const metrics = getMetrics();
  assert.equal(metrics.counters.messages_sent, 5);
  assert.equal(metrics.counters.messages_received, 3);
  assert.equal(metrics.counters.api_requests, 10);
  assert.equal(metrics.counters.api_errors, 2);
  assert.equal(metrics.counters.webhook_events, 7);
  assert.equal(metrics.counters.webhook_errors, 1);
  assert.equal(metrics.gauges.active_sessions, 42);
  assert.equal(metrics.gauges.active_contacts, 128);
  assert.deepEqual(metrics.latency.sort((a, b) => a - b), [80, 120, 250]);
});

test('metrics render Prometheus format', async () => {
  const { incrementCounter, setGauge, renderPrometheusMetrics } = await import('../server/observability/metrics.js');

  incrementCounter('messages_sent', {}, 10);
  setGauge('active_sessions', 5);

  const output = renderPrometheusMetrics();
  assert.ok(output.includes('# TYPE messages_sent counter'));
  assert.ok(output.includes('messages_sent 15'));
  assert.ok(output.includes('# TYPE active_sessions gauge'));
  assert.ok(output.includes('active_sessions 5'));
  assert.ok(output.includes('# HELP messages_sent Total number of messages sent'));
});

test('metrics reject unknown counter names', async () => {
  const { incrementCounter } = await import('../server/observability/metrics.js');
  assert.throws(() => incrementCounter('unknown_metric'), /Unknown counter metric/);
});

test('metrics reject unknown gauge names', async () => {
  const { setGauge } = await import('../server/observability/metrics.js');
  assert.throws(() => setGauge('unknown_gauge', 1), /Unknown gauge metric/);
});
