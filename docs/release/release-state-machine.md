# Release State Machine

The release state is derived from evidence and approvals; it is not a manually optimistic label.

```text
PENDING_EXTERNAL
  ├─ VERIFIED_EXTERNAL
  └─ EXTERNAL_VERIFICATION_FAILED

PENDING_OPERATOR
  └─ APPROVED_OPERATOR

VERIFIED_EXTERNAL + APPROVED_OPERATOR
  └─ READY_FOR_RELEASE

READY_FOR_RELEASE + explicit GO
  └─ RELEASE_APPROVED

RELEASE_APPROVED
  ├─ DEPLOYED
  ├─ ROLLED_BACK
  └─ RELEASE_FAILED
```

## Transition record

Every state transition must record:

- previous state and new state;
- actor or service identity;
- ISO-8601 timestamp;
- repository and full commit SHA;
- exact image digests;
- environment and region;
- evidence references and evidence digest;
- decision or approval reference;
- unresolved risks and exceptions.

## Transition guards

| Transition | Mandatory guards |
|---|---|
| `PENDING_EXTERNAL -> VERIFIED_EXTERNAL` | External deployed staging evidence passes and is bound to the candidate revision. |
| `PENDING_OPERATOR -> APPROVED_OPERATOR` | Reviewer, incident, rollback, release, and approval ownership are explicit. |
| `VERIFIED_EXTERNAL + APPROVED_OPERATOR -> READY_FOR_RELEASE` | Both records reference the same candidate and remain valid. |
| `READY_FOR_RELEASE -> RELEASE_APPROVED` | Authorized production approver records explicit `GO`, exact revision, evidence digest, and change window. |
| `RELEASE_APPROVED -> DEPLOYED` | Production observes the exact approved commit and image digests and post-deploy checks pass. |
| `RELEASE_APPROVED -> ROLLED_BACK` | Abort criteria trigger and the rollback plan completes. |
| `RELEASE_APPROVED -> RELEASE_FAILED` | Deployment or rollback cannot meet defined safety criteria. |

## Invalid transitions

The following are prohibited:

- deriving `VERIFIED_EXTERNAL` from local, mocked, or Compose-only tests;
- treating a PR merge as production approval;
- approving one revision and deploying another;
- using floating image tags as release identity;
- approving without named operational and rollback ownership;
- modifying evidence after approval without invalidating the approval;
- bypassing an abort criterion without auditable emergency authorization.

## Invalidation

A verification or approval returns to pending when the candidate SHA or any image digest changes, evidence integrity fails, a critical finding opens, the approval expires, or the target environment materially changes.