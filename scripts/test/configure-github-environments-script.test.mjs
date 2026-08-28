import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";

const scriptPath = fileURLToPath(new URL("../../scripts/configure-github-environments.sh", import.meta.url));
const script = await readFile(scriptPath, "utf8");

test("environment script configures ci, staging, and production", () => {
  assert.match(script, /set_environment_payload "ci" none ""/);
  assert.match(script, /repos\/\$\{REPO\}\/environments\/\$\{environment_name\}/);
  assert.match(script, /set_environment_payload "staging"/);
  assert.match(script, /set_environment_payload "production"/);
});

test("environment script loads the local dotenv overlays in order", () => {
  assert.match(script, /load_default_env_files/);
  assert.match(script, /\.env\.phase6/);
  assert.match(script, /\.env\.phase6\.server/);
  assert.match(script, /load_env_file "\$env_file"/);
});

test("environment script requires explicit reviewer selectors", () => {
  assert.match(script, /--staging-reviewer/);
  assert.match(script, /--production-reviewer/);
  assert.match(script, /user:LOGIN\|team:SLUG/);
  assert.match(script, /normalize_reviewer_selector/);
  assert.match(script, /STAGING_REVIEWER/);
  assert.match(script, /INCIDENT_OWNER/);
  assert.match(script, /ESCALATION_ROUTE/);
  assert.match(script, /WATCH_WINDOW/);
  assert.match(script, /PRODUCTION_APPROVER/);
  assert.match(script, /PRODUCTION_REVIEWER/);
  assert.match(script, /sync_staging_environment_values/);
  assert.match(script, /sync_production_environment_values/);
  assert.match(script, /gh secret set "\$key" --repo "\$REPO" --env "\$environment_name"/);
  assert.match(script, /gh variable set "\$key" --repo "\$REPO" --env "\$environment_name"/);
  assert.match(script, /skipped empty/);
});

test("environment script sets protected branch policy for protected and main-only modes", () => {
  assert.match(script, /STAGING_BRANCH_POLICY/);
  assert.match(script, /PRODUCTION_BRANCH_POLICY/);
  assert.match(script, /STAGING_BRANCH_NAME/);
  assert.match(script, /PRODUCTION_BRANCH_NAME/);
  assert.match(script, /protected_branches":true/);
  assert.match(script, /custom_branch_policies":true/);
  assert.match(script, /deployment-branch-policies/);
});
