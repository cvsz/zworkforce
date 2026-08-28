import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = fileURLToPath(new URL("../..", import.meta.url));
const envScope = join(root, "scripts/cloudflare/lib/env-scope.sh");
const rotation = join(root, "scripts/cloudflare/rotate-tokens-with-permission-preflight.sh");

function loadScopedValue({ shellValue, baseValue, generatedValue }) {
  const fixture = mkdtempSync(join(tmpdir(), "z-platform-cf-env-"));
  const baseFile = join(fixture, "base.env");
  const generatedFile = join(fixture, "generated.env");
  writeFileSync(baseFile, `CLOUDFLARE_ACCOUNT_ID=${baseValue ?? ""}\n`, { mode: 0o600 });
  writeFileSync(generatedFile, `CLOUDFLARE_ACCOUNT_ID=${generatedValue ?? ""}\n`, { mode: 0o600 });

  const environment = {
    ...process.env,
    PROJECT_ROOT: root,
    CLOUDFLARE_ENV_FILE: baseFile,
    CLOUDFLARE_TOKEN_ENV_FILE: generatedFile,
  };
  if (shellValue === undefined) {
    delete environment.CLOUDFLARE_ACCOUNT_ID;
  } else {
    environment.CLOUDFLARE_ACCOUNT_ID = shellValue;
  }

  return execFileSync(
    "bash",
    ["-c", 'source "$1"; cf_load_cloudflare_env_scope; printf "%s" "${CLOUDFLARE_ACCOUNT_ID-<unset>}"', "bash", envScope],
    { cwd: root, env: environment, encoding: "utf8" },
  );
}

test("Cloudflare env scope preserves explicit non-empty shell identity", () => {
  assert.equal(
    loadScopedValue({ shellValue: "shell-account", baseValue: "base-account", generatedValue: "generated-account" }),
    "shell-account",
  );
});

test("Cloudflare env scope prefers base identity over generated identity", () => {
  assert.equal(
    loadScopedValue({ baseValue: "base-account", generatedValue: "generated-account" }),
    "base-account",
  );
});

test("Cloudflare env scope falls back from blank base identity to generated identity", () => {
  assert.equal(
    loadScopedValue({ baseValue: "", generatedValue: "generated-account" }),
    "generated-account",
  );
});

test("offline token rotation previews scoped tokens without writing output", () => {
  const fixture = mkdtempSync(join(tmpdir(), "z-platform-cf-rotation-"));
  const outputFile = join(fixture, "tokens.env");
  const cacheDirectory = join(fixture, "cache");
  const permissionCache = join(
    cacheDirectory,
    "account-token-permission-groups.00000000000000000000000000000000.json",
  );
  execFileSync("mkdir", ["-p", cacheDirectory]);
  writeFileSync(
    permissionCache,
    JSON.stringify({
      success: true,
      result: [
        { name: "DNS Write", id: "dns-write" },
        { name: "Access: Apps and Policies Write", id: "access-write" },
        { name: "Workers Scripts Write", id: "workers-write" },
        { name: "Workers Routes Write", id: "workers-routes-write" },
        { name: "Pages Write", id: "pages-write" },
        { name: "Cloudflare Tunnel Write", id: "tunnel-write" },
      ],
    }),
    { mode: 0o600 },
  );
  writeFileSync(
    outputFile,
    [
      "PRIMARY_DOMAIN=zeaz.dev",
      "CLOUDFLARE_BOOTSTRAP_TOKEN=sentinel-bootstrap-secret",
      'CLOUDFLARE_API_TOKEN="sentinel-api-secret"',
      "ACCESS_SECRET_KEY=sentinel-access-secret",
      "ACCESS_KEY_ID=sentinel-access-id",
      "",
    ].join("\n"),
    { mode: 0o600 },
  );
  const result = spawnSync(
    "bash",
    [
      rotation,
      "--offline",
      "--regenerate",
      "--types",
      "dns,zt,workers,pages,tunnel",
      "--write",
      outputFile,
      "--dry-run",
    ],
    {
      cwd: root,
      env: {
        ...process.env,
        CLOUDFLARE_ENV_FILE: "/dev/null",
        CLOUDFLARE_TOKEN_ENV_FILE: "/dev/null",
        CLOUDFLARE_ACCOUNT_ID: "00000000000000000000000000000000",
        CLOUDFLARE_ZONE_ID: "11111111111111111111111111111111",
        CACHE_DIR: cacheDirectory,
        BACKUP_DIR: join(fixture, "backups"),
        AUDIT_LOG: join(fixture, "audit.log"),
      },
      encoding: "utf8",
    },
  );

  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /DRY-RUN: would create zeaz-dns-token/);
  assert.match(result.stdout, /resolved dns permission-group override: dns-write/);
  assert.match(result.stdout, /resolved pages permission-group override: pages-write/);
  assert.match(result.stdout, /resolved tunnel permission-group override: tunnel-write/);
  assert.doesNotMatch(result.stdout + result.stderr, /could not resolve permission-group ID for (dns|pages|tunnel)/);
  assert.match(result.stdout, /CLOUDFLARE_DNS_TOKEN="<redacted>"/);
  assert.doesNotMatch(result.stdout, /sentinel-/);
  assert.match(result.stdout, /CLOUDFLARE_BOOTSTRAP_TOKEN="<redacted>"/);
  assert.match(result.stdout, /ACCESS_SECRET_KEY="<redacted>"/);
  assert.match(result.stdout, /ACCESS_KEY_ID="<redacted>"/);
  assert.match(readFileSync(outputFile, "utf8"), /sentinel-bootstrap-secret/);
});

test("live Make targets require explicit operator confirmation", () => {
  const makefile = readFileSync(join(root, "Makefile"), "utf8");
  assert.match(makefile, /TOKEN_ROTATE_CONFIRM\)" = "YES"/);
  assert.match(makefile, /TOKEN_CLEAN_CONFIRM\)" = "YES"/);
  assert.match(makefile, /TOKEN_BOOTSTRAP_ROLL_CONFIRM\)" = "YES"/);
  assert.match(makefile, /TOKEN_LEGACY_SCRUB_CONFIRM\)" = "YES"/);
  assert.match(makefile, /TOKEN_ROTATE_TYPES \?= dns,zt,workers,pages,tunnel/);
});
