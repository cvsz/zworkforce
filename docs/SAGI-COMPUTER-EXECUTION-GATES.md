# SAGI Computer Execution Gates — Read-only Adapter

This incremental change connects existing SAGI session preflight to the
read-only Playwright observation adapter. It intentionally rejects all
CLICK/TYPE/SCROLL/KEY requests even when a proposed plan asks for them.
It enforces exact target URL identity and calls the authoritative session
preflight before browser launch and again via the browser authorization callback.

## Invariants and remaining blockers

- This is **not** a canonical production service binding: session/approval
  sources must be backed by the real zWorkforce durable authorities.
- A callback check is **not** atomic approval consumption, screenshot freshness,
  or in-flight stop propagation.
- SQLite single-claim behavior in `sagi_atomic_approval.py` is a local reference
  and must not be used to issue approvals. Production requires canonical policy
  issuer, four-eyes checks, transactional lease fencing and audit/outbox.
- An actual network-isolated worker and outbound firewall/proxy are **not**
  provisioned by this change. Request interception is insufficient as SSRF
  protection. Block metadata/private ranges at the networking layer.
- E2E smoke in `tests/test_sagi_browser_live.py` requires a separately
  provisioned browser worker and approved staging URL. The environment flag
  does not attest to isolation.

## Verification

```bash
PYTHONPATH=. python -m unittest tests.test_sagi_computer_dispatch -v
PYTHONPATH=. python -m unittest discover -s tests -v
```

No public endpoint, feature flag enablement, privileged host mount or
production deployment is introduced.
