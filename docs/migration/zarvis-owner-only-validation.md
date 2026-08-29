# Z.A.R.V.I.S. Owner-Only Validation Record

Date: 2026-08-06
Branch: `feat/zarvis-voice-github-status`
Epic: #148
Pull request: #149

## Scope

This validation covers the requirement that the Z.A.R.V.I.S. instance can be used only by GitHub user ID `4076926` (`cvsz`).

## Implemented controls

- Immutable owner ID embedded in both the console and orchestrator.
- No environment variable or runtime endpoint can replace the owner.
- Console requires a trusted edge owner assertion and edge shared secret.
- Orchestrator requires the fixed owner ID and a separate console service token.
- All caller-supplied user and tenant headers are discarded.
- Audit identity is always `github:4076926` in tenant `owner-4076926`.
- All non-health routes fail closed.
- Missing or short secrets prevent service startup.

## Focused local validation

Runtime: Node.js `v22.16.0`

```text
8 tests passed
0 tests failed
```

Covered cases:

1. Console startup fails without owner secrets.
2. Console rejects unauthenticated access.
3. Console serves static UI only with the owner assertion.
4. Console replaces spoofed browser identity headers.
5. Console preserves content-type validation after authentication.
6. Orchestrator startup fails without its service token.
7. Orchestrator rejects direct requests.
8. Orchestrator derives actor identity from immutable owner ID.

## Pending gates

- Full repository test suite on the PR head.
- GitHub Actions CI, validate, and CodeQL completion.
- Deployment verification of the exact identity-provider allow policy.
- Origin firewall verification that direct public access is unavailable.
- Secret-manager evidence and rotation drill.

The branch must not be merged or deployed as owner-only production access until all pending gates are complete.
