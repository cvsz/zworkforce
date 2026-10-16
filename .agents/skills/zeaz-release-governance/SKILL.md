---
name: zeaz-release-governance
description: Configure role-based GitHub review and merge actors without embedding ZEAZDEV identities in universal installers. Use for governed PR review, account switching, and release checks.
---

# Configurable GitHub Release Governance

The universal profile must not contain hardcoded GitHub usernames, credentials, or an implicit authorization to approve/merge. Authentication is local to the executor or delegated to scoped GitHub App installations.

## Profiles

- `personal`: use a user's own identity for development and PR creation; request review from another eligible person if independent approval is required.
- `organization`: resolve reviewer team, release actor, repository scope, and permissions from tenant policy.
- `zeazdev-internal`: an administrator may configure reviewer `policedbc` and merger `cvsz` explicitly. This profile must not ship active in a third-party installation.

## Local gh CLI adapter

Before switching identity, ensure expected accounts exist and are authenticated:

```bash
gh auth status
gh auth switch -u "$GITHUB_REVIEWER"
test "$(gh api user --jq .login)" = "$GITHUB_REVIEWER"
```

Review is conditional on verified repository permission and true reviewer independence. Never approve your own PR or use alternate accounts to manufacture an independent review.

Then switch to the configured merger identity:

```bash
gh auth switch -u "$GITHUB_MERGER"
test "$(gh api user --jq .login)" = "$GITHUB_MERGER"
```

Recheck PR state, requested reviews, exact-head required checks, mergeability, and branch rules immediately before merge. An approved review is not a standing authorization for deployment. Abort on any unknown or failing gate. Prefer a GitHub App with minimum-scoped short-lived tokens for server-side automation.

## Safety

- No account login, token transmission, review approval, merge, or deployment happens merely by invoking this skill.
- Never store OAuth tokens or private keys in job metadata, source control, or the browser.
- GitHub's branch rules and review restrictions are authoritative; zWorkforce gates add restrictions but never bypass them.
- Changes to reviewer/merger configuration must be tenant-authorized and audited.
