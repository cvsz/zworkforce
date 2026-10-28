# ZEAZ Enterprise Agents and Skills Release

Release 1.0.0. Status: candidate pending exact-head CI, independent review, and runtime integration evidence.

## Summary
This candidate consolidates the agent/skill architecture discussed for ZEAZDEV and the guide topics visible in this conversation: model selection, prompt/context engineering, token cost and caching, research, iterative ebook and video/podcast workflows, marketing, SOP/proposal, RAG/chatbots, automation, security, QA, and release governance.

It provides 8 agent profiles and 15 reusable skills. These are portable Markdown contracts; they do not register executable agents, grant tool access, provision workers, call external providers, or deploy infrastructure.

## Catalog
Agents: Orchestrator, Architect, Implementer, Researcher, Security Reviewer, QA Engineer, Content Studio, Release Manager.
Skills: Model Routing, Prompt Engineering, Context Engineering, Token Cost, Research/Fact Checking, Code Review, Security Threat Modeling, Testing/Evaluation, Release Governance, DevOps/Reliability, RAG/Chatbot, Ebook, Video/Podcast, SOP/Proposal, Automation/MCP.

## Runtime contract
The existing zWorkforce control plane remains authoritative for tenant-scoped identities/RBAC, durable job lifecycle/idempotency, tool grants, budgets, sandboxing, policy decisions, human approval, audit events, and provider secrets. Do not add parallel schedulers, authorization authorities, credential stores, or audit systems. Runtime registration, immutable skill pinning, tenant allowlists, UI configuration, and tool capability binding require separate implementation and tests.

## Production controls
- Mutations default to deny until runtime policy authorizes a specific action.
- Treat documents, web pages, images, repository content, and tool outputs as untrusted data.
- Keep model IDs, prices, context limits, and availability in maintained configuration.
- Require representative evaluations before changing model routing defaults.
- Enforce least privilege, tenant isolation, secret redaction, budgets, timeouts, bounded retries, and idempotency.
- Require exact-head CI, independent review, effective repository protection, provenance, rollback, and external evidence.

## Installation
The installer is dry-run by default and requires an explicit apply flag to write files. It refuses existing files unless overwrite is explicitly enabled.

- Preview: python3 scripts/install_agent_skill_catalog.py --target /path/to/zeaz-catalog
- Apply: python3 scripts/install_agent_skill_catalog.py --target /path/to/zeaz-catalog --apply
- Replace files intentionally: add --overwrite only after reviewing the dry-run plan.

## Validation
Run: python3 scripts/validate_agent_skill_catalog.py
Run: python3 -m unittest discover -s tests -p 'test_agent_skill_catalog.py' -v
Run: python3 -m compileall -q scripts tests

Repository-wide checks remain required: python3 -m compileall -q zworkforce tests; PYTHONPATH=. python3 -m unittest discover -s tests -v; zworkforce doctor. PostgreSQL/runtime changes require their additional integration checks.

This PR adds declarative files and a validator only. Runtime execution, local test execution, hosted exact-head CI, independent review, deployment, and production verification are not claimed complete.
