import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

const script = path.resolve("scripts/resolve-ghcr-credentials.sh");

async function resolveCredentials(overrides) {
  const directory = await mkdtemp(path.join(tmpdir(), "ghcr-resolver-"));
  const githubEnv = path.join(directory, "github-env");
  const env = {
    PATH: process.env.PATH,
    GITHUB_ENV: githubEnv,
    GHCR_USERNAME: "",
    GHCR_PULL_TOKEN: "",
    GHCR_OAUTH_ID: "",
    GHCR_OAUTH_TOKEN: "",
    ...overrides,
  };
  const result = spawnSync("bash", [script], { env, encoding: "utf8" });
  const output = result.status === 0 ? await readFile(githubEnv, "utf8") : "";
  await rm(directory, { recursive: true, force: true });
  return { ...result, output };
}

test("prefers the legacy GHCR pair when both patterns are configured", async () => {
  const result = await resolveCredentials({
    GHCR_USERNAME: "legacy-user",
    GHCR_PULL_TOKEN: "legacy-token",
    GHCR_OAUTH_ID: "oauth-id",
    GHCR_OAUTH_TOKEN: "oauth-token",
  });
  assert.equal(result.status, 0);
  assert.match(result.output, /GHCR_EFFECTIVE_USERNAME=legacy-user/);
  assert.match(result.output, /GHCR_EFFECTIVE_TOKEN=legacy-token/);
  assert.match(result.output, /GHCR_CREDENTIAL_SOURCE=legacy/);
});

test("falls back to the OAuth GHCR pair", async () => {
  const result = await resolveCredentials({ GHCR_OAUTH_ID: "oauth-id", GHCR_OAUTH_TOKEN: "oauth-token" });
  assert.equal(result.status, 0);
  assert.match(result.output, /GHCR_EFFECTIVE_USERNAME=oauth-id/);
  assert.match(result.output, /GHCR_EFFECTIVE_TOKEN=oauth-token/);
  assert.match(result.output, /GHCR_CREDENTIAL_SOURCE=oauth/);
});

test("rejects partial pairs instead of mixing credential patterns", async () => {
  const result = await resolveCredentials({ GHCR_USERNAME: "legacy-user", GHCR_OAUTH_ID: "oauth-id", GHCR_OAUTH_TOKEN: "oauth-token" });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /must be provided together/);
  assert.doesNotMatch(result.stderr, /oauth-token|legacy-user/);
});
