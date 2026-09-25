# ZeaZDev Work Context & Domain Infrastructure

## Purpose

This is the canonical ZeaZDev ecosystem context for zWorkforce agents, operators, developers, and automation workflows. It defines the relationship between the ZeaZDev software ecosystem, the `zeaz.dev` domain namespace, Cloudflare edge infrastructure, Terraform infrastructure-as-code, and zWorkforce.

## About the Owner

**PHIPHAT PHOEMSUK** is the founder and CEO of ZeaZDev and a Senior Staff Software Engineer / System Architect focused on production-grade distributed systems, platform engineering, automation, AI-assisted engineering, and cost-efficient infrastructure.

Engineering principle:

> Code is a liability — less code, fewer moving parts, stronger architecture, higher reliability.

The preferred approach is secure-by-default, reproducible, observable, recoverable, infrastructure-as-code driven, local-first/self-hosted where practical, and optimized for long-term maintainability.

## ZeaZDev Ecosystem

ZeaZDev is a connected technology ecosystem containing applications, platforms, AI systems, automation, infrastructure, and business products.

zWorkforce is the AI/agent/automation engine and governed control plane. It provides durable tasks, workflows, scheduling, events, agents, provider/model routing, policy-as-code, approvals, MCP, memory, artifacts, FinOps, observability, and operational controls.

Architecture:

```text
Infrastructure
    ↓
Platform / Control Plane
    ↓
ZWorkforce AI Workforce / Automation
    ↓
Application Services
    ↓
Products / User Interfaces
```

Repository boundaries remain explicit. zWorkforce is the orchestration/AI engine; individual product repositories remain responsible for product-specific implementation and domain concerns.

## Primary Domain: zeaz.dev

`zeaz.dev` is the primary domain namespace for the ZeaZDev ecosystem.

All production `*.zeaz.dev` hostnames are managed infrastructure resources and must be traceable to their intended service, environment, origin, security boundary, and deployment configuration.

Known namespaces include:

```text
zeaz.dev
*.zeaz.dev

app.zeaz.dev
api.zeaz.dev
admin.zeaz.dev
account.zeaz.dev
auth.zeaz.dev
pay.zeaz.dev
wallet.zeaz.dev

zttato.zeaz.dev
zneon.zeaz.dev
```

This list is contextual, not authoritative. The authoritative inventory must be discoverable from Terraform and validated against actual Cloudflare state.

## Cloudflare + Terraform Architecture

```text
Internet
   │
   ▼
Cloudflare
   ├── DNS
   ├── Proxy
   ├── SSL/TLS
   ├── Zero Trust / Access where required
   ├── Cloudflare Tunnel
   ├── WAF / security controls
   └── Edge routing
          │
          ▼
Origin Infrastructure
   ├── Docker
   ├── Kubernetes / k3s where justified
   ├── Internal services
   ├── Web applications
   └── AI / automation services
```

Where Cloudflare Tunnel is used, origins should remain private whenever practical instead of unnecessarily exposing inbound ports.

Terraform is the source of truth for intended Cloudflare infrastructure configuration. Cloudflare is the execution/edge layer. Git provides version history, review, and traceability.

Manual Cloudflare dashboard changes must not silently become the permanent source of truth.

## Terraform Lifecycle

Infrastructure changes should follow:

```text
Change
  ↓
Git
  ↓
Terraform fmt
  ↓
Terraform validate
  ↓
Static / security checks
  ↓
Terraform plan
  ↓
Impact review
  ↓
Controlled apply
  ↓
Cloudflare
  ↓
Post-deployment validation
```

Use explicit variables, strong validation, least privilege, environment separation, protected state, CI validation, drift detection, and secret separation. Production credentials must never be committed to Git.

## Domain-to-Service Traceability

For every production hostname, zWorkforce should be able to determine:

- What the hostname is for.
- Which service owns it.
- Which repository owns the service.
- Which environment it belongs to.
- Where the origin runs.
- Whether Cloudflare proxying is enabled.
- Whether Cloudflare Tunnel is used.
- Which Terraform resource manages it.
- Which security and access controls apply.
- Which health/readiness checks validate it.
- How it is deployed.
- How it is rolled back or recovered.

Desired relationship:

```text
Hostname
   ↓
Terraform resource
   ↓
Cloudflare zone / edge configuration
   ↓
DNS / Tunnel / Access / security policy
   ↓
Origin service
   ↓
Health validation
```

Unknown, orphaned, duplicated, or manually-created production DNS records are infrastructure debt and must be investigated rather than blindly deleted.

## ZWorkforce Responsibilities

