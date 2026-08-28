# Z.A.R.V.I.S. Threat Model

Scope: first vertical slice — voice/text transcript to read-only GitHub repository status.

## Protected assets

- Server-side `GITHUB_TOKEN`.
- Tenant and user identifiers.
- Command transcripts.
- Tool arguments and normalized results.
- Audit event integrity.
- Availability of the console and orchestrator.

## Security invariants

1. Browser code never receives GitHub or model-provider credentials.
2. The only executable capability is `github.repository.status` with `read_only` access.
3. User input cannot select an arbitrary upstream host, HTTP method, header, or URL path.
4. Unsupported or mutating tool requests fail closed.
5. Raw upstream response bodies and authorization headers are not copied into responses or audit events.
6. Every tool attempt emits a success or failure audit event.
7. Microphone use requires a direct browser user action; there is no continuous listening.

## Threat analysis

| Threat | Example | Mitigation | Residual risk |
|---|---|---|---|
| Credential exposure | Browser bundle contains `GITHUB_TOKEN` | Token is read only by the orchestrator process; console proxy never adds authorization | Deployment logs or host compromise remain out of scope for this slice |
| SSRF | Transcript contains an internal URL | Tool accepts owner/repo segments and constructs a fixed `api.github.com` URL | DNS or upstream compromise is an infrastructure concern |
| Tool escalation | Client asks for repository deletion | Tool name allowlist admits only `github.repository.status`; unknown tools return 400/422 | Future tools must preserve separate approval contracts |
| Redirect abuse | GitHub-like endpoint redirects to attacker host | `redirect: error` | Upstream implementation behavior must remain covered by tests |
| Prompt/intent injection | Transcript asks the assistant to ignore policy | Deterministic parser and explicit tool contract; no model-generated tool name in this slice | Natural-language coverage is intentionally narrow |
| Audit secret leakage | Error body includes token or private metadata | Audit fields are allowlisted; raw headers and bodies are excluded | Logger configuration must protect tenant metadata |
| Oversized request | Large transcript exhausts memory | 32 KiB body limit and 2,000-character transcript limit | Distributed request floods require gateway rate limiting |
| Cross-site data extraction | Malicious page frames console | CSP `frame-ancestors 'none'`, `X-Frame-Options: DENY`, same-origin API | Authentication and CSRF controls are required before personalized deployment |
| Ambient microphone collection | App listens continuously | Push-to-start browser recognition only; no audio upload by this console | Browser vendor speech services may have their own privacy terms |
| Tenant spoofing | Client supplies arbitrary identity headers | Headers are treated as provisional context only | Production must inject verified claims at the identity gateway and strip client-supplied identity headers |

## Production prerequisites

The slice must not be exposed as a multi-tenant production service until these controls exist:

- Identity gateway strips untrusted identity headers and injects verified tenant/user claims.
- Rate limiting and request budgets at the edge and service boundary.
- Durable append-only audit transport with retention and access controls.
- Secret manager integration and token rotation.
- Egress policy allowing only approved GitHub API destinations.
- Metrics and alerts for failure rate, timeout rate, audit sink failures, and unusual repository enumeration.
- Data-retention policy for transcripts and audit records.
- Security review for the browser speech-recognition provider behavior in each supported browser.

## Explicit exclusions

- No financial transactions.
- No repository writes.
- No shell or desktop automation.
- No continuous microphone or camera surveillance.
- No biometric identification.
- No physical control, weapon control, targeting, or offensive security actions.
