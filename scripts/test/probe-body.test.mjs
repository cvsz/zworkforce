import assert from "node:assert/strict";
import test from "node:test";

import { withJsonBody } from "../probe-body.mjs";

test("adds a JSON content type only when a body is present", () => {
  const empty = withJsonBody({ Accept: "application/json" }, undefined);
  assert.deepEqual(empty, { headers: { Accept: "application/json" }, body: undefined });

  const populated = withJsonBody({ Accept: "application/json" }, { hello: "world" });
  assert.equal(populated.body, '{"hello":"world"}');
  assert.equal(populated.headers.Accept, "application/json");
  assert.equal(populated.headers["Content-Type"], "application/json");
});
