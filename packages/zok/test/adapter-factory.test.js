import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createAdapterFactory } from '../server/channels/adapter-factory.js';

test('createAdapterFactory returns factory object', () => {
  const factory = createAdapterFactory();
  assert.ok(factory);
  assert.ok(typeof factory.getAdapter === 'function');
  assert.ok(typeof factory.initializeAdapter === 'function');
  assert.ok(typeof factory.initializeAll === 'function');
  assert.ok(typeof factory.healthChecks === 'function');
  assert.ok(Array.isArray(factory.providers));
  assert.ok(factory.providers.includes('whatsapp'));
  assert.ok(factory.providers.includes('line'));
  assert.ok(factory.providers.includes('messenger'));
  assert.ok(factory.providers.includes('tiktok'));
  assert.equal(factory.mode, 'simulated');
});

test('createAdapterFactory throws on invalid config', () => {
  assert.throws(() => createAdapterFactory(null), /Adapter configuration must be a non-null object/);
  assert.throws(() => createAdapterFactory([]), /Adapter configuration must be a non-null object/);
  assert.throws(() => createAdapterFactory({ whatsapp: 'invalid' }), /Adapter configuration for whatsapp must be an object/);
});

test('getAdapter returns cached adapter on second call', () => {
  const factory = createAdapterFactory();
  const adapter1 = factory.getAdapter('whatsapp');
  const adapter2 = factory.getAdapter('whatsapp');
  assert.strictEqual(adapter1, adapter2);
});

test('getAdapter throws on unsupported provider', () => {
  const factory = createAdapterFactory();
  assert.throws(() => factory.getAdapter('unknown'), /Unsupported provider/);
});

test('initializeAdapter returns initialized adapter', async () => {
  const factory = createAdapterFactory();
  const adapter = await factory.initializeAdapter('line');
  assert.ok(adapter);
  assert.ok(adapter.initialized);
});

test('initializeAll initializes all providers', async () => {
  const factory = createAdapterFactory();
  const results = await factory.initializeAll();
  assert.equal(Object.keys(results).length, 4);
  for (const provider of ['whatsapp', 'line', 'messenger', 'tiktok']) {
    assert.ok(results[provider]);
  }
});

test('healthChecks returns health for all providers', async () => {
  const factory = createAdapterFactory();
  const results = await factory.healthChecks();
  assert.equal(Object.keys(results).length, 4);
  for (const provider of ['whatsapp', 'line', 'messenger', 'tiktok']) {
    assert.equal(results[provider].provider, provider);
    assert.equal(results[provider].status, 'ok');
  }
});

test('createAdapterFactory accepts custom config', () => {
  const factory = createAdapterFactory({
    whatsapp: { accessToken: 'test-token', phoneNumberId: '123456' },
  });
  assert.ok(factory);
  const adapter = factory.getAdapter('whatsapp');
  assert.ok(adapter);
});
