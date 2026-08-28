import assert from "node:assert/strict";
import test from "node:test";

import { cleanupWorkspaces } from "../server/cleanup-workspaces.mjs";

test("cleanup runner emits structured result", async () => {
  const lines = [];
  const store = {
    async cleanupExpired() {
      return ["workspace-old"];
    },
  };

  const result = await cleanupWorkspaces({ store, logger: { info: (line) => lines.push(line) } });

  assert.deepEqual(result, {
    event: "workspace_cleanup",
    removed_count: 1,
    removed: ["workspace-old"],
  });
  assert.deepEqual(JSON.parse(lines[0]), result);
});
