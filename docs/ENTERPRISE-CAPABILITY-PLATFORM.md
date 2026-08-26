# zWorkforce Enterprise Capability Platform

**Status:** forward architecture contract  
**Scope:** `cvsz/zworkforce`  
**Release semantics:** this document defines forward capability-platform work; it does not change the current release-evidence ledger or claim external production certification.

## 1. Purpose

zWorkforce already has durable tasks and workflows, policy and approval boundaries, signed skills, MCP support, model routing, sandbox controls, artifacts, semantic memory, evaluation, FinOps, audit, and telemetry. The enterprise capability platform composes those existing primitives into one governed resource model rather than introducing a second agent stack.

The target product loop is:

```text
Discover -> Validate -> Sign -> Review -> Publish -> Approve -> Execute -> Evaluate -> Audit -> Improve
```

The unit of governance is a **capability**. A capability can be a prompt, skill, agent, MCP server, workflow, knowledge pack, evaluation pack, policy pack, or automation.

## 2. Non-goals

This architecture does not:

- clone a third-party prompt marketplace;
- replace the existing zWorkforce task, workflow, policy, approval, MCP, provider, artifact, or workspace runtimes;
- move provider or service credentials into browser clients or model context;
- allow a model to authorize its own tool use or mutations;
- automatically promote generated capabilities into production;
- claim that Temporal, OPA, Vault, SPIFFE/SPIRE, or another external control plane is deployed when it is not;
- make forward marketplace work a blocker for the current release candidate unless the release plan explicitly promotes it.

## 3. Architecture

```text
+------------------------------------------------------------------+
|                         EXPERIENCE PLANE                         |
| Web / Z.A.R.V.I.S. / CLI / API / SDK / operator surfaces        |
+-------------------------------+----------------------------------+
                                |
+-------------------------------v----------------------------------+
|                          CONTROL PLANE                           |
| identity | capability registry | policy | approval | eval | cost |
| audit | provenance | tenant governance | discovery               |
+--------------------+--------------------------+-------------------+
                     |                          |
             plan / resolve              policy decisions
                     |                          |
+--------------------v--------------------------v-------------------+
|                         EXECUTION PLANE                          |
| task/workflow runtime | agents | skills | tools | MCP | models    |
| workspace grants | process sandbox | artifacts | memory           |
+--------------------+--------------------------+-------------------+
                     |                          |
              approved effects            provider calls
                     |                          |
+--------------------v--------------------------v-------------------+
|                          EXTERNAL PLANE                          |
| GitHub / SaaS / databases / browser targets / model providers    |
+------------------------------------------------------------------+
```

The planes are logical trust boundaries. They do not require one independently deployed microservice per box. zWorkforce can retain a modular-monolith deployment where that is operationally simpler, provided the authorization and persistence boundaries remain explicit.

## 4. Mapping to existing zWorkforce primitives

| Capability-platform concern | Existing zWorkforce primitive |
| --- | --- |
| identity and tenant context | `zworkforce/identity.py`, API auth boundaries |
| signed skills | `zworkforce/skills.py`, `zworkforce/skill_registry.py` |
| policy decisions | `zworkforce/policy.py` |
| approvals and mutation authority | existing approval/action boundaries and workspace grants |
| workflow execution | `zworkforce/workflow.py`, scheduler/event infrastructure |
| model routing | `zworkforce/router.py`, `zworkforce/providers.py` |
| MCP | `zworkforce/mcp.py` |
| sandboxed local execution | `zworkforce/process_sandbox.py`, workspace tool executor |
| secrets | `zworkforce/secret_store.py` and server-side configuration |
| knowledge and retrieval | `zworkforce/rag.py`, zKnowBase integration |
| artifacts | `zworkforce/artifacts.py` and artifact APIs |
| evaluations | `zworkforce/evaluator.py`, `zworkforce/evaluation_suite.py` |
| telemetry | `zworkforce/telemetry.py`, router tracing and metrics |
| audit | durable audit records in the database layer |
| FinOps | economics/FinOps database and runtime surfaces |

The implementation rule is **compose first, extract later**. A new service is justified only when scaling, isolation, ownership, or failure-domain evidence requires it.

## 5. Universal capability kinds

The first contract recognizes:

```text
Prompt
Skill
Agent
MCPServer
Workflow
KnowledgePack
EvaluationPack
PolicyPack
Automation
```

