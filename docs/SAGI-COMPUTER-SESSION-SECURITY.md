# SAGI Computer Use — Session Security Preflight

This experimental module adds a fail-closed permission *preflight*, not an execution authorization, to the stacked SAGI Computer Use feature. It requires an operator-authorized, unexpired, non-revoked session, checks an emergency-stop callback, and requires an exact unconsumed, unexpired, tenant/actor/session/plan/request-bound approval snapshot for proposed mutations.

It deliberately does **not** mutate or consume the approval. A caller must not treat a positive preflight as sufficient to perform click/type/scroll/key actions. Production execution requires atomic approval consumption with compare-and-set, fenced leases, fresh screenshot verification and audit persistence, plus network-isolated disposable browser workers and real emergency-stop propagation.

Do not connect this to public API or production execution until these missing boundaries and their concurrency/replay tests are implemented and verified. Keep feature disabled by default. See `docs/SAGI-BROWSER-RUNTIME.md` and `docs/SAGI-COMPUTER-USE.md`.
