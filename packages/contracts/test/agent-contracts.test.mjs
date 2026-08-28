import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";

const schemaDir = new URL("../schemas/", import.meta.url);

async function readSchema(name) {
  return JSON.parse(await readFile(new URL(name, schemaDir), "utf8"));
}

function assertCommonEnvelope(schema, eventType) {
  for (const field of ["event_id", "event_type", "event_version", "occurred_at", "tenant_id", "job_id"]) {
    assert.ok(schema.required.includes(field), `${eventType} requires ${field}`);
  }
  assert.equal(schema.properties.event_type.const, eventType);
  assert.equal(schema.properties.event_version.const, "v1");
  assert.equal(schema.properties.occurred_at.format, "date-time");
  assert.equal(schema.additionalProperties, false);
}

test("agent job event schemas expose immutable common envelopes", async () => {
  const schemas = [
    ["agent.job.requested.v1.schema.json", "agent.job.requested.v1"],
    ["agent.job.approved.v1.schema.json", "agent.job.approved.v1"],
    ["agent.job.completed.v1.schema.json", "agent.job.completed.v1"],
  ];

  for (const [file, eventType] of schemas) {
    assertCommonEnvelope(await readSchema(file), eventType);
  }
});

test("requested job schema requires explicit tool grants and approval policy", async () => {
  const schema = await readSchema("agent.job.requested.v1.schema.json");
  assert.ok(schema.required.includes("requested_by"));
  assert.ok(schema.required.includes("objective"));
  assert.ok(schema.required.includes("tool_grants_requested"));
  assert.equal(schema.properties.tool_grants_requested.minItems, 1);
  assert.ok(schema.properties.execution_policy.required.includes("requires_approval"));
});

test("approved job schema carries approval state, grants, and runtime constraints", async () => {
  const schema = await readSchema("agent.job.approved.v1.schema.json");
  assert.deepEqual(schema.properties.approval_state.enum, ["approved", "rejected"]);
  assert.ok(schema.properties.tool_grants.items.required.includes("expires_at"));
  assert.deepEqual(schema.properties.constraints.properties.sandbox.enum, ["restricted", "isolated"]);
  assert.deepEqual(schema.properties.constraints.properties.network.enum, ["deny-by-default", "allowlisted"]);
});

test("completed job schema captures terminal status and audit trail", async () => {
  const schema = await readSchema("agent.job.completed.v1.schema.json");
  assert.deepEqual(schema.properties.status.enum, ["succeeded", "failed", "cancelled", "expired"]);
  assert.ok(schema.required.includes("audit"));
  assert.ok(schema.properties.audit.required.includes("tool_calls"));
  assert.deepEqual(schema.properties.audit.properties.tool_calls.items.properties.status.enum, ["succeeded", "failed", "skipped"]);
});
