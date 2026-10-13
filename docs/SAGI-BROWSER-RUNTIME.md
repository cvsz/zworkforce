# SAGI Browser Runtime — Read-only Experimental Slice

An opt-in browser observation adapter is provided by `zworkforce/sagi_browser_runtime.py`. It requires explicit externally supplied permission and an exact HTTPS origin allowlist. It launches an ephemeral Playwright Chromium context, blocks downloads and service workers, restricts requests to allowed HTTPS origins, and returns screenshot bytes. It is not wired into the API, scheduler, ZLoop dispatcher, or control panel.

**Not production safe by itself:** browser request interception does not prevent DNS rebinding, malicious infrastructure, or guarantee egress isolation. Deploy only inside an operator-controlled network-isolated sandbox with DNS/IP egress enforcement, time limits, CPU/memory caps, and disposable storage. No credential injection or host desktop mounts.

Interactive actions (click/type/scroll/key) deliberately fail closed until canonical durable grants, screen freshness proof, approvals, replay resistance and independent audit are integrated. Do not store raw screenshots without retention and redaction controls.

Test with `PYTHONPATH=. python3 -m unittest tests.test_sagi_browser_runtime -v`. Full repository required checks must also pass before merging.
