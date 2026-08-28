import { randomUUID } from 'node:crypto';
import { createLogger } from './logger.js';

const rootLogger = createLogger({ component: 'tracing' });

const SAMPLING_RATES = {
  always: 1.0,
  never: 0.0,
};

let sampleRate = SAMPLING_RATES.always;

export function configureTracing(options = {}) {
  if (options.sampleRate !== undefined) {
    sampleRate = Number(options.sampleRate);
  }
  if (options.sampleRatePreset !== undefined && SAMPLING_RATES[options.sampleRatePreset] !== undefined) {
    sampleRate = SAMPLING_RATES[options.sampleRatePreset];
  }
  rootLogger.info('tracing configured', { sampleRate });
}

function shouldSample() {
  return Math.random() < sampleRate;
}

export function createSpan(operationName, parentContext = {}) {
  const sampled = shouldSample();
  const span = {
    traceId: parentContext.traceId || randomUUID(),
    spanId: randomUUID(),
    parentSpanId: parentContext.spanId || null,
    operationName,
    startTime: Date.now(),
    sampled,
  };
  return span;
}

export function endSpan(span, attributes = {}) {
  if (!span.sampled) return;
  span.endTime = Date.now();
  span.duration = span.endTime - span.startTime;
  span.attributes = attributes;

  const logger = rootLogger.child({
    traceId: span.traceId,
    spanId: span.spanId,
    parentSpanId: span.parentSpanId,
    duration: span.duration,
    operation: span.operationName,
  });

  if (span.duration > 1000) {
    logger.warn('slow span', { duration: span.duration, ...attributes });
  } else {
    logger.debug('span ended', { duration: span.duration, ...attributes });
  }
}

export function createTraceMiddleware() {
  return (req, res, next) => {
    const span = createSpan(`http ${req.method} ${req.path}`);
    req.span = span;
    req.traceId = span.traceId;
    res.setHeader('X-Trace-Id', span.traceId);

    res.on('finish', () => {
      endSpan(span, {
        http_method: req.method,
        http_route: req.path,
        http_status_code: res.statusCode,
        request_id: req.requestId || null,
        tenant_id: req.user?.tenantId || null,
        user_id: req.user?.id || null,
      });
    });

    next();
  };
}