`Skill` is the first kind integrated with the existing runtime because zWorkforce already has a signed remote skill registry. Other kinds become persisted first-class registry resources in later slices.

## 6. Enterprise manifest v1

Enterprise manifests use:

```text
apiVersion: zworkforce.ai/v1
```

The v1 envelope is intentionally additive to the current skill schema. Existing ProMeta skill manifests remain valid. An enterprise skill adds governance fields without changing the established `id`, `version`, `allowed_tools`, and `system_prompt_append` fields used by current storage and runtime code.

Example:

```json
{
  "apiVersion": "zworkforce.ai/v1",
  "kind": "Skill",
  "id": "enterprise-review",
  "version": "1.0.0",
  "metadata": {
    "owner": "platform-security",
    "visibility": "organization"
  },
  "allowed_tools": ["workspace_read"],
  "permissions": {
    "tools": ["workspace_read"],
    "scopes": ["workspace:read"],
    "secrets": []
  },
  "mutability": "read_only",
  "approval": {
    "required": false,
    "minimum_approvals": 0
  },
  "security": {
    "risk": "R1"
  },
  "network": {
    "mode": "deny",
    "allowed_hosts": []
  },
  "resources": {
    "timeout_seconds": 300,
    "memory_mb": 512,
    "cpu_millis": 500
  },
  "provenance": {
    "source": "git:owner/repo@commit",
    "digest": "sha256:<content digest>"
  },
  "evaluation": {
    "suite": "enterprise-review-v1",
    "minimum_score": 0.9
  }
}
```

### 6.1 Required security properties

The validator enforces the following for enterprise envelopes:

- fixed `apiVersion` and recognized capability kind;
- DNS-like capability ID and bounded version value;
- explicit owner and visibility;
- duplicate-free tool, scope, and secret lists;
- exact agreement between legacy `allowed_tools` and `permissions.tools` for enterprise skills;
- explicit mutability;
- explicit risk tier `R0` through `R5`;
- approval for every mutating capability;
- approval for every `R3` through `R5` capability;
- bounded approval quorum;
- network mode of `deny`, exact-host `allowlist`, or `platform`;
- no wildcard network hosts;
- bounded timeout, memory, and CPU authority;
- provenance source plus lowercase SHA-256 digest;
- bounded optional evaluation threshold.

The manifest describes requested authority. Runtime policy remains authoritative. A manifest cannot grant itself permissions merely by declaring them.

## 7. Risk model

| Tier | Typical behavior | Default posture |
| --- | --- | --- |
| R0 | local deterministic read/transform | automatic when policy allows |
| R1 | bounded read-only retrieval | automatic when policy allows |
| R2 | externally visible draft or bounded preparation | policy-controlled |
| R3 | send, publish, submit, deploy, or other mutation | approval required |
| R4 | payment, production merge, deletion, privilege-sensitive action | strong approval required |
| R5 | destructive security/admin or high-blast-radius action | multi-party policy and dedicated controls |

The risk label never replaces deterministic checks at the tool boundary.

## 8. Upgrade safety

Signed code is not automatically safe code. An update can be correctly signed and still request more authority than the installed version.

For enterprise-to-enterprise remote skill updates, zWorkforce therefore treats these changes as **authority expansion** and rejects them through the automatic update path:

- adding tools;
- adding authorization scopes;
- adding secret access;
- changing read-only to mutating;
- removing approval requirements;
- reducing approval quorum;
- silently lowering the declared risk tier;
- adding network access;
- expanding a network allowlist;
- increasing timeout, memory, or CPU authority;
- changing capability identity, kind, or established owner.

Authority-reducing updates can proceed through the signed registry path. Authority expansion requires a future explicit reviewed promotion path with policy and approval evidence.

Legacy skill updates retain their existing behavior in this slice to preserve backward compatibility. Migration of legacy packages to the enterprise envelope must be deliberate and tested.

## 9. Registry lifecycle

Manifest validation and registry lifecycle are intentionally separate.

Target registry states:

```text
DRAFT
  -> VALIDATED
  -> SECURITY_SCANNED
  -> EVALUATED
  -> REVIEWED
  -> SIGNED
  -> PUBLISHED
  -> APPROVED
  -> PRODUCTION
  -> DEPRECATED
  -> REVOKED
```

