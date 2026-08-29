import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import test from "node:test";

const root = fileURLToPath(new URL("../..", import.meta.url));
const read = (relative) => readFile(join(root, relative), "utf8");

const [
  operatorInputsStatus,
  operatorInputsRegister,
  releaseReadme,
  ownershipDoc,
  productionRecordDoc,
  productionRecordSchema,
  externalWorkflow,
  finalWorkflow,
] = await Promise.all([
  read("docs/operations/operator-inputs-status.md"),
  read("docs/operations/phase-6-operator-inputs.md"),
  read("docs/release/README.md"),
  read("docs/release/operational-ownership.md"),
  read("docs/release/production-release-record.md"),
  read("schemas/release/production-release-record.schema.json"),
  read(".github/workflows/external-staging-readiness.yml"),
  read(".github/workflows/final-release-readiness.yml"),
]);

test("operator inputs status documents the remaining operator-owned stack", () => {
  assert.match(operatorInputsStatus, /PENDING_OPERATOR/);
  assert.match(operatorInputsStatus, /external identity provider/i);
  assert.match(operatorInputsStatus, /Production secret-manager selection/i);
  assert.match(operatorInputsStatus, /Managed production data services/i);
  assert.match(operatorInputsStatus, /Billing currency/i);
  assert.match(operatorInputsStatus, /Staging reviewer/i);
  assert.match(operatorInputsStatus, /Agent cancellation/i);
  assert.match(operatorInputsStatus, /Deployed ZWallet and ZChat QA/i);
  assert.match(operatorInputsStatus, /Issue #1 operator mapping/);
  assert.match(operatorInputsStatus, /phase-6-operator-inputs\.json/);
  assert.match(operatorInputsStatus, /cloudflare-access\.md/);
  assert.match(operatorInputsStatus, /final-release-readiness\.yml/);
});

test("phase 6 operator register points at the release sign-off records", () => {
  assert.match(operatorInputsRegister, /Release sign-off records/);
  assert.match(operatorInputsRegister, /operational-ownership\.md/);
  assert.match(operatorInputsRegister, /production-release-record\.md/);
  assert.match(operatorInputsRegister, /external-staging-readiness\.yml/);
  assert.match(operatorInputsRegister, /final-release-readiness\.yml/);
  assert.match(operatorInputsRegister, /Issue #1 operator-item mapping/);
  assert.match(operatorInputsRegister, /Identity \/ Cloudflare/);
  assert.match(operatorInputsRegister, /Finance \/ legal/);
  assert.match(operatorInputsRegister, /phase-6-operator-inputs\.json/);
});

test("release governance README names the operator-controlled records", () => {
  assert.match(releaseReadme, /Operational ownership/);
  assert.match(releaseReadme, /Production release record/);
  assert.match(releaseReadme, /PENDING_OPERATOR/);
});

test("operational ownership record remains fail-closed until approved", () => {
  assert.match(ownershipDoc, /Initial state: `PENDING_OPERATOR`/);
  assert.match(ownershipDoc, /APPROVED_OPERATOR/);
  assert.match(ownershipDoc, /Incident command/);
  assert.match(ownershipDoc, /Production approver/);
  assert.match(ownershipDoc, /Rollback owner/);
  assert.match(ownershipDoc, /PENDING_OPERATOR -> APPROVED_OPERATOR/);
});

test("production release record captures approval and execution fields", () => {
  assert.match(productionRecordDoc, /Status: `PENDING_OPERATOR`/);
  assert.match(productionRecordDoc, /Explicit decision/);
  assert.match(productionRecordDoc, /Operator record/);
  assert.match(productionRecordDoc, /Staging reviewer/);
  assert.match(productionRecordDoc, /Incident owner/);
  assert.match(productionRecordDoc, /Escalation route/);
  assert.match(productionRecordDoc, /Watch window/);
  assert.match(productionRecordDoc, /Execution record/);
  assert.match(productionRecordDoc, /Final outcome recorded as `DEPLOYED`, `ROLLED_BACK`, or `RELEASE_FAILED`/);
  assert.match(productionRecordSchema, /"operatorRecord"/);
  assert.match(productionRecordSchema, /"stagingReviewer"/);
  assert.match(productionRecordSchema, /"incidentOwner"/);
  assert.match(productionRecordSchema, /"escalationRoute"/);
  assert.match(productionRecordSchema, /"watchWindow"/);
});

test("external staging and final release workflows retain protected approval gates", () => {
  assert.match(externalWorkflow, /STAGING_REVIEWER/);
  assert.match(externalWorkflow, /INCIDENT_OWNER/);
  assert.match(externalWorkflow, /ESCALATION_ROUTE/);
  assert.match(externalWorkflow, /WATCH_WINDOW/);
  assert.match(externalWorkflow, /PRODUCTION_APPROVER/);
  assert.match(finalWorkflow, /environment: production/);
  assert.match(finalWorkflow, /final-production-approval/);
  assert.match(finalWorkflow, /issues: write/);
  assert.match(finalWorkflow, /state=closed/);
});
