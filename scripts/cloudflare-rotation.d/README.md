# Cloudflare rotation hooks

`rotate-cloudflare-secrets.sh` invokes executable `*.sh` files in this
directory only after the timer is due and `ROTATION_APPROVED=YES` is present.
Hooks receive the operator environment path as `$1`, receive
`ROTATION_ENV_FILE` and `ROTATION_OUT_DIR`, and must never print credential
values.

`10-account-api-token.sh` implements the Cloudflare account-token roll API.
It requires an independent mode-0600 bootstrap file containing
`CLOUDFLARE_ROTATION_BOOTSTRAP_TOKEN=...` at
`ROTATION_BOOTSTRAP_ENV_FILE`. It verifies the old runtime token and the
bootstrap token, rolls the runtime token through Cloudflare's official API,
verifies the replacement and tunnel access, then atomically updates
`CLOUDFLARE_API_TOKEN` in the operator file.

The bootstrap token must not be the same token as `CLOUDFLARE_API_TOKEN`.
Keep it outside the repository and outside the runtime environment whenever
possible. Do not revoke the bootstrap token until a replacement bootstrap
credential and recovery procedure have been verified.

Cloudflare tunnel-token rotation is separate from account API-token rotation.
Use Cloudflare's supported tunnel-token rotation procedure, update every
connector replica, restart them, verify the tunnel and public routes, and only
then revoke the old token. Do not add an unreviewed dashboard automation hook.
