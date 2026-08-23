/**
 * Cloudflare Worker entry for the Vinext App Router build.
 * Keep the entry small; Vinext owns route rendering and asset delegation.
 */
import handler from "vinext/server/app-router-entry";
import { runWithExecutionContext } from "vinext/shims/request-context";
import type { ExecutionContextLike } from "vinext/shims/request-context";

type WorkerEnv = {
  ASSETS?: {
    fetch(request: Request): Promise<Response> | Response;
  };
};

const worker = {
  fetch(request: Request, env: WorkerEnv, ctx: ExecutionContextLike) {
    return runWithExecutionContext(ctx, () => handler.fetch(request, env, ctx));
  },
};

export default worker;
