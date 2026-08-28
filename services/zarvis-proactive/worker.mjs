const host = process.env.ZARVIS_PROACTIVE_HOST ?? '127.0.0.1';
const port = Number(process.env.ZARVIS_PROACTIVE_PORT ?? 8099);
const workerToken = process.env.ZARVIS_PROACTIVE_WORKER_TOKEN;
const intervalMs = Number(process.env.ZARVIS_PROACTIVE_WORKER_INTERVAL_MS ?? 60000);

if (typeof workerToken !== 'string' || Buffer.byteLength(workerToken) < 32) {
  throw new Error('ZARVIS_PROACTIVE_WORKER_TOKEN must contain at least 32 bytes');
}
if (host !== '127.0.0.1' && host !== '::1') throw new Error('Local proactive worker requires loopback host');
if (!Number.isInteger(intervalMs) || intervalMs < 250 || intervalMs > 300000) {
  throw new Error('ZARVIS_PROACTIVE_WORKER_INTERVAL_MS must be between 250 and 300000');
}

const baseUrl = `http://${host}:${port}`;
let stopping = false;

export async function runOnce() {
  const response = await fetch(`${baseUrl}/v1/internal/proactive/tick`, {
    method: 'POST',
    headers: { 'x-zarvis-proactive-worker-token': workerToken },
  });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

async function loop() {
  while (!stopping) {
    try {
      await runOnce();
    } catch (error) {
      process.stderr.write(`zarvis-proactive-worker: ${error.message}\n`);
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}

process.on('SIGINT', () => { stopping = true; });
process.on('SIGTERM', () => { stopping = true; });

if (import.meta.url === `file://${process.argv[1]}`) {
  loop().catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  });
}
