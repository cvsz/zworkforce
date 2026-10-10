# SAGI Computer Use isolated-worker deployment gate

Status: deployment specification only; not a deployed network sandbox.

Use an ephemeral isolated Linux worker with the browser process running
without root, host network, privileged mode or any host Docker socket mount.
Implement egress through an operator-controlled authenticated filtering proxy,
with deny-all outside that proxy in the host/container network firewall.
Prohibit DNS bypass, localhost, RFC1918, RFC4193, link-local and cloud metadata
addresses. Revalidate every DNS resolution/redirect at the enforcement proxy.

Required admission checks before launching:
- A canonical tenant-bound, valid and nonrevoked session.
- A fresh screenshot/DOM state from the trusted worker.
- A reviewed, durable, single-consumption action approval bound to exact plan,
  session, actor, selector/action/target and screen version.
- Separate approval reviewer and execution actor where required.
- A running immutable-image, nonroot, read-only, seccomp-protected worker
  with CPU/memory/pid/time limits, bounded stdout and audit correlation.
- Emergency stop propagation to cancel active browser sessions.
- A secure screenshot storage/retention and redaction policy.

## Live E2E

Execute in the **real isolated worker**, not the host:

```bash
python -m playwright install chromium
export SAGI_BROWSER_LIVE_ORIGIN=https://your-approved-staging.example
export SAGI_BROWSER_LIVE_URL=https://your-approved-staging.example/
export SAGI_BROWSER_EGRESS_ISOLATED=1
PYTHONPATH=. python -m unittest tests.test_sagi_browser_live -v
```

The environment marker alone is **not** proof of isolation. Record a separate
network egress test, browser process metadata, firewall policies, sandbox/image
digest and negative attempts to reach private and metadata addresses.

This smoke test verifies screenshot rendering from a live Chromium session.
It does not establish full computer-use action correctness, egress isolation
or production readiness. Never run live tests with real customer credentials.
