# Planning & Implementation: zWorkforce Core Control Plane (`planning-implementation-zwf.md`)

**Updated:** 2026-08-18T18:30Z (auto-quad-loop)  
**Module:** `zworkforce/` Python Control Plane, DB Repository, Distributed Task Queue, and Auth Gateway  
**Parent Strategy:** [`exec-planning-master.md`](exec-planning-master.md) & [`exec-planning-zwf.md`](exec-planning-zwf.md)

---

## 1. Module Overview & Architecture

`zworkforce` provides the production-grade control plane for multi-tenant AI workforce orchestration:

```mermaid
graph TD
    subgraph "Core Ingestion & Auth"
        API["FastAPI / HTTP & WebSocket Gateway (:9569)"]
        AUTH["Bearer Token / Scope / HMAC Signature Verifier"]
        GOV["Governance & Immutable Audit Ledger"]
    end

    subgraph "Execution & Queue Plane"
        QUEUE["Distributed Transactional Queue (SQLite / PostgreSQL)"]
        DOOM_GUARD["Doom Loop Cycle Detector (Signature Tracking)"]
        OUTBOX["Reliable Webhook Outbox Worker (X-Delivery-ID)"]
        ENGINE["Execution Engine & Tool Dispatcher"]
    end

    subgraph "Tooling & Connectors"
        TOOLS["Standard Tools (File, Shell, Command)"]
        CONNECTORS["Omnichannel Connectors (Shopee, TikTok, Meta)"]
        MCP_SERVER["MCP 2026-07-28 Stateless Endpoint (/mcp)"]
        ACP_SERVER["Agent Client Protocol Endpoint (/acp)"]
    end

    API --> AUTH
    AUTH --> GOV
    API --> QUEUE
    QUEUE --> DOOM_GUARD
    DOOM_GUARD --> ENGINE
    ENGINE --> TOOLS
    ENGINE --> CONNECTORS
    ENGINE --> OUTBOX
    API --> MCP_SERVER
    API --> ACP_SERVER
```

---

## 2. Completed Implementation Milestones

- [x] **Durable Multi-Tenant Database Repository**:
  - Schema evolution with PostgreSQL session advisory locks and SQLite fallback (`zworkforce/db.py`, `zworkforce/db_migrations.py`).
  - Immutable cryptographic hash chain for audit events (`zworkforce/db_governance.py`).
- [x] **Automatic Doom-Loop Detection Engine (R8.2)**:
  - Tracks sorted tool call signatures and consecutive failure counters in `zworkforce/engine.py`.
  - Configurable thresholds (`doom_loop_max_identical_calls`, `doom_loop_max_consecutive_failures`) in `zworkforce/config.py`.
- [x] **Omnichannel Social & Shop Connectors**:
  - Built `zworkforce/connectors.py` supporting Shopee Open Platform v2, TikTok Shop Seller API, and Facebook Commerce.
  - Implemented HMAC-SHA256 signature verification and fail-closed approval governance.
- [x] **Slash Command Interactive Navigation (SW2/SW11)**:
  - Interactive popup autocomplete menu and contextual documentation hints in web static frontend (`index.html`, `app.js`, `styles.css`).
- [x] **Standalone Test Runner Import Fix (PR #110)**:
  - Added `try/except ImportError` fallback for `tests.common` import in `tests/test_connectors.py`.
  - Enables canonical `PYTHONPATH=. python3 -m unittest tests/test_connectors.py -v` to pass per `AGENTS.md`.
- [x] **OTLP Telemetry & Multi-Sink Trace Export (Phase 3)**:
  - Built `zworkforce/telemetry.py` with OpenTelemetry JSON exporter, sensitive attribute redaction, and token counter attribution.
  - Test suite in `tests/test_v3_telemetry_handoff.py`.
- [x] **Typed Agent Handoff & Guardrail Protocol (Phase 4)**:
  - Built `zworkforce/agent_handoff.py` with typed handoff contracts, self-delegation guards, and context token budgets.
  - Integrated into `zworkforce/engine.py` delegation loop.
- [x] **Secure MCP Reverse Tunnel Client Gateway (Phase 1)**:
  - Built `zworkforce/tunnel.py` with `McpTunnelManager` supporting client registration, encrypted tunnel heartbeats, and timeout fencing.
  - Test suite in `tests/test_v3_tunnel.py`.
- [x] **Agent Client Protocol (ACP) Multi-IDE Integration (Phase 2)**:
  - Implemented `zworkforce/acp.py` handling JSON-RPC operations (`initialize`, `authenticate`, `newSession`, `loadSession`, `prompt`, `cancel`, `requestPermission`).
  - Unit tests in `tests/test_acp.py`.

---

## 3. Active & Upcoming Implementation Workstreams

*(All Phases 1 through 4 for ZWF Control Plane Core are now implemented and verified).*

---

## 4. Quality & Verification Gates

```bash
# 1. Bytecode Compilation & Unit Tests
python3 -m compileall -q zworkforce tests
PYTHONPATH=. python3 -m unittest discover -s tests -v

# 2. System Health Doctor
zworkforce doctor

# 3. PostgreSQL Concurrency & Regression
PYTHONPATH=. python3 -m unittest tests/test_v3_postgres.py -v
```
