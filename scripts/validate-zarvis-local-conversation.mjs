#!/usr/bin/env node

import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DEFAULT_CONTRACT = path.join(ROOT, 'ops/zarvis-owner-domain/local-conversation-contract.json');
const DEFAULT_COMPOSE = path.join(ROOT, 'compose.zarvis-owner-voice.yml');
const DEFAULT_NGINX = path.join(ROOT, 'ops/zarvis-owner-domain/nginx.conf');

const PORT_ENV = new Map([
  ['ollama', 'OLLAMA_PORT'],
  ['zarvis-orchestrator', 'ZARVIS_ORCHESTRATOR_PORT'],
  ['voice-gateway', 'VOICE_GATEWAY_PORT'],
  ['zarvis-owner-voice-edge', 'ZARVIS_OWNER_VOICE_EDGE_PORT'],
]);

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function readText(file) {
  return fs.readFileSync(file, 'utf8');
}

function serviceBlock(compose, serviceId) {
  const lines = compose.split(/\r?\n/);
  const start = lines.findIndex((line) => line === `  ${serviceId}:`);
  if (start < 0) return '';

  let end = lines.length;
  for (let index = start + 1; index < lines.length; index += 1) {
    if (/^  [A-Za-z0-9][A-Za-z0-9_-]*:$/.test(lines[index])) {
      end = index;
      break;
    }
  }
  return lines.slice(start, end).join('\n');
}

function assert(condition, message, errors) {
  if (!condition) errors.push(message);
}

export function validateStaticContract({
  contractPath = DEFAULT_CONTRACT,
  composePath = DEFAULT_COMPOSE,
  nginxPath = DEFAULT_NGINX,
} = {}) {
  const errors = [];
  const contract = readJson(contractPath);
  const compose = readText(composePath);
  const nginx = readText(nginxPath);

  assert(contract.schemaVersion === 1, 'unsupported local conversation contract schema', errors);
  assert(contract.mode === 'owner-local-conversation', 'unexpected local conversation mode', errors);
  assert(contract.publicIngress === false, 'public ingress must remain disabled', errors);
  assert(contract.gateway?.host === '127.0.0.1', 'HTTPS gateway must bind to 127.0.0.1', errors);
  assert(contract.gateway?.port === 8443, 'HTTPS gateway must remain on port 8443', errors);
  assert(contract.security?.anonymousAccess === false, 'anonymous access must remain disabled', errors);
  assert(contract.security?.browserProviderKeys === false, 'browser provider keys must remain disabled', errors);
  assert(contract.security?.localLlmOnly === true, 'local LLM-only mode must remain enabled', errors);
  assert(contract.security?.mutationRequiresApproval === true, 'mutations must require approval', errors);
  assert(contract.security?.runtimeEgressAfterBootstrap === false, 'runtime egress must be detached after bootstrap', errors);

  const seenPorts = new Set();
  for (const service of contract.publishedLoopbackServices ?? []) {
    assert(service.host === '127.0.0.1', `${service.id} must bind to 127.0.0.1`, errors);
    assert(!seenPorts.has(service.hostPort), `duplicate published host port ${service.hostPort}`, errors);
    seenPorts.add(service.hostPort);

    const envName = PORT_ENV.get(service.id);
    assert(Boolean(envName), `missing port environment mapping for ${service.id}`, errors);
    const block = serviceBlock(compose, service.id);
    assert(Boolean(block), `compose service missing: ${service.id}`, errors);
    if (block && envName) {
      const expected = `127.0.0.1:${'${'}${envName}:-${service.hostPort}}:${service.containerPort}`;
      assert(block.includes(expected), `${service.id} must publish only ${expected}`, errors);
      assert(block.includes('ports:'), `${service.id} must declare its loopback port`, errors);
    }
  }

  for (const service of contract.internalOnlyServices ?? []) {
    const block = serviceBlock(compose, service.id);
    assert(Boolean(block), `internal compose service missing: ${service.id}`, errors);
    if (block) {
      assert(!/^    ports:/m.test(block), `${service.id} must not publish a host port`, errors);
    }
  }

  assert(compose.includes('VOICE_ALLOW_ANONYMOUS: "false"'), 'voice gateway anonymous access must be false', errors);
  assert(compose.includes('ZVOICE_ALLOW_ANONYMOUS: "false"'), 'zvoice anonymous access must be false', errors);
  assert(compose.includes('ZARVIS_LOCAL_LLM_BASE_URL: http://ollama:11434/v1'), 'zvoice must use local Ollama', errors);
  assert(compose.includes('VOICE_LLM_BASE_URL: http://ollama:11434/v1'), 'voice agent must use local Ollama', errors);
  assert(/networks:\s*\n\s+zarvis-voice-internal:\s*\n\s+internal: true/m.test(compose), 'voice runtime network must remain internal', errors);

  const listenLines = nginx
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.startsWith('listen ') && line.includes('8443'));
  assert(listenLines.length > 0, 'nginx must listen on 8443', errors);
  for (const line of listenLines) {
    assert(line.startsWith('listen 127.0.0.1:8443 ssl'), `unsafe 8443 listener: ${line}`, errors);
  }

  const voiceRoutePattern = /server_name voice\.zarvis\.zeaz\.dev;[\s\S]*?location \/v1\/realtime \{[\s\S]*?proxy_pass http:\/\/127\.0\.0\.1:8450;[\s\S]*?location \/ \{[\s\S]*?proxy_pass http:\/\/127\.0\.0\.1:3023;/m;
  assert(voiceRoutePattern.test(nginx), 'voice nginx routes must map realtime->8450 and UI/API->3023', errors);

  for (const upstream of contract.forbiddenGatewayUpstreams ?? []) {
    assert(!nginx.includes(`proxy_pass ${upstream}`), `forbidden direct gateway upstream present: ${upstream}`, errors);
  }

  return { contract, errors };
}

export function parseSsListeners(output) {
  const listeners = new Map();
  for (const rawLine of output.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    const columns = line.split(/\s+/);
    const local = columns.at(-2);
    if (!local) continue;

    let host;
    let portText;
    if (local.startsWith('[')) {
      const match = local.match(/^\[([^\]]+)]:(\d+)$/);
      if (!match) continue;
      [, host, portText] = match;
    } else {
      const index = local.lastIndexOf(':');
      if (index < 0) continue;
      host = local.slice(0, index);
      portText = local.slice(index + 1);
    }

    const port = Number(portText);
    if (!Number.isInteger(port)) continue;
    if (!listeners.has(port)) listeners.set(port, new Set());
    listeners.get(port).add(host);
  }
  return listeners;
}

