# SAGI to ZLoop Plan Binding

Status: experimental, non-executing integration slice stacked on PR #269.

`bind_plan_to_loop` validates identity, lifecycle and remaining estimated budget. It returns immutable metadata only, not an approval or execution capability.

Next work: canonical repository compare-and-set, recomputed digests, durable approvals bound to exact action and digest, transactional queue dispatch, canonical actual-cost ledger, negative security and recovery tests. Do not merge or deploy without required checks and independent review.
