# CMe Production Operator Contract

zWorkforce owns the external `zeaz.dev` edge and production evidence for CMe. The CMe repository owns the application, database behavior and application verification commands.

## Edge contract

- Public host: `cme.zeaz.dev`
- Managed DNS: `infrastructure/terraform/cloudflare/cme.tf`
- Tunnel ingress: `deploy/cloudflare/tunnel-ingress.yml`
- Reviewed loopback origin: `http://127.0.0.1:8001`

Do not place CMe database credentials, session secrets or Cloudflare credentials in repository files.

## Change procedure

1. Freeze the exact CMe commit/image digest to deploy.
2. Run Terraform plan from the Cloudflare stack with operator credentials and retain the plan artifact.
3. Obtain explicit production-change approval before applying Cloudflare mutations.
4. Deploy the exact CMe artifact to the reviewed loopback origin.
5. Write the immutable deployed commit/image digest to an operator-controlled release evidence file.
6. Run:
   `python3 scripts/verify-cme-production.py --expected-release <digest-or-sha> --release-file <path> --output <evidence.json>`
7. Retain the JSON evidence with operator identity, Terraform plan/apply reference, deployment reference and alert receipt.
8. Exercise rollback to the prior immutable artifact, repeat verification, measure recovery time, then restore the intended artifact and verify again.

## Required PASS evidence

A CMe production GO requires current evidence for exact artifact identity, DNS resolution, trusted TLS, health, readiness, PostgreSQL restore/rollback with measured RPO/RTO, workload-derived load thresholds, production monitoring/alert delivery, and runtime credential/secret rotation.

Repository configuration is not proof that Cloudflare or production infrastructure has been applied. Until an approved operator apply and post-action verification are retained, those gates remain pending external evidence.
