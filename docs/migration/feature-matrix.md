# Migration Feature Matrix

| Capability | Boundary | Status | Validation |
|---|---|---|---|
| Release evidence commit binding | `scripts/validate-release-evidence.mjs` | complete | Rejects missing, malformed, placeholder, and mismatched release-candidate commit SHAs. |
| Provider credential isolation | Server adapters only | preserved | No provider SDK or credential handling is introduced by this slice. |
| CLI credential isolation | Platform CLI | preserved | The validator accepts only a record path and immutable commit SHA. |

This matrix records the vertical slice completed by `feat/release-evidence-commit-binding`.
