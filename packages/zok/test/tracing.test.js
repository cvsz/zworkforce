import { test } from 'node:test';
import assert from 'node:assert/strict';

test('tracing creates spans with trace and span ids', async () => {
  const { createSpan, endSpan } = await import('../server/observability/tracing.js');

  const span = createSpan('test-operation');
  assert.ok(span.traceId);
  assert.ok(span.spanId);
  assert.equal(span.operationName, 'test-operation');
  assert.equal(span.parentSpanId, null);
  assert.ok(typeof span.startTime === 'number');
});

test('tracing propagates parent context', async () => {
  const { createSpan, endSpan } = await import('../server/observability/tracing.js');

  const parent = createSpan('parent');
  const child = createSpan('child', { traceId: parent.traceId, spanId: parent.spanId });

  assert.equal(child.traceId, parent.traceId);
  assert.equal(child.parentSpanId, parent.spanId);
});

test('tracing createTraceMiddleware sets trace id on request', async () => {
  const { createTraceMiddleware } = await import('../server/observability/tracing.js');
  const middleware = createTraceMiddleware();

  let capturedTraceId = null;
  let capturedSpan = null;

  const req = {
    method: 'GET',
    path: '/api/test',
  };
  const res = {
    setHeader() {},
    on() {},
  };
  const next = () => {
    capturedTraceId = req.traceId;
    capturedSpan = req.span;
  };

  middleware(req, res, next);
  assert.ok(capturedTraceId);
  assert.ok(capturedSpan);
  assert.equal(capturedTraceId, capturedSpan.traceId);
});

test('tracing createTraceMiddleware sets X-Trace-Id response header', async () => {
  const { createTraceMiddleware } = await import('../server/observability/tracing.js');
  const middleware = createTraceMiddleware();

  const headers = [];
  const req = { method: 'GET', path: '/api/test' };
  const res = {
    setHeader(name, value) { headers.push({ name, value }); },
    on() {},
  };
  const next = () => {};

  middleware(req, res, next);
  const traceHeader = headers.find(h => h.name === 'X-Trace-Id');
  assert.ok(traceHeader);
  assert.equal(traceHeader.value, req.traceId);
});

test('tracing endSpan records duration and logs attributes', async () => {
  const { createSpan, endSpan } = await import('../server/observability/tracing.js');

  const span = createSpan('test');
  await new Promise(r => setTimeout(r, 10));
  endSpan(span, { http_status_code: 200 });

  assert.ok(span.endTime);
  assert.ok(span.duration >= 10);
  assert.equal(span.attributes.http_status_code, 200);
});
