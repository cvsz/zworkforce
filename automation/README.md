# Automation Source of Truth

This directory is the canonical source for AI automation assets in `z-platform`.

## Structure

```text
automation/
├── README.md          # This file
├── agents/            # Agent persona definitions
├── prompts/           # Phase and task prompt templates
├── skills/            # Reusable skill definitions
├── policies/          # Automation policies (approval, sandbox, secrets)
└── workflows/         # Reusable workflow definitions
```

## Canonical sources

| Asset | Canonical path | Generated compatibility layer |
|---|---|---|
| z-platform skill | `automation/skills/z-platform/SKILL.md` | `.agents/skills/z-platform/SKILL.md`, `.claude/skills/z-platform/SKILL.md` |
| Codex agents | `automation/agents/*.toml` | `.codex/agents/*.toml` |
| Codex prompts | `automation/prompts/*/` | `.codex/prompts/*/` |
| Claude commands | `automation/workflows/*.md` | `.claude/commands/*.md` |

## Generation

Compatibility layers are generated from canonical sources. Do not edit generated files directly. Instead:

1. Edit the canonical source in `automation/`.
2. Run the generation script (to be created in Phase R5).
3. Commit both the canonical source and the generated layer.

## Policies

- No user-specific credentials or private MCPs in the repository.
- Keep secrets, provider keys, and tokens in environment variables or secret managers.
- Automation must not silently mutate production infrastructure.

## Multi-agent support

- Explorer: read-only evidence gathering
- Reviewer: correctness, security, and regression review
- Docs researcher: API and release-note verification
- Phase planner: phase-scoped platform delivery planning
- Security guardian: secrets, access policy, and guarded automation review
- Validation operator: offline validation mapping without infrastructure mutation
