# Master Plan: 24/7 AI Trading Desk

## 1. Objective

Extend the existing zWorkforce trading-related components into a
governed, observable, paper-first AI Trading Desk.

The system separates:
- Deterministic market calculations and order validation.
- Typed AI judgments and confidence calibration.
- Strategy policy and position sizing.
- Execution simulation and outcome accounting.
- Human approval for sensitive or irreversible operations.

Default configuration:
- execution_mode: paper
- live_trading_enabled: false
- withdrawals: unsupported
- private_key_access: prohibited for AI agents

## 2. Existing Components

- packages/wall-street/
  Market intelligence UI and public market feeds.
- packages/ztrader/zeaz-intelligence/
  Token intelligence, scoring, and security-risk signals.
- infrastructure/terraform/cloudflare/zksato.tf
  zkSato infrastructure declarations; not proof of runtime readiness.
- services/ai-gateway/
  Existing model routing and server-side credential boundary.
- zWorkforce control plane
  Governed agents, policies, durable workflows, audit, and observability.

Do not duplicate existing capabilities without first verifying their
interfaces, tests, and runtime ownership.

## 3. Target Architecture

Market Adapters
  -> Validated Market Events
  -> Deterministic State Engine
  -> Strategy Candidate Filters
  -> Typed Decision Judge
  -> Deterministic Policy
  -> Risk Engine
  -> Paper Broker
  -> Durable Ledger and Outcome Evaluator

Every decision must carry a correlation ID, market identifier,
strategy version, state timestamp, model version, and policy version.

## 4. Strategy Interfaces

Gambler:
- Classify market regime and setup quality.
- Evaluate directional pressure and execution quality.

House:
- Evaluate range state, toxic flow, and quoting suitability.
- Keep reservation price, spread, inventory, and quote size in code.

Spy:
- Evaluate wallet behavior and consistency.
- Apply deterministic contract and liquidity vetoes first.
- Never mirror an unverified or rejected candidate.

Strategies must share common state, policy, risk, and execution
interfaces without sharing implicit execution authority.

## 5. Typed Decision Contract

- Use explicit schemas and enumerated outputs.
- Give every Choice an explicit "other" or "unknown" option.
- Preserve null and unavailable data as unknown.
- Keep arithmetic, thresholds, position sizing, and final authorization
  in deterministic code.
- Run independent questions concurrently where the provider supports it.
- Pin and record the exact model version.
- Reject malformed, expired, or schema-invalid responses.
- If the judge is unavailable, fail closed.

## 6. Risk Engine

Mandatory checks before every simulated order:
- Maximum per-market and aggregate exposure.
- Daily loss and drawdown limits.
- Leverage and inventory limits.
- Market-data freshness and decision deadline.
- Strategy range and liquidity guards.
- Fees, slippage, gas, and expected-edge economics.
- Model/policy version compatibility.
- Idempotency and duplicate-order protection.

No model output may override a risk veto.

## 7. Execution Modes

Shadow:
- Record decisions and hypothetical actions only.
- Never create broker orders.

Paper:
- Simulate fills, fees, slippage, partial fills, and rejection cases.
- Persist positions, cash, orders, and realized/unrealized PnL.

Live:
- Out of scope for this implementation.
- Must remain disabled unless separately authorized and reviewed.

## 8. Reliability and Observability

- Enforce deadlines; never execute stale decisions.
- Bound retries and use backoff for transient provider failures.
- Do not retry permanent schema or malformed-question errors.
- On stale data or repeated failures, stop opening positions.
- Reconcile persisted orders and positions after restart.
- Maintain an operator kill switch and durable audit trail.
- Report calibration, Brier score, realized PnL after costs,
  risk vetoes, provider latency, and execution discrepancies.

## 9. Security and Governance

- Keep provider credentials server-side in approved secret stores.
- Agents never receive exchange private keys or withdrawal authority.
- Separate judgment, policy, risk, and broker permissions.
- Enforce tenant isolation, scoped authorization, and audit correlation.
- Paper Trading endpoints require service authentication plus a unique tenant-bound token; `X-Tenant-ID` alone is never authentication.
- Treat external market data and token metadata as untrusted input.
- Require human approval for sensitive policy changes.

## 10. Acceptance Gates

1. Existing tests and interfaces remain compatible.
2. Unit and integration tests cover policies, risk vetoes, and broker
   accounting.
3. Security tests cover authorization, stale data, malformed outputs,
   duplicate orders, and secret leakage.
4. Shadow mode produces reproducible, auditable decisions.
5. Paper mode survives restart and reconciles its ledger.
6. Calibration and economics are measured on venue-specific data.
7. Live execution remains disabled throughout this plan.

Passing unit tests alone does not establish production readiness.

## 11. Implementation Sequence

Phase 0: Inventory existing code, contracts, tests, and ownership.
Phase 1: Define schemas and deterministic state calculations.
Phase 2: Implement judge/provider adapters and failure handling.
Phase 3: Integrate policy, risk vetoes, and paper broker.
Phase 4: Add durable outcomes, calibration, and daily reports.
Phase 5: Run shadow and paper validation; document residual risks.

Each phase requires a reviewed diff, test evidence, and explicit
acceptance criteria before proceeding to the next phase.