A package must not be considered production-safe merely because its manifest says so. Lifecycle state is durable registry state controlled by zWorkforce policy, review, evaluation, signatures, and audit evidence.

## 10. Execution invariant

The core authorization invariant is:

> The model proposes. Policy and approval authorize. A deterministic executor performs the effect.

Every mutating execution should eventually correlate at least:

```text
tenant_id
actor_id
execution_id
action_id
idempotency_key
capability_id
capability_version
tool_id
target_resource
policy_decision_id
approval_id
trace_id
```

The exact field locations may differ across current subsystems; future slices should normalize correlation without creating a duplicate task runtime.

## 11. MCP boundary

MCP remains behind the zWorkforce control plane. Agents do not gain unrestricted MCP authority from discovery alone.

The target MCP path is:

```text
Agent -> zWorkforce MCP boundary -> schema validation -> tenant/policy check
      -> approval when required -> bounded tool call -> audit/telemetry
```

MCP server registration, server trust, tool discovery, and tool execution are distinct operations and should have distinct policy decisions.

## 12. Secrets

Capabilities declare **secret references**, never secret values. Provider and connector credentials remain server-side.

The target path is:

```text
execution identity -> policy -> secret broker/store -> scoped credential -> tool/provider
```

Long-lived provider credentials must not be serialized into browser payloads, capability manifests, model prompts, traces, or audit details.

## 13. Sandbox and network policy

Untrusted or marketplace-origin execution should be placed behind the strongest practical sandbox boundary. The existing process sandbox remains the immediate implementation primitive. Future isolation tiers can introduce container, gVisor/Kata, or microVM boundaries based on threat model and operational evidence.

Network authority is explicit in the capability envelope. `platform` means the capability may call only platform-mediated network tools whose own policy and SSRF controls remain authoritative; it does not mean unrestricted raw egress.

## 14. Evaluation and certification

Target release flow for a capability:

```text
candidate
  -> schema and static validation
  -> security/adversarial evaluation
  -> functional evaluation
  -> signed artifact
  -> reviewed publication
  -> tenant/org approval
  -> shadow/canary where applicable
  -> production
```

Useful metrics include task success, tool success, policy denials, approval rate, retries, latency, token use, cost per successful task, sandbox failures, and capability-version regressions.

## 15. Multi-tenant invariants

Every future persistent capability record must be tenant-scoped unless it is an explicitly global system artifact. Tenant context must be enforced at API, persistence, policy, retrieval, artifact, and execution boundaries. Capability discovery must never surface resources a subject cannot subsequently read or execute.

## 16. Supply-chain target

The long-term trust chain is:

```text
source commit
  -> controlled build/package
  -> manifest + content digest
  -> security/evaluation evidence
  -> signature/provenance
  -> registry lifecycle approval
  -> runtime admission
  -> execution audit
```

The existing HMAC skill signature mechanism remains compatible in this slice. Publisher identity, asymmetric signatures, SBOM/provenance binding, revocation, and organization trust roots are later registry-hardening work.

## 17. Implementation slices

The executable plan is maintained in `planning/exec-planning-capability-platform.md`.

The first slice implemented with this document provides:

- `zworkforce/capabilities.py` universal v1 manifest validation;
- stable capability fingerprinting;
- authority-diff enforcement for enterprise updates;
- enterprise skill validation integrated into the existing signing path;
- fail-closed enterprise-to-enterprise remote skill updates;
- regression tests proving legacy compatibility and authority-expansion rejection.

It intentionally does not create a second database registry, second workflow runtime, or second approval system.

## 18. Enterprise readiness gates

The broader platform must not be described as fully certified solely because the manifest contract exists. Before a universal registry is promoted to production, evidence should cover:

- tenant isolation and cross-tenant negative tests;
- lifecycle transition authorization;
- signature/provenance verification and revocation;
- privilege-expansion review path;
- policy and approval binding;
- replay/idempotency behavior for mutating execution;
- MCP trust-boundary tests;
- prompt-injection and tool-confusion tests;
- sandbox and egress enforcement;
- secret-leakage tests;
- evaluation regression gates;
- audit completeness and trace correlation;
- load, recovery, backup/restore, and rollback evidence;
- release SBOM/provenance evidence where applicable.

Until those gates are evidenced, this document is the architecture and implementation contract, not a claim of external production certification.
