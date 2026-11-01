/**
 * Graceful shutdown coordinator for Zeto.
 *
 * On SIGTERM or SIGINT:
 * 1. Stop accepting new HTTP requests (server.close).
 * 2. Drain in-flight requests up to GRACEFUL_SHUTDOWN_TIMEOUT_MS (default 10s).
 * 3. Release the database pool.
 * 4. Exit 0 on clean shutdown, 1 on timeout.
 *
 * Usage:
 *   const { registerShutdown } = require('./shutdown');
 *   registerShutdown({ server, pool, log });
 */

"use strict";

const DEFAULT_TIMEOUT_MS = parseInt(
  process.env.GRACEFUL_SHUTDOWN_TIMEOUT_MS ?? "10000",
  10,
);

/**
 * @param {object} opts
 * @param {import('http').Server} opts.server - HTTP server instance
 * @param {{ end: () => Promise<void> }} [opts.pool] - DB pool with .end()
 * @param {(msg: string) => void} [opts.log] - Logger function (defaults to console.error)
 * @param {number} [opts.timeoutMs] - Drain timeout in ms
 * @param {NodeJS.Process} [opts.proc] - Process reference (for testing)
 */
function registerShutdown({
  server,
  pool = null,
  log = console.error,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  proc = process,
}) {
  let shutting_down = false;

  async function shutdown(signal) {
    if (shutting_down) return;
    shutting_down = true;
    log(`[shutdown] ${signal} received — draining (timeout=${timeoutMs}ms)`);

    const timer = setTimeout(() => {
      log("[shutdown] drain timeout exceeded — forcing exit 1");
      proc.exit(1);
    }, timeoutMs);
    timer.unref();

    await new Promise((resolve) => server.close(resolve));
    log("[shutdown] HTTP server closed");

    if (pool) {
      try {
        await pool.end();
        log("[shutdown] DB pool released");
      } catch (err) {
        log(`[shutdown] DB pool release error: ${err.message}`);
      }
    }

    clearTimeout(timer);
    log("[shutdown] clean exit 0");
    proc.exit(0);
  }

  proc.once("SIGTERM", () => shutdown("SIGTERM"));
  proc.once("SIGINT", () => shutdown("SIGINT"));
}

module.exports = { registerShutdown };
