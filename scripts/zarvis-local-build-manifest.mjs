import { createHash } from 'node:crypto';
import { readFile, stat } from 'node:fs/promises';
import { basename, join, resolve } from 'node:path';

const evidenceDir = resolve(process.argv[2] ?? 'zarvis-local-release-evidence');
const required = [
  'zarvis-local-container-evidence.json',
  'zarvis-local-release-acceptance.json',
  'zarvis-local-red-team.json',
  'zarvis-local-restart-drill.json',
  'zarvis-local-restore-verification.json',
  'zarvis-local-rotation-verification.json',
  'zarvis-local-backup-manifest.json',
];

function sha256(value) {
  return createHash('sha256').update(value).digest('hex');
}

const documents = new Map();
const files = [];
for (const name of required) {
  const path = join(evidenceDir, name);
  const content = await readFile(path);
  const metadata = await stat(path);
  const parsed = JSON.parse(content.toString('utf8'));
  documents.set(name, parsed);
  files.push({ file: basename(path), bytes: metadata.size, sha256: sha256(content) });
}

const acceptance = documents.get('zarvis-local-release-acceptance.json');
const redTeam = documents.get('zarvis-local-red-team.json');
const restart = documents.get('zarvis-local-restart-drill.json');
const restored = documents.get('zarvis-local-restore-verification.json');
const rotation = documents.get('zarvis-local-rotation-verification.json');
const container = documents.get('zarvis-local-container-evidence.json');
const backup = documents.get('zarvis-local-backup-manifest.json');

const assertions = {
  automated_acceptance_passed: acceptance.automated_acceptance === 'passed',
  red_team_passed: redTeam.all_passed === true && redTeam.secret_leaks_detected === 0 && redTeam.autonomous_mutations_detected === 0,
  restart_recovery_passed: restart.durable_state_preserved === true && restart.workers_resumed === true,
  restore_passed: restored.restored === true && restored.handoff_executed === false,
  rotation_passed: rotation.rotated === true && rotation.old_credentials_rejected === true && rotation.new_credentials_accepted === true,
  container_hardening_passed: container.local_only === true && container.services.every((service) => Object.values(service.checks).every(Boolean)) && container.sockets.every((socket) => socket.loopback === true && socket.wildcard === false),
  backup_secret_free: backup.contains_secrets === false && backup.archives.length === 2,
  proactive_non_mutating: acceptance.proactive.handoff_requires_owner_approval === true && acceptance.proactive.handoff_executed === false,
  local_slo_passed: Object.values(acceptance.slo).filter((value) => value && typeof value === 'object').every((sample) => sample.errors === 0 && sample.p95_ms <= acceptance.slo.threshold_p95_ms),
};
if (Object.values(assertions).some((passed) => !passed)) {
  throw new Error(`Release evidence assertion failed: ${JSON.stringify(assertions)}`);
}

const manifest = {
  schema_version: 'zarvis.local-release-manifest.v1',
  source_sha: process.env.GITHUB_SHA ?? 'local-uncommitted',
  generated_at: new Date().toISOString(),
  owner_github_id: '4076926',
  owner_user_id: 'github:4076926',
  tenant_id: 'owner-4076926',
  deployment_target: 'single-owner Ubuntu/Linux local host or VM',
  local_only: true,
  automated_release_evidence: 'passed',
  manual_owner_machine_acceptance: 'pending_actual_target_host',
  contains_secrets: false,
  assertions,
  evidence: files.sort((left, right) => left.file.localeCompare(right.file)),
  phase_evidence: [
    { phase: 1, pull_request: 149, capability: 'owner-only voice/text GitHub read-only command' },
    { phase: 2, pull_request: 150, capability: 'voice bridge and durable sessions' },
    { phase: 3, pull_request: 157, capability: 'durable tasks and exact-plan approval' },
    { phase: 4, pull_request: 158, capability: 'encrypted owner memory and privacy' },
    { phase: 5, pull_request: 159, capability: 'consent-based perception' },
    { phase: 6, pull_request: 160, capability: 'reversible local action gateway' },
    { phase: 7, pull_request: 161, capability: 'bounded local proactive scheduler' },
  ],
  prohibited_capabilities: [
    'unapproved mutation',
    'autonomous proactive mutation',
    'public or LAN ingress',
    'shared accounts or owner reassignment',
    'arbitrary shell or filesystem execution',
    'financial, weapon, targeting, or offensive-security actions',
  ],
};

process.stdout.write(`${JSON.stringify(manifest, null, 2)}\n`);
