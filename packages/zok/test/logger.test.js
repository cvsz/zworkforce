import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';

async function createLogger() {
  const mod = await import('../server/observability/logger.js');
  return mod.createLogger({ requestId: 'test-request' });
}

function parseLogLines(output) {
  return output.trim().split('\n').filter(Boolean).map(line => JSON.parse(line));
}

test('logger outputs structured JSON to stdout', async () => {
  const logger = await createLogger();
  const lines = [];
  const originalWrite = process.stdout.write.bind(process.stdout);
  process.stdout.write = (chunk) => {
    lines.push(chunk);
    return originalWrite(chunk);
  };

  try {
    logger.info('hello world', { foo: 'bar' });
    const parsed = parseLogLines(lines.join(''));
    assert.equal(parsed.length, 1);
    assert.equal(parsed[0].level, 'info');
    assert.equal(parsed[0].message, 'hello world');
    assert.equal(parsed[0].foo, 'bar');
    assert.equal(parsed[0].requestId, 'test-request');
    assert.ok(parsed[0].timestamp);
  } finally {
    process.stdout.write = originalWrite;
  }
});

test('logger outputs errors to stderr', async () => {
  const logger = await createLogger();
  const lines = [];
  const originalWrite = process.stderr.write.bind(process.stderr);
  process.stderr.write = (chunk) => {
    lines.push(chunk);
    return originalWrite(chunk);
  };

  try {
    logger.error('something failed', { code: 500 });
    const parsed = parseLogLines(lines.join(''));
    assert.equal(parsed.length, 1);
    assert.equal(parsed[0].level, 'error');
    assert.equal(parsed[0].message, 'something failed');
    assert.equal(parsed[0].code, 500);
  } finally {
    process.stderr.write = originalWrite;
  }
});

test('logger redacts sensitive fields', async () => {
  const logger = await createLogger();
  const lines = [];
  const originalWrite = process.stdout.write.bind(process.stdout);
  process.stdout.write = (chunk) => {
    lines.push(chunk);
    return originalWrite(chunk);
  };

  try {
    logger.info('auth event', {
      password: 'secret123',
      token: 'abc',
      apiKey: 'xyz',
      authorization: 'Bearer tok',
      email: 'user@example.com',
      nested: { password: 'nested-secret', safe: 'keep' },
    });
    const parsed = parseLogLines(lines.join(''));
    assert.equal(parsed[0].password, '[REDACTED]');
    assert.equal(parsed[0].token, '[REDACTED]');
    assert.equal(parsed[0].apiKey, '[REDACTED]');
    assert.equal(parsed[0].authorization, '[REDACTED]');
    assert.equal(parsed[0].email, 'user@example.com');
    assert.equal(parsed[0].nested.password, '[REDACTED]');
    assert.equal(parsed[0].nested.safe, 'keep');
  } finally {
    process.stdout.write = originalWrite;
  }
});

test('logger supports child loggers with merged context', async () => {
  const logger = await createLogger();
  const child = logger.child({ tenantId: 'tenant-1' });
  const lines = [];
  const originalWrite = process.stdout.write.bind(process.stdout);
  process.stdout.write = (chunk) => {
    lines.push(chunk);
    return originalWrite(chunk);
  };

  try {
    child.warn('child event', { action: 'update' });
    const parsed = parseLogLines(lines.join(''));
    assert.equal(parsed[0].level, 'warn');
    assert.equal(parsed[0].requestId, 'test-request');
    assert.equal(parsed[0].tenantId, 'tenant-1');
    assert.equal(parsed[0].action, 'update');
  } finally {
    process.stdout.write = originalWrite;
  }
});

test('logger supports all log levels', async () => {
  const logger = await createLogger();
  const stdoutLines = [];
  const stderrLines = [];
  const originalStdoutWrite = process.stdout.write.bind(process.stdout);
  const originalStderrWrite = process.stderr.write.bind(process.stderr);
  process.stdout.write = (chunk) => {
    stdoutLines.push(chunk);
    return originalStdoutWrite(chunk);
  };
  process.stderr.write = (chunk) => {
    stderrLines.push(chunk);
    return originalStderrWrite(chunk);
  };

  try {
    logger.debug('debug msg');
    logger.info('info msg');
    logger.warn('warn msg');
    logger.error('error msg');
    const allLines = [...stdoutLines, ...stderrLines];
    const parsed = allLines.map(line => JSON.parse(line));
    assert.deepEqual(parsed.map(p => p.level), ['debug', 'info', 'warn', 'error']);
    assert.deepEqual(parsed.map(p => p.message), ['debug msg', 'info msg', 'warn msg', 'error msg']);
  } finally {
    process.stdout.write = originalStdoutWrite;
    process.stderr.write = originalStderrWrite;
  }
});

test('logger omits undefined values', async () => {
  const logger = await createLogger();
  const lines = [];
  const originalWrite = process.stdout.write.bind(process.stdout);
  process.stdout.write = (chunk) => {
    lines.push(chunk);
    return originalWrite(chunk);
  };

  try {
    logger.info('undefined test', { present: 'yes', missing: undefined });
    const parsed = parseLogLines(lines.join(''));
    assert.equal(parsed[0].present, 'yes');
    assert.ok(!('missing' in parsed[0]));
  } finally {
    process.stdout.write = originalWrite;
  }
});
