import { execFileSync } from 'node:child_process';

const envFile = process.env.ZARVIS_LOCAL_ENV_FILE ?? '.env.zarvis.local';
const composeFile = process.env.ZARVIS_LOCAL_COMPOSE_FILE ?? 'compose.zarvis-local.yml';
const actionPort = Number(process.env.ZARVIS_ACTION_PORT ?? 8098);
const proactivePort = Number(process.env.ZARVIS_PROACTIVE_PORT ?? 8099);
const services = [
  { name: 'zarvis-action-gateway', minimumMemory: 256 * 1024 * 1024 },
  { name: 'zarvis-action-worker', minimumMemory: 128 * 1024 * 1024 },
  { name: 'zarvis-proactive', minimumMemory: 256 * 1024 * 1024 },
  { name: 'zarvis-proactive-worker', minimumMemory: 128 * 1024 * 1024 },
];

function run(command, args) {
  return execFileSync(command, args, { encoding: 'utf8' }).trim();
}

const evidence = [];
for (const service of services) {
  const containerId = run('docker', ['compose', '--env-file', envFile, '-f', composeFile, 'ps', '-q', service.name]);
  if (!containerId) throw new Error(`${service.name} container is not running`);
  const inspected = JSON.parse(run('docker', ['inspect', containerId]))[0];
  const host = inspected.HostConfig;
  const securityOptions = Array.isArray(host.SecurityOpt) ? host.SecurityOpt : [];
  const checks = {
    network_mode_host: host.NetworkMode === 'host',
    readonly_rootfs: host.ReadonlyRootfs === true,
    pids_limit: Number(host.PidsLimit) === 128,
    memory_limit: Number(host.Memory) >= service.minimumMemory,
    cpu_limit: Number(host.NanoCpus) > 0,
    cap_drop_all: Array.isArray(host.CapDrop) && host.CapDrop.includes('ALL'),
    no_new_privileges: securityOptions.some((value) => value === 'no-new-privileges' || value === 'no-new-privileges:true'),
  };
  if (Object.values(checks).some((passed) => !passed)) {
    throw new Error(`${service.name} hardening failed: ${JSON.stringify({ checks, securityOptions })}`);
  }
  evidence.push({
    service: service.name,
    image: inspected.Config.Image,
    memory_bytes: Number(host.Memory),
    nano_cpus: Number(host.NanoCpus),
    pids_limit: Number(host.PidsLimit),
    checks,
  });
}

const sockets = [];
for (const port of [actionPort, proactivePort]) {
  const output = run('ss', ['-ltnH', `sport = :${port}`]);
  const loopback = new RegExp(`127\\.0\\.0\\.1:${port}|\\[::1\\]:${port}`).test(output);
  const wildcard = new RegExp(`0\\.0\\.0\\.0:${port}|\\[::\\]:${port}`).test(output);
  if (!loopback || wildcard) throw new Error(`Port ${port} is not exclusively loopback-bound: ${output}`);
  sockets.push({ port, loopback, wildcard, output });
}

process.stdout.write(`${JSON.stringify({
  schema_version: 'zarvis.local-container-evidence.v1',
  local_only: true,
  services: evidence,
  sockets,
})}\n`);
