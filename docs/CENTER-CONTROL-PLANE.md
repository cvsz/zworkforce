# ZEAZ Center Control Plane

## Purpose

zWorkforce is the repository-level orchestration center for the ZEAZ ecosystem.
It combines governed AI workforce execution with operator views for GitHub
repositories, Cloudflare-owned edge resources, release evidence, and generated
project foundations.

This document defines the contract. It does **not** claim that every dashboard
surface, GitHub mutation, Cloudflare route, or generator action is already
implemented or externally provisioned.

## Control-plane boundaries

zWorkforce may aggregate inventory from many repositories, but ownership remains
explicit:

- application source stays owned by the application repository;
- Cloudflare resources are mutable here only when Terraform or another
  repository-owned declaration explicitly assigns edge ownership to
  `cvsz/zworkforce`;
- a hostname in the `zeaz.dev` zone does not by itself grant zWorkforce
  mutation authority;
- GitHub repository administration requires explicit repository permission;
- production deployment, DNS/Tunnel apply, secret rotation, destructive
  infrastructure changes, and release promotion remain approval-gated.

The machine-readable inventory contract is
[`schemas/center-control-plane.schema.json`](../schemas/center-control-plane.schema.json).
A non-secret example is
[`examples/center-control-plane.example.json`](../examples/center-control-plane.example.json).

## Operator dashboard

The primary browser surface is
[`apps/agent-control-panel`](../apps/agent-control-panel/).

Required navigation model:

```text
ZEAZ CENTER CONTROL PLANE
├── Overview
├── Repositories
│   ├── All
│   ├── Production
│   ├── Needs Update
│   └── Archived
├── Generator
│   ├── New Repository
│   ├── Profiles
│   └── Templates
├── GitHub
│   ├── Pull Requests
│   ├── Actions / CI
│   ├── Security
│   ├── Branch / Ruleset Status
│   └── Releases
├── Cloudflare
│   ├── Hostnames
│   ├── Ownership
│   ├── Tunnel / Origin Mapping
│   ├── Access Policy Status
│   └── Terraform Plan Evidence
├── Production
│   ├── Readiness Gates
│   ├── Deployments
│   ├── Rollback
│   ├── Backup / Restore
│   └── DR
├── AI Workforce
│   ├── Agents
│   ├── Skills
│   ├── Tasks
│   └── Automations
└── Audit Log
```

Browser code is an operator view, not a privileged infrastructure client.
Provider credentials, GitHub installation secrets, Cloudflare API tokens,
database credentials, and signing material stay server-side.

## Repository generator

The generator consumes an approved project profile and a repository-foundation
source such as `cvsz/ztemplate`.

A generated project request should capture:

- repository owner/name/visibility;
- project description and license;
- profile: minimal, API, web, full-stack, SaaS, worker, agent, platform;
- runtime/framework/package manager;
- database/cache/queue;
- dashboard choice;
- Docker/Kubernetes/Cloudflare requirements;
- CI/security baseline;
- CODEOWNERS and support policy;
- observability/recovery expectations.

Generation is two-phase:

1. **Preview** — render intended files/settings without mutation.
2. **Apply** — create repository/branch/files only after authorization.

Repository generation must never imply application production readiness.

## zTemplate relationship

`cvsz/ztemplate` is the repository-foundation source for new repositories and
safe baseline synchronization.

Existing repositories must use audit-first synchronization:

```text
inventory -> compatibility review -> focused branch -> minimal diff
          -> exact-head CI/security checks -> review -> merge
```

Do not overwrite repository-specific AGENTS rules, CI matrices, deployment
workflows, infrastructure ownership, or security contacts.

## Cloudflare center view

The control plane may inventory all known `zeaz.dev` hostnames, but mutation
authority is derived from ownership declarations.

For every managed hostname record:

- hostname;
- application repository;
- edge owner repository;
- environment;
- intended origin;
- tunnel identifier/reference without secret material;
- Access requirement;
- Terraform/source path;
- desired/effective state;
- last verified evidence reference.

### Cloudflare mutation rule

A Cloudflare action is eligible for execution only when all are true:

1. the target hostname has explicit edge ownership;
2. the requested change is representable in the owning configuration;
3. a preview/plan exists;
4. unrelated destroy/change operations are absent or explicitly approved;
5. the operator authorizes the exact plan/digest;
6. post-apply verification is recorded.

Read-only inventory does not require mutation authority.

## GitHub fleet view

For each repository, the control plane should aggregate:

- exact default-branch SHA;
- open PR/issue counts;
- required-check conclusions;
- CodeQL/Dependency Review/Dependabot signals;
- branch/ruleset status when readable;
- repository-foundation baseline version/drift;
- latest release and deployment evidence;
- applicable production-readiness gates.

Preferred authentication for multi-repository automation is a least-privilege
GitHub App installation rather than a long-lived broad personal token.

## Evidence states

Use these states for each gate:

- `VERIFIED`
- `PARTIALLY VERIFIED`
- `UNVERIFIED`
- `BLOCKED`
- `NOT APPLICABLE`

Do not display an overall "production ready" result while any applicable gate
is `PARTIALLY VERIFIED`, `UNVERIFIED`, or `BLOCKED`.

## Mutation pipeline

All high-impact actions use a proposal/approval/execution flow:

```text
read current state
  -> generate preview / diff / plan
  -> policy evaluation
  -> immutable action digest
  -> explicit approval
  -> compare-and-set execution
  -> verification
  -> durable audit evidence
```

Examples requiring approval:

- create or change public Cloudflare DNS/Tunnel/Access state;
- apply Terraform;
- production deployment;
- repository security/ruleset mutation;
- credential rotation;
- release/tag publication;
- destructive branch/resource deletion.

## Dashboard implementation

The current control panel uses Next.js/React. Keep its data model independent
from a visual theme.

AdminLTE may be used as an optional visual/design adapter, but it must not become
a required runtime dependency for the control-plane API or repository generator.
The default implementation should preserve Next.js routing, server-side secret
boundaries, accessibility, responsive behavior, and testability.

## Delivery phases

### Phase 0 — contract and inventory
- machine-readable center-control registry;
- ownership and mutation boundaries;
- dashboard information architecture;
- generator contract.

### Phase 1 — read-only fleet dashboard
- GitHub repository inventory;
- Cloudflare ownership/desired-state inventory;
- CI/security/readiness summaries;
- no production mutation.

### Phase 2 — repository generator
- zTemplate profiles;
- previewable file tree/settings;
- focused repository creation flow;
- exact audit record.

### Phase 3 — approved GitHub mutations
- branch/ruleset/security setting proposals;
- pull-request creation and safe baseline sync;
- no force merge/bypass.

### Phase 4 — approved Cloudflare mutations
- Terraform-backed change preview;
- exact-plan approval;
- apply through the owning repository;
- post-apply DNS/TLS/origin verification.

### Phase 5 — integrated production operations
- deployment/release/recovery evidence;
- alerting and incident context;
- environment-specific rollback/restore controls.

Each phase requires its own implementation and evidence before being marked
complete.
