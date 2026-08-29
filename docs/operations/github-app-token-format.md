# GitHub App Token Format Readiness

GitHub is rolling out stateless JWT-format GitHub App installation server-to-server tokens. `z-platform` integrations that create or consume GitHub App installation tokens must accept both the current stateful opaque format and the new stateless JWT format.

## Scope

This applies to GitHub Enterprise Cloud and Data Residency environments for GitHub App installation server-to-server tokens, including Actions `GITHUB_TOKEN` behavior as GitHub rolls out the format. GitHub Enterprise Server is not in scope for this rollout.

This document is operational guidance only. Do not commit real installation tokens, private keys, app IDs, installation IDs, service tokens, or request output.

## Token formats

| Format | Shape | Detection |
|---|---|---|
| Stateful opaque token | `ghs_` prefix, short opaque string, no dots | zero dots after `ghs_` |
| Stateless JWT-format token | `ghs_` prefix, longer string, approximately 520 characters, contains two dots | two dots after `ghs_` |

Treat both formats as opaque credentials. Do not decode, introspect, parse, log, or derive authorization decisions from token claims.

## Temporary override header

When calling `POST /app/installations/:installation_id/access_tokens`, GitHub supports a temporary request header:

| Header | Value | Effect |
|---|---|---|
| `X-GitHub-Stateless-S2S-Token` | `enabled` | Force a stateless JWT-format installation token for that single request. |
| `X-GitHub-Stateless-S2S-Token` | `disabled` | Force a classic stateful opaque installation token for that single request. |
| absent | none | Use GitHub's normal rollout behavior. |

Other values such as `true`, `false`, `1`, or `0` are ignored by GitHub and should not be used.

The header is temporary. Remove it from production code after both formats are validated.

## Compatibility requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| GH-TOKEN-001 | Token validators MUST accept both stateful and stateless `ghs_` tokens. | Validation accepts `ghs_[A-Za-z0-9._-]{36,}`. |
| GH-TOKEN-002 | Token storage MUST allow at least 520 characters. | Database columns, secret-store fields, env var validators, and config schemas accept long JWT-format tokens. |
| GH-TOKEN-003 | Token handling MUST treat `ghs_` values as opaque strings. | Code does not decode JWT claims, split for authorization, or assume fixed length. |
| GH-TOKEN-004 | Logs and traces MUST redact installation tokens. | No token value is emitted in application logs, CI logs, traces, audit events, or error messages. |
| GH-TOKEN-005 | Tests SHOULD cover both override modes. | Token creation clients are tested with `enabled` and `disabled` override responses. |
| GH-TOKEN-006 | Production code SHOULD NOT keep the temporary override header after validation. | Header usage is removed or limited to an explicit test harness. |

## Recommended token regex

Use this regex only to recognize a GitHub App installation token shape, not to prove validity:

```text
ghs_[A-Za-z0-9._-]{36,}
```

The character class intentionally allows dots, hyphens, and underscores so JWT-format stateless tokens match.

## Validation plan

1. Inventory every code path that requests `POST /app/installations/:installation_id/access_tokens`.
2. Inventory every code path that stores, validates, forwards, logs, or redacts `ghs_` tokens.
3. Test token creation with `X-GitHub-Stateless-S2S-Token: enabled` and confirm the stateless token flows end to end.
4. Test token creation with `X-GitHub-Stateless-S2S-Token: disabled` and confirm the classic opaque token still flows end to end.
5. Confirm storage, environment variables, secret manager fields, and configuration schemas support at least 520 characters.
6. Confirm redaction handles both formats, including JWT dots.
7. Remove the override header from production code after validation.
8. Record the validation result in the release notes or production readiness checklist.

## Do not log sample tokens

Examples in tests should use synthetic placeholders, not real GitHub tokens. If fixture values are needed, use strings such as:

```text
ghs_opaqueplaceholdertokenvalue000000000000
ghs_header.payload.signature_placeholder_value_000000000000
```

Do not use a real token captured from GitHub, even if expired.

## Production readiness checklist

- [ ] No fixed-length assumptions for `ghs_` tokens.
- [ ] Regex accepts dots, hyphens, underscores, and long values.
- [ ] Storage supports at least 520 characters.
- [ ] Token redaction catches both opaque and JWT-format tokens.
- [ ] Stateless token path tested with `enabled` override.
- [ ] Stateful token path tested with `disabled` override.
- [ ] Temporary override header removed from production path after validation.
- [ ] Release record includes validation evidence and rollback notes.

## Related documents

- [Master requirements](../requirements/master-requirements.md)
- [Production master document](production-master.md)
- [Security policy](../../SECURITY.md)