zWorkforce acts as the AI workforce and automation control layer across the ZeaZDev ecosystem.

Relevant agent roles include:

- Architect
- Developer
- Code Reviewer
- Security
- QA/Test
- DevOps
- Terraform
- Cloudflare
- Documentation
- Repository Auditor
- CI/CD
- Production Readiness

Agents must inspect current state before changes and preserve existing architecture and public interfaces unless the requested work explicitly requires change.

## Change-Safety Gate

Cloudflare, Terraform, DNS, Tunnel, authentication, networking, and production mutations require explicit change-safety analysis.

Before a mutation determine:

1. Resource affected.
2. Hostname(s) affected.
3. Environment affected.
4. Origin affected.
5. DNS behavior.
6. Traffic-routing behavior.
7. Tunnel ingress behavior.
8. Security-policy impact.
9. Expected service interruption.
10. Rollback/recovery path.

Preferred flow:

```text
Inspect → Understand → Validate → Plan → Review impact → Apply → Verify
```

Agents must not perform destructive infrastructure changes merely because a configuration appears inconsistent.

## Security Principles

ZeaZDev and zWorkforce follow:

- Least privilege.
- Zero-trust principles where applicable.
- Secret isolation.
- Secure credential handling.
- No plaintext production secrets in Git.
- Strong authentication and explicit authorization.
- Secure API boundaries.
- Dependency and container security.
- Infrastructure validation.
- Auditability.
- Safe automation.

Repository access does not automatically imply authorization to perform destructive infrastructure operations.

## Local-First and Cost Control

Preferred infrastructure hierarchy:

```text
Existing hardware
    >
Self-hosted infrastructure
    >
Open-source software
    >
Free tiers
    >
Paid services only when justified
```

Architecture decisions should account for compute, storage, network, API/model, Cloudflare, managed-service, and operational costs. Avoid unnecessary vendor lock-in and unnecessary managed services when reliable self-hosted alternatives exist.

## Production-Grade Definition

Production readiness is broader than a successful build.

Validate the relevant scope for:

### Application
- Functional correctness.
- API contracts.
- Authentication and authorization.
- Error handling.
- Data integrity.

### Infrastructure
- Reproducible deployment.
- Terraform validation.
- Cloudflare configuration.
- DNS correctness.
- Tunnel routing.
- Origin health.

### Security
- Secrets.
- Dependencies.
- Access control.
- Network exposure.
- Container configuration.
- Security policies.

### Operations
- Logging.
- Metrics and tracing where applicable.
- Health/readiness checks.
- Backup and recovery.
- Rollback.
- Operational documentation.

### Engineering
- Automated tests.
- CI/CD.
- Code quality.
- Documentation.
- Dependency management.
- Version control and traceability.

## Single Source of Truth

```text
Git Repository
      │
      ├── Terraform
      ├── Application Code
      ├── CI/CD
      ├── Configuration
      ├── Contracts
      └── Documentation
             │
             ▼
         Deployment
             │
             ▼
        Cloudflare
             │
             ▼
      Runtime Environment
```

Runtime state is evidence of what is deployed. Git/Terraform expresses intended state. Drift must be detected, understood, and reconciled deliberately.

## Agent Operating Rule

Every zWorkforce agent operating on the ZeaZDev ecosystem should work as an engineering operator:

```text
Discover
→ Analyze
→ Plan
→ Implement
→ Test
→ Review
→ Secure
→ Document
→ Validate
```

Prefer the smallest safe change that completely solves the requested problem.

Avoid duplicate implementations, unnecessary abstractions/dependencies, placeholder implementations, fake or disabled tests, hardcoded secrets, manual-only production configuration, unvalidated Terraform changes, and unrelated production breakage.

## Core Objective

Make zWorkforce the intelligent engineering and automation layer for the ZeaZDev ecosystem, with safe traceability from AI agent action to repository, Terraform configuration, Cloudflare resource, `*.zeaz.dev` hostname, origin service, and production validation.

```text
                    ZEA ZDEV ECOSYSTEM
                           │
                           ▼
                      ZWorkforce
                           │
          ┌────────────────┼────────────────┐
          │                │                │
       Software        Infrastructure      AI
       Engineering      Automation       Workforce
          │                │                │
          ▼                ▼                ▼
       GitHub          Terraform       Agents / Skills
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                       Cloudflare
                           │
                           ▼
                     *.zeaz.dev
                           │
                           ▼
                  Production Services
```

This document provides ecosystem context. It does not replace repository security policy, Terraform-specific rules, Cloudflare provider documentation, deployment runbooks, or application-specific operational documentation.
