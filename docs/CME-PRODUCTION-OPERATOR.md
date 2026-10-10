# CMe Production Operator Contract

zWorkforce owns the external `zeaz.dev` edge and production evidence for CMe. The CMe repository owns the application, database behavior and application verification commands.

## Edge contract

- Public host: `cme.zeaz.dev`
- Managed DNS: existing `cloudflare_dns_record.cmeerp` in `infrastructure/terraform/cloudflare/main.tf`; do not duplicate its Terraform state address
- Cloudflare Access protection: `infrastructure/terraform/cloudflare/cme.tf`
- Tunnel ingress: `deploy/cloudflare/tunnel-ingress.yml`
- Reviewed loopback origin: `http://127.0.0.1:8001`

Do not place CMe database credentials, session secrets or Cloudflare credentials in repository files.

## Change procedure

1. Freeze the exact CMe commit/image digest to deploy.
2. Run Terraform plan from the Cloudflare stack with operator credentials and retain the plan artifact.
3. Obtain explicit production-change approval for the saved Terraform plan/digest before applying Cloudflare mutations.
4. Apply exactly the approved saved Terraform plan, retain the apply result, and verify the Access application/policies are present. Never run an unreviewed fresh plan as the apply step.
5. Deploy the exact CMe artifact to the reviewed loopback origin.
6. Expose immutable deployed commit/image identity from a runtime/deployment metadata endpoint that returns JSON `{\"release\": \"<digest-or-sha>\"}` and is bound to the serving deployment, not an operator-written file.
7. Export the machine-verification Access credentials from the protected operator secret store as `ZWORKFORCE_ACCESS_ID` and `ZWORKFORCE_ACCESS_TOKEN`; never write them to repository files or evidence.
8. Run with a new output path for every attempt:
   `python3 scripts/verify-cme-production.py --expected-release <digest-or-sha> --runtime-release-url <https-runtime-metadata-url> --operator <operator-id> --approval-reference <approval-id> --terraform-plan-reference <plan-sha-or-uri> --terraform-apply-reference <apply-run-id> --deployment-reference <deployment-run-id> --alert-receipt <alert-delivery-id> --output <immutable-evidence.json>`
9. Retain the JSON evidence with operator identity, Terraform plan/apply reference, deployment reference and alert receipt.
10. Exercise rollback to the prior immutable artifact, repeat verification, measure recovery time, then restore the intended artifact and verify again.

## Required PASS evidence

A CMe production GO requires current evidence for exact artifact identity, DNS resolution, trusted TLS, health, readiness, PostgreSQL restore/rollback with measured RPO/RTO, workload-derived load thresholds, production monitoring/alert delivery, and runtime credential/secret rotation.

Repository configuration is not proof that Cloudflare or production infrastructure has been applied. Until an approved operator apply and post-action verification are retained, those gates remain pending external evidence.
