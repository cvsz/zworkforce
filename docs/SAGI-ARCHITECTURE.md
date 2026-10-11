# SAGI — Superintelligence-oriented Agent Architecture

**Status:** Experimental bounded-planning module; not artificial superintelligence, AGI, autonomous tool execution, or production-ready.

## Goal

Extend the existing ZLoop orchestration design using validated hierarchical plans and independent evidence loops without replacing any zWorkforce production authority. Continue the design in [ZEAZ AGI Blueprint PR #267](https://github.com/cvsz/zworkforce/pull/267) and [ZLoop](ZLOOP-INTEGRATION.md).

## First implemented slice

`zworkforce/sagi_planning.py` is a **pure Python validator** for proposed plans. It enforces tenant/actor identity, bounded step count, strict topological dependency order, bounded fan-out/depth, finite cost estimates and deterministic SHA-256 plan digests. It provides `requires_approval` as a *signal*, not authorization. No API, model call, database, scheduler, tool execution or migration is introduced.

The term SAGI describes a research and engineering direction, not a demonstrated intelligence capability.

## Integration constraints

1. Parse LLM planning responses into `ProposedStep` through a separate schema-validation boundary; untrusted models cannot invoke execution directly.
2. Bind the digest to the canonical durable approval decision with actor, tenant, action, target, expiry and idempotency key. A digest alone is not a signature or authorization.
3. Submit approved work exclusively via the existing zWorkforce queue and scoped tool grant authority.
4. Independently verify outcomes; `INCONCLUSIVE` must yield handoff. Never allow the executor to self-certify.
5. Charge actual provider/model costs to the canonical ledger; estimates are not actual budget debits.
6. Keep limits inherited, bounded and immutable for child agents; detect stalled loops.
7. Start disabled, add policy and approval adapters, recovery tests, integration tests and release evidence before rollout.

## Validation

Run `PYTHONPATH=. python3 -m unittest tests.test_sagi_planning -v` and all repository-required checks. This module is not wired into production. No live infrastructure or model claims should be inferred.
