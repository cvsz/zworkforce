import { createRealtimeClient } from "./core/realtime.js";
import { createPackageRegistry, DEFAULT_DEFINITIONS } from "./core/registry.js";
import { mountRealtimePackage } from "./packages/realtime/index.js";

export function createDashboardRealtime(options = {}) {
  const client = options.client || createRealtimeClient({
    endpoint: options.endpoint || "/api/v1/dashboard/events",
    getSession: options.getSession,
    fetchImpl: options.fetchImpl,
    sleep: options.sleep,
    random: options.random,
  });
  const registry = createPackageRegistry(
    options.definitions || DEFAULT_DEFINITIONS,
    (packageId, event) => options.onInvalidate?.(packageId, event),
  );
  const packageMount = mountRealtimePackage({ root: options.root || globalThis.document, client });
  const unsubscribeEvents = client.subscribeEvents?.((event) => {
    const packageIds = registry.dispatch(event);
    options.onEvent?.(event, packageIds);
  });
  const unsubscribeStatus = client.subscribeStatus?.((state) => options.onStatus?.(state));

  return {
    start: () => client.start(),
    stop: () => client.stop(),
    restart: () => client.restart(),
    getState: () => client.getState(),
    getCursor: () => client.getCursor(),
    markStale: () => client.markStale?.(),
    destroy() {
      unsubscribeEvents?.();
      unsubscribeStatus?.();
      packageMount.destroy();
      registry.destroy();
      client.stop();
    },
  };
}

export { createRealtimeClient, createPackageRegistry, mountRealtimePackage };
