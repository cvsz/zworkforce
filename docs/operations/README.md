# Operations Documentation

This directory contains production operations controls, runbooks, and readiness gates for `z-platform`.

## Primary production document

- [Production master document](production-master.md)

## Runbooks and reviews

- [Local Compose operations](local-compose.md)
- [Cloudflare Access service policies](cloudflare-access.md)
- [GitHub App token format readiness](github-app-token-format.md)
- [Observability and health](observability.md)
- [Backup and restore runbook](backups.md)
- [Incident runbook](incident-runbook.md)
- [Staging readiness review](staging-readiness.md)
- [Phase 6 decisions](phase-6-decisions.md)
- [Phase 6 operator input register](phase-6-operator-inputs.md)
- [Phase 6 verification commands](phase-6-verification-commands.md)
- [GitHub Environments operations guide](github-environments.md)

Production traffic remains blocked until the production master document and staging readiness review are satisfied by the operator.
