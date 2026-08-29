# Z Platform Cloudflare Terraform Python Installer

Safety-focused installer for the Cloudflare Terraform routing stack.

## Features

- validates Cloudflare token, account ID, zone ID, and tunnel UUID;
- checks out `feat/cloudflare-terraform-stack` when needed;
- never writes the API token into `terraform.tfvars`;
- checks for an existing DNS record before planning;
- requires explicit `--import-existing` for an existing record;
- rejects plans containing delete or replace actions;
- requires explicit `--apply` to mutate Cloudflare;
- excludes secrets, state, and plan files from Git.

## Run

```bash
unzip z-platform-cloudflare-py-installer.zip
cd z-platform-cloudflare-py-installer
chmod 750 install_cloudflare_terraform.py

./install_cloudflare_terraform.py \
  --repo ~/z-platform \
  --env-file ~/z-platform/.env.cloudflare \
  --import-existing
```

Review the plan:

```bash
terraform \
  -chdir=~/z-platform/infrastructure/terraform/cloudflare \
  show -no-color tfplan
```

Apply only after review:

```bash
./install_cloudflare_terraform.py \
  --repo ~/z-platform \
  --env-file ~/z-platform/.env.cloudflare \
  --import-existing \
  --apply
```
