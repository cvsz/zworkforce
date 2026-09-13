# zNeonDrive — zneon.zeaz.dev

Cloudflare publishes zNeonDrive through the existing tunnel.

- Public hostname: zneon.zeaz.dev
- Dedicated loopback origin: http://127.0.0.1:18085
- Terraform output: zneon_url

Port 18085 is reserved for zNeonDrive so it does not collide with existing ZEAZ One services on 18081, 18083, or 18084.

The origin must be healthy on host loopback before the public route is considered ready. Keep full tunnel configuration management disabled until the existing remote ingress has been reconciled and the complete Terraform plan has been reviewed for unrelated changes.

Expected public checks are the site root, /healthz, and /api/healthz. Publishing this website does not by itself make the game runtime production-ready.
