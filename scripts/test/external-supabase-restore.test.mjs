import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const script = await readFile(new URL("../backup/external-supabase-restore.sh", import.meta.url), "utf8");

test("Supabase restore uses an isolated namespace wrapper", () => {
  assert.match(script, /\{namespace: \$namespace, snapshot: \$snapshot\[0\]\}/);
  assert.match(script, /\.isolated == true/);
  assert.match(script, /BACKUP_RESTORE_NAMESPACE/);
});

test("Supabase verification binds object, namespace, and digest", () => {
  assert.match(script, /object=\$object_query&namespace=\$namespace_query/);
  assert.match(script, /\.digest == \$digest/);
  assert.match(script, /run\) run_backup_cycle/);
});
