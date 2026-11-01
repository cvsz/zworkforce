import assert from 'node:assert/strict';
import test from 'node:test';
import { parseJsonRejectingDuplicateKeys } from '../strict-json.mjs';

test('accepts unique security claims, nested objects, arrays and escaped values', () => {
  const json = '{"aud":["zeaz-financial"],"scope":"billing:write","nested":{"a":1,"b":[true,null,"a\\\"b"]}}';
  assert.deepEqual(parseJsonRejectingDuplicateKeys(json), JSON.parse(json));
});

test('rejects repeated JWT header and financial authorization claims', () => {
  for (const json of [
    '{"alg":"RS256","alg":"none","kid":"key-1"}',
    '{"tenant_id":"tenant-a","tenant_id":"tenant-b"}',
    '{"aud":"zeaz-financial","aud":"other-service"}',
    '{"scope":"billing:write","scope":"billing:read"}',
    '{"sub":"subject-a","sub":"subject-b"}',
    '{"exp":1792800600,"exp":1792800000}',
    '{"iss":"https://identity.example.test","iss":"https://other.example.test"}',
  ]) assert.throws(() => parseJsonRejectingDuplicateKeys(json), /Duplicate JSON member name/);
});

test('rejects semantically identical names written with JSON escapes', () => {
  for (const json of [
    '{"tenant_id":"a","tenant\\u005fid":"b"}',
    '{"a\\u0062":1,"ab":2}',
    '{"nested":{"role":"viewer","role":"billing_writer"}}',
    '{"array":[{"a":1,"a":2}]}',
  ]) assert.throws(() => parseJsonRejectingDuplicateKeys(json), /Duplicate JSON member name/);
});

test('permits the same member name in distinct objects', () => {
  assert.deepEqual(parseJsonRejectingDuplicateKeys('{"a":{"role":"viewer"},"b":{"role":"billing_writer"}}'), {
    a: { role: 'viewer' }, b: { role: 'billing_writer' },
  });
});

test('rejects invalid JSON and pathological nesting', () => {
  for (const json of ['{"a":}', '{"a":1,}', '[1,]', '{"a":"bad\\q"}']) {
    assert.throws(() => parseJsonRejectingDuplicateKeys(json), SyntaxError);
  }
  const deep = '['.repeat(70) + '0' + ']'.repeat(70);
  assert.throws(() => parseJsonRejectingDuplicateKeys(deep), /nesting exceeds security limit/);
});
