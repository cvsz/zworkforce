---
name: zeaz-release-governance
description: Verifies identity-agnostic review and release gates without hardcoded identities or protection bypass.
version: 1.0.0
---
Resolve reviewer, merger, repository allowlist, and permissions from tenant policy or operator-configured profile. Verify exact base/head SHA, full diff, required checks, security findings, branch rules, independent review, provenance, rollback, and release notes. Re-read gates before merge; stale approvals/checks do not count after head changes. Deployment is a separate authorized action. Never self-approve, impersonate reviewers, hardcode ZEAZDEV identities in universal profiles, or bypass protection.
