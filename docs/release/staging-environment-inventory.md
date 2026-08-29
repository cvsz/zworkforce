# Staging Environment Inventory

Status: `PENDING_EXTERNAL`

This inventory records the externally deployed staging environment. Do not mark an item verified without a durable evidence reference. Never store credentials, tokens, private keys, or unredacted account identifiers in this document.

## Release candidate

| Field | Value |
|---|---|
| Repository | `cvsz/z-platform` |
| Environment | `staging` |
| Region | `<region>` |
| Full commit SHA | `<40-character-sha>` |
| Deployment revision | `<revision-or-release-id>` |
| Deployment timestamp | `<ISO-8601>` |
| Operator | `<GitHub-handle-or-service-identity>` |
| Evidence root | `<artifact-or-log-reference>` |

## Immutable workloads

Every image must use `registry/repository@sha256:<digest>`. Floating tags such as `latest`, `main`, or semantic tags without a digest are prohibited.

| Workload | Image digest | Runtime | Namespace/project | Evidence |
|---|---|---|---|---|
| Gateway | `<image@sha256:...>` | `<k3s/kubernetes/etc>` | `<scope>` | `<reference>` |
| API | `<image@sha256:...>` | `<runtime>` | `<scope>` | `<reference>` |
| Worker | `<image@sha256:...>` | `<runtime>` | `<scope>` | `<reference>` |
| Web | `<image@sha256:...>` | `<runtime>` | `<scope>` | `<reference>` |

## Infrastructure components

| Component | Provider/product | Account/project (redacted) | Region | Endpoint (redacted where needed) | Identity/secret reference | Evidence | State |
|---|---|---|---|---|---|---|---|
| Database | `<provider>` | `<redacted>` | `<region>` | `<endpoint>` | `<secret-manager-ref>` | `<reference>` | `PENDING` |
| Queue | `<provider>` | `<redacted>` | `<region>` | `<endpoint>` | `<secret-manager-ref>` | `<reference>` | `PENDING` |
| Object storage | `<provider>` | `<redacted>` | `<region>` | `<endpoint>` | `<secret-manager-ref>` | `<reference>` | `PENDING` |
| Identity provider | `<provider>` | `<redacted>` | `<region>` | `<issuer>` | `<client-secret-ref>` | `<reference>` | `PENDING` |
| Sandbox workers | `<runtime>` | `<redacted>` | `<region>` | `<control-endpoint>` | `<workload-identity>` | `<reference>` | `PENDING` |
| Observability | `<provider>` | `<redacted>` | `<region>` | `<dashboard/log endpoint>` | `<identity-ref>` | `<reference>` | `PENDING` |
| Secret manager | `<provider>` | `<redacted>` | `<region>` | `<vault/project>` | `<workload-identity>` | `<reference>` | `PENDING` |

## Network and security boundaries

- Browser clients receive no provider credentials.
- Provider calls traverse the platform gateway.
- Ingress, egress, DNS, TLS, and certificate evidence are linked.
- Workload identity and least-privilege grants are recorded.
- Administrative access and emergency access paths are documented.
- Secret values are excluded from logs and evidence artifacts.

## Completion gate

This inventory is complete only when every required component is `VERIFIED`, the tested commit and image digests match the release candidate, and all evidence references are accessible to authorized reviewers.