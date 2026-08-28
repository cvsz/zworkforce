import assert from "node:assert/strict";
import test from "node:test";

import { validateReleaseEvidence } from "../validate-release-evidence.mjs";

const sha = "0123456789abcdef0123456789abcdef01234567";

function record({ commitSha = sha, approvedCommitSha = sha, observedCommitSha = sha } = {}) {
  return `spec:\n  revision:\n    commitSha: ${commitSha}\n  approval:\n    approvedCommitSha: ${approvedCommitSha}\n  execution:\n    observedCommitSha: ${observedCommitSha}\n`;
}

test("accepts evidence bound to the exact release candidate", () => {
  assert.deepEqual(validateReleaseEvidence(record(), sha), []);
});

test("rejects evidence copied from another commit", () => {
  const stale = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  const errors = validateReleaseEvidence(record({ approvedCommitSha: stale }), sha);
  assert.match(errors.join("\n"), /approvedCommitSha.*does not match/);
});

test("rejects placeholders and missing fields", () => {
  const errors = validateReleaseEvidence("spec:\n  revision:\n    commitSha: <40-character-sha>\n", sha);
  assert.equal(errors.length, 3);
  assert.match(errors.join("\n"), /commitSha must be/);
  assert.match(errors.join("\n"), /missing approvedCommitSha/);
  assert.match(errors.join("\n"), /missing observedCommitSha/);
});

test("rejects an invalid expected release candidate SHA", () => {
  assert.match(validateReleaseEvidence(record(), "main")[0], /expected commit SHA/);
});
