import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const workflow = await readFile(".github/workflows/container-images.yml", "utf8");

test("container publication pins Node 24 action majors by immutable SHA", () => {
  const expected = [
    ["actions/checkout", "3d3c42e5aac5ba805825da76410c181273ba90b1", "v5"],
    ["docker/setup-buildx-action", "bb05f3f5519dd87d3ba754cc423b652a5edd6d2c", "v4"],
    ["docker/login-action", "af1e73f918a031802d376d3c8bbc3fe56130a9b0", "v4"],
    ["docker/metadata-action", "dc802804100637a589fabce1cb79ff13a1411302", "v6"],
    ["docker/build-push-action", "53b7df96c91f9c12dcc8a07bcb9ccacbed38856a", "v7"],
  ];
  for (const [action, sha, major] of expected) {
    assert.match(workflow, new RegExp(`uses: ${action}@${sha} # ${major}`));
  }
  assert.doesNotMatch(workflow, /uses:\s+[^\s]+@v\d+/);
});