export function validateRuntimeListeners(contract, output, { allowMissing = false } = {}) {
  const errors = [];
  const listeners = parseSsListeners(output);
  const expected = [
    { id: 'private-https-gateway', host: contract.gateway.host, port: contract.gateway.port },
    ...(contract.publishedLoopbackServices ?? []).map((service) => ({
      id: service.id,
      host: service.host,
      port: service.hostPort,
    })),
  ];

  for (const endpoint of expected) {
    const hosts = listeners.get(endpoint.port);
    if (!hosts || hosts.size === 0) {
      if (!allowMissing) errors.push(`${endpoint.id} is not listening on ${endpoint.host}:${endpoint.port}`);
      continue;
    }
    for (const host of hosts) {
      if (host !== endpoint.host) {
        errors.push(`${endpoint.id} has unsafe listener ${host}:${endpoint.port}`);
      }
    }
    if (!hosts.has(endpoint.host)) {
      errors.push(`${endpoint.id} is not bound to required host ${endpoint.host}:${endpoint.port}`);
    }
  }

  return { listeners, errors };
}

function runRuntimeValidation(contract, { allowMissing = false } = {}) {
  const output = execFileSync('ss', ['-H', '-ltn'], { encoding: 'utf8' });
  return validateRuntimeListeners(contract, output, { allowMissing });
}

function isMainModule() {
  return process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
}

if (isMainModule()) {
  const runtime = process.argv.includes('--runtime');
  const allowMissing = process.argv.includes('--allow-missing');
  const json = process.argv.includes('--json');

  try {
    const staticResult = validateStaticContract();
    const errors = [...staticResult.errors];
    let runtimeResult = null;

    if (runtime) {
      runtimeResult = runRuntimeValidation(staticResult.contract, { allowMissing });
      errors.push(...runtimeResult.errors);
    }

    const result = {
      ok: errors.length === 0,
      mode: staticResult.contract.mode,
      domain: staticResult.contract.domain,
      errors,
    };

    if (runtimeResult) {
      result.listeners = Object.fromEntries(
        [...runtimeResult.listeners.entries()].map(([port, hosts]) => [String(port), [...hosts].sort()]),
      );
    }

    if (json) {
      console.log(JSON.stringify(result, null, 2));
    } else if (errors.length === 0) {
      console.log('Z.A.R.V.I.S. local conversation contract: OK');
    } else {
      for (const error of errors) console.error(`[FAIL] ${error}`);
    }

    process.exitCode = errors.length === 0 ? 0 : 1;
  } catch (error) {
    console.error(`[FAIL] ${error.message}`);
    process.exitCode = 2;
  }
}
