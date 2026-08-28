from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

# Valid zWorkforce tool identifiers from TOOL_DEFINITIONS
DEFAULT_ZWORKFORCE_TOOLS = ["workspace_read", "workspace_write", "shell_exec"]


@dataclass
class AgentPromptSpec:
    name: str
    role: str = ""
    description: str = ""
    domain: str = "general"
    reasoning_tier: str = "terra"  # luna, terra, sol
    allowed_tools: List[str] = field(default_factory=lambda: list(DEFAULT_ZWORKFORCE_TOOLS))
    tenant_isolation: bool = True
    deny_by_default: bool = True
    fail_closed: bool = True
    additional_rules: List[str] = field(default_factory=list)
    output_format: str = "markdown"  # markdown, json


class AgentPromptGenerator:
    """Generates structured prompts and configurations for workforce agents."""

    TEMPLATES = {
        "coder": {
            "role": "Autonomous Software Engineer",
            "principles": [
                "Write modular, type-annotated, and production-tested code.",
                "Never introduce shell=True or expose plaintext secrets.",
                "Maintain backward compatibility and adhere to fail-closed error handling.",
                "Run test suites and linters before reporting completion."
            ]
        },
        "reviewer": {
            "role": "Code Reviewer & Security Auditor",
            "principles": [
                "Audit code for tenant isolation, secret redaction, and bounded execution.",
                "Enforce deny-by-default access policies and verify error paths.",
                "Confirm that all mutation boundaries carry approval requirements.",
                "Provide concise, actionable findings with specific line references."
            ]
        },
        "researcher": {
            "role": "Codebase & Deep Research Specialist",
            "principles": [
                "Explore files using targeted searches without loading unnecessary context.",
                "Summarize findings with clear source file links and citations.",
                "Distinguish between verified facts and speculative hypotheses."
            ]
        },
        "writer": {
            "role": "Technical Documentation Specialist",
            "principles": [
                "Document APIs, architectures, and disaster-recovery runbooks with precision.",
                "Follow established repo styling, markdown standards, and mermaid diagrams.",
                "Ensure zero drift between implementation and reference documentation."
            ]
        },
        "general": {
            "role": "Specialist Agent",
            "principles": [
                "Perform assigned tasks with precision and adhere to repository boundaries."
            ]
        }
    }

    def __init__(self) -> None:
        pass

    def resolve_role(self, spec: AgentPromptSpec) -> str:
        if spec.role and spec.role.strip():
            return spec.role.strip()
        template = self.TEMPLATES.get(spec.domain, self.TEMPLATES["general"])
        return template["role"]

    def build_system_prompt(self, spec: AgentPromptSpec) -> str:
        """Constructs a comprehensive system prompt string."""
        resolved_role = self.resolve_role(spec)
        template_info = self.TEMPLATES.get(spec.domain, self.TEMPLATES["general"])

        lines = [
            f"# AGENT SYSTEM DIRECTIVE: {spec.name.upper()}",
            f"**Role**: {resolved_role}",
            f"**Domain**: {spec.domain.capitalize()} | **Reasoning Tier**: {spec.reasoning_tier.upper()}",
            "",
            "## 1. Primary Objectives & Identity",
            spec.description,
            "",
            "## 2. Core Operational Principles",
        ]

        for p in template_info.get("principles", []):
            lines.append(f"- {p}")

        lines.extend([
            "",
            "## 3. Tool Permissions & Security Boundaries",
            f"- **Allowed Tools**: {', '.join(spec.allowed_tools) if spec.allowed_tools else 'None (Read-only / Conversational)'}",
            f"- **Tenant Isolation**: {'STRICT' if spec.tenant_isolation else 'SHARED'}",
            f"- **Default Policy**: {'DENY-BY-DEFAULT' if spec.deny_by_default else 'PERMISSIVE'}",
            f"- **Execution Failure Mode**: {'FAIL-CLOSED' if spec.fail_closed else 'FAIL-OPEN'}",
        ])

        if spec.additional_rules:
            lines.extend(["", "## 4. Specific Guardrails & Custom Rules"])
            for rule in spec.additional_rules:
                lines.append(f"- {rule}")

        lines.extend([
            "",
            "## 5. Output & Delivery Standards",
            "- Format all responses concisely in GitHub-flavored markdown.",
            "- Use file:// links when referring to symbols, classes, or files.",
            "- Do not hallucinate or claim unverified external states."
        ])

        return "\n".join(lines)

    def generate_manifest(self, spec: AgentPromptSpec) -> Dict[str, Any]:
        """Generates a zWorkforce API compatible agent manifest dictionary."""
        slug_id = re.sub(r"[^a-z0-9-]+", "-", spec.name.lower()).strip("-")
        prompt = self.build_system_prompt(spec)
        
        tier_map = {
            "fast": "luna",
            "balanced": "terra",
            "deep_thinking": "sol",
            "luna": "luna",
            "terra": "terra",
            "sol": "sol"
        }
        tier = tier_map.get(spec.reasoning_tier.lower(), "terra")

        return {
            "id": slug_id or "custom-agent",
            "name": spec.name,
            "description": spec.description,
            "system_prompt": prompt,
            "default_tier": tier,
            "allowed_tools": spec.allowed_tools,
            "approval_tools": [t for t in spec.allowed_tools if t in {"workspace_write", "shell_exec"}],
            "skill_ids": [],
            "max_iterations": 16,
            "max_subagents": 4,
            "required_approvals": 1 if any(t in {"workspace_write", "shell_exec"} for t in spec.allowed_tools) else 0,
            "max_cost_credits": 10.0
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate structured agent prompts and manifests")
    parser.add_argument("--name", required=True, help="Agent name (e.g. zworkforce-auditor)")
    parser.add_argument("--role", default="", help="Role title (defaults to domain template role if omitted)")
    parser.add_argument("--domain", choices=["coder", "reviewer", "researcher", "writer", "general"], default="coder", help="Predefined domain")
    parser.add_argument("--desc", required=True, help="Task description and objectives")
    parser.add_argument("--tier", choices=["luna", "terra", "sol", "fast", "balanced", "deep_thinking"], default="terra", help="Reasoning tier")
    parser.add_argument("--tools", nargs="*", default=None, help="Allowed tools")
    parser.add_argument("--rules", nargs="*", default=[], help="Additional specific rules")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Output format")

    args = parser.parse_args()

    tools = args.tools if args.tools is not None else list(DEFAULT_ZWORKFORCE_TOOLS)

    spec = AgentPromptSpec(
        name=args.name,
        role=args.role,
        description=args.desc,
        domain=args.domain,
        reasoning_tier=args.tier,
        allowed_tools=tools,
        additional_rules=args.rules,
        output_format=args.format
    )

    gen = AgentPromptGenerator()

    if args.format == "json":
        manifest = gen.generate_manifest(spec)
        print(json.dumps(manifest, indent=2))
    else:
        prompt = gen.build_system_prompt(spec)
        print(prompt)


if __name__ == "__main__":
    main()
