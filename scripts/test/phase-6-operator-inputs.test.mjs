import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { validatePhase6OperatorInputs } from "../validate-phase-6-operator-inputs.mjs";

const inputs = JSON.parse(await readFile(new URL("../../scripts/phase-6-operator-inputs.json", import.meta.url), "utf8"));
const schema = JSON.parse(await readFile(new URL("../../schemas/operations/phase-6-operator-inputs.schema.json", import.meta.url), "utf8"));

test("accepts the current phase 6 operator input register", () => {
  assert.deepEqual(validatePhase6OperatorInputs(inputs), []);
});

test("rejects an operator input record that stops being explicitly pending", () => {
  const value = structuredClone(inputs);
  value.items[0].status = "APPROVED_OPERATOR";
  assert.match(validatePhase6OperatorInputs(value).join("\n"), /status must be PENDING_OPERATOR/);
});

test("rejects a missing operator input item", () => {
  const value = structuredClone(inputs);
  value.items.pop();
  assert.match(validatePhase6OperatorInputs(value).join("\n"), /expected 5 operator-input records/);
});

test("exposes the pending operator contract in schema form", () => {
  assert.equal(schema.$schema, "https://json-schema.org/draft/2020-12/schema");
  assert.equal(schema.properties.schemaVersion.const, "1.0.0");
  assert.equal(schema.properties.items.minItems, 5);
  assert.equal(schema.properties.items.items.properties.status.const, "PENDING_OPERATOR");
});
