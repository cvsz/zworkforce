import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const serverSource = await readFile(new URL('../server.js', import.meta.url), 'utf8');

test('Express runtime delegates persistence through the JSON storage adapter boundary', () => {
  assert.match(
    serverSource,
    /import\s+\{\s*createJsonStorage\s*\}\s+from\s+['"]\.\/server\/storage\/json-storage\.js['"]/,
  );
  assert.match(serverSource, /const\s+storage\s*=\s*createJsonStorage\s*\(/);
  assert.match(serverSource, /async function readDB\(\)\s*\{\s*return storage\.read\(\);\s*\}/s);
  assert.match(serverSource, /function updateDB\(mutator\)\s*\{\s*return storage\.update\(mutator\);\s*\}/s);

  assert.doesNotMatch(serverSource, /import\s+fs\s+from\s+['"]fs\/promises['"]/);
  assert.doesNotMatch(serverSource, /async function atomicWrite\(/);
  assert.doesNotMatch(serverSource, /async function ensureDB\(/);
  assert.doesNotMatch(serverSource, /let\s+mutationQueue\s*=/);
});
