# External Staging Readiness Completion

This runbook closes every automatable item remaining in Issue #1 without treating placeholders or unverified external systems as evidence.

## Safety properties

- The workflow checks out an immutable 40-character release SHA.
- The protected manifest is supplied through the `staging` GitHub Environment secret `STAGING_READINESS_MANIFEST_JSON`.
- Optional bearer credentials are supplied through `STAGING_BEARER_TOKEN` and are never written to evidence.
- Probe evidence stores only a SHA-256 fingerprint of the endpoint origin, not the endpoint URL.
- Human-only checks require reviewer, timestamp, and a non-secret evidence reference.
- Production approval is a separate job protected by the `production` GitHub Environment.
- A prior release's evidence cannot validate a newer release SHA.

## Required staging configuration

Create these GitHub Environment values outside the repository.
Use `scripts/configure-github-environments.sh` before loading the secrets below so `staging` and `production` exist with the correct reviewer and branch policies and the populated overlay keys are synchronized into the relevant GitHub environment variables and secrets.

### Secrets

- `STAGING_READINESS_MANIFEST_JSON`: completed manifest based on `docs/operations/external-readiness-manifest.example.json`.
- `STAGING_BEARER_TOKEN`: optional bearer token for HTTPS probes.
- `STAGING_CF_ACCESS_CLIENT_ID`: optional Cloudflare Access service-token client ID for protected HTTPS probes.
- `STAGING_CF_ACCESS_CLIENT_SECRET`: optional Cloudflare Access service-token client secret for protected HTTPS probes.
- `STAGING_ALLOWED_ORIGINS`: comma-separated HTTPS origins explicitly allowed for staging probes.
- `STAGING_DECISION_RECORD_JSON`: sanitized decision record covering external identity, secret manager, managed data services, backup target class, observability platform, AI policy, and billing policy. Do not include account IDs, credentials, tax identifiers, or sensitive infrastructure identifiers.

### Variables

- `STAGING_REVIEWER`
- `INCIDENT_OWNER`
- `ESCALATION_ROUTE`
- `WATCH_WINDOW`

The `production` Environment must define `PRODUCTION_APPROVER` and retain required-reviewer protection.

## Required check IDs

The manifest must contain each check exactly once:

- `observability.dashboard`
- `observability.traces`
- `observability.alert_delivery`
- `backup.external_restore`
- `ai.streaming`
- `ai.upload`
- `ai.multi_provider`
- `ai.failover`
- `browser.bundle_scan`
- `browser.har_scan`
- `zchat.keyboard`
- `zchat.screen_reader`
- `zchat.responsive`
- `zchat.session_provider`

Use `mode: probe` only for an HTTPS endpoint whose expected response status is meaningful. Use `mode: attestation` for human QA or checks whose evidence is held in an approved external system.

## Execute staging verification

1. Select a release SHA that has current passing CI, security, SBOM, provenance, and isolated deployed-smoke evidence.
2. Complete the staging manifest with the same release SHA.
3. Store the manifest and decision record in the protected `staging` Environment.
4. Run **external-staging-readiness** with `request_production_approval=false`.
5. The workflow validates that the requested release SHA exists in `cvsz/z-platform` before it checks out the code, so an invalid or stale SHA fails closed before deployment evidence is collected.
5. Review the uploaded and attested `external-staging-evidence-<sha>` artifact.
6. Record the workflow run, artifact digest, staging reviewer, and review time in Issue #1.

A failed or incomplete probe, missing operator owner, mismatched SHA, insecure URL, missing check, or invalid attestation fails the workflow.

## Request production approval

Run the same workflow for the same immutable SHA with `request_production_approval=true`. The production job begins only after staging evidence is verified and requires approval through the protected `production` Environment.

Completion of the approval job creates and attests `production-approval-<sha>`. It records approval evidence; it does not itself enable traffic or deploy production.

## Local validation

```bash
node --test scripts/external-readiness.test.mjs
RELEASE_SHA=<full-sha> \
STAGING_REVIEWER=<reviewer> \
INCIDENT_OWNER=<owner> \
ESCALATION_ROUTE=<route> \
WATCH_WINDOW=<window> \
node scripts/external-readiness.mjs /secure/path/manifest.json
```

Never commit a completed external manifest when it contains sensitive endpoint information. Keep production and external traffic disabled until Issue #1's completion rule is satisfied for one immutable release SHA.
