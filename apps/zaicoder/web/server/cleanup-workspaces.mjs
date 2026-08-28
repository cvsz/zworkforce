import { fileURLToPath } from "node:url";

import { createWorkspaceStoreFromEnv } from "./workspace-store.mjs";

export async function cleanupWorkspaces({ store = createWorkspaceStoreFromEnv(), logger = console } = {}) {
  const removed = await store.cleanupExpired();
  const result = {
    event: "workspace_cleanup",
    removed_count: removed.length,
    removed,
  };
  logger.info(JSON.stringify(result));
  return result;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  cleanupWorkspaces().catch((error) => {
    console.error(JSON.stringify({ event: "workspace_cleanup_failed", error: error?.message || "Unexpected error" }));
    process.exitCode = 1;
  });
}
