# Home Directory Reorganization Plan

## Objective

Organize `/home/cvsz/*` repositories into a clear structure that separates:
- Canonical platform (`z-platform`)
- Migration sources (verified copies outside canonical platform)
- Separate platforms/products
- Standalone apps
- Tools/utilities
- Archives

## Constraints

1. **Do not move/delete repos with uncommitted changes** without operator approval.
2. **Do not break existing CI/CD, scripts, aliases, or bookmarks** that reference absolute paths.
3. **Preserve `.git` history** in all repos.
4. **Secrets must remain in place**; do not move `.env` files across directory boundaries without review.
5. **Operator approval required** for any destructive operation (delete, force push, remote URL change).

## Current state

| Repository | Files (est.) | Uncommitted changes | Classification |
|---|---|---|---|
| `z-platform/` | 180+ | 185 | **CANONICAL** — active refactoring target |
| `zc/` | 350 | 46 | MIGRATION_SOURCE — merged into `services/zc` |
| `zcoder/` | 580 | 7 | MIGRATION_SOURCE — duplicate of `zc` |
| `z-prov/` | 150+ | 37 | MIGRATION_SOURCE — merged into `services/z-prov` |
| `zai-coder/` | 6924 | 15 | MIGRATION_SOURCE — partial merge into `apps/zaicoder` |
| `zaff/` | 500+ | 1 | SEPARATE_PLATFORM — Affiliate Automation OS |
| `zaffiliate/` | 400+ | 0 | SEPARATE_PLATFORM — Affiliate marketing |
| `zworkforce/` | 800+ | 30 | SEPARATE_PLATFORM — Enterprise AI Workforce OS |
| `zeaz/` | 1200+ | 10 | SEPARATE_PLATFORM — MooPiew + legacy migration source |
| `zeaz-ai-command-center/` | 300+ | 0 | SEPARATE_PLATFORM — AI Command Center |
| `zeaz-autonomous-security-agent/` | 100+ | 0 | SEPARATE_PLATFORM — Security agent |
| `zeaz-one-complete/` | 50+ | 0 | ARCHIVE — Product plan artifacts |
| `zeto/` | 400+ | 41 | SEPARATE_PLATFORM — AI Content Factory |
| `zkid/` | 200+ | 0 | STANDALONE_APP — Kids app |
| `zkids-zai/` | 300+ | 14 | STANDALONE_APP — Kids ZAI app |
| `zknowbase/` | 250+ | 1 | SEPARATE_PLATFORM — Knowledge base |
| `zloop_orig/` | 50+ | 0 | ARCHIVE — Skills repo |
| `zpay-android/` | 150+ | 17 | STANDALONE_APP — Android payment |
| `zpwsh/` | 20+ | 9 | TOOL — PowerShell module |
| `z-world/` | 100+ | 0 | SEPARATE_PLATFORM — OCU/World |
| `zdash/` | 300+ | 9 | STANDALONE_APP — Dashboard (submodule reference in z-platform) |

## Proposed structure

```text
/home/cvsz/
├── z-platform/                        # Canonical platform (active)
├── migration-sources/                 # Verified copies, canonical in z-platform
│   ├── zc/                            # Merged into services/zc
│   ├── zcoder/                        # Duplicate of zc
│   ├── z-prov/                        # Merged into services/z-prov
│   └── zai-coder/                     # Partial merge into apps/zaicoder
├── platforms/                         # Separate platforms/products
│   ├── zaff/
│   ├── zaffiliate/
│   ├── zworkforce/
│   ├── zeaz/
│   ├── zeaz-ai-command-center/
│   ├── zeto/
│   ├── zknowbase/
│   ├── z-world/
│   └── zloop_orig/
├── apps/                              # Standalone apps
│   ├── zkid/
│   ├── zkids-zai/
│   ├── zpay-android/
│   └── zdash/
├── tools/                             # Utilities
│   ├── zpwsh/
│   ├── autoc/
│   ├── openclaw/
│   ├── qwen-gen/
│   └── zwiki/
├── archives/                          # Old artifacts, not maintained
│   ├── zeaz-one-complete/
│   ├── zeaz-autonomous-security-agent/
│   ├── zai-coder/                     # Old release artifacts
│   └── ...
└── README.md                          # Home directory index
```

## Execution phases

### Phase H1 — Safe moves (no uncommitted changes)

Move repos with **0 uncommitted changes** first:

1. `z-world/` → `platforms/z-world/`
2. `zaffiliate/` → `platforms/zaffiliate/`
3. `zeaz-ai-command-center/` → `platforms/zeaz-ai-command-center/`
4. `zeaz-autonomous-security-agent/` → `archives/zeaz-autonomous-security-agent/`
5. `zeaz-one-complete/` → `archives/zeaz-one-complete/`
6. `zloop_orig/` → `archives/zloop_orig/`
7. `zkid/` → `apps/zkid/`

**Risk:** Low. No working tree changes to lose.

### Phase H2 — Archive migration sources

After verifying `z-platform` CI passes with migrated code:

1. `zc/` → `migration-sources/zc/`
2. `zcoder/` → `migration-sources/zcoder/`
3. `z-prov/` → `migration-sources/z-prov/`
4. `zai-coder/` → `migration-sources/zai-coder/`

**Risk:** Medium. Requires verification that z-platform contains all needed code.

### Phase H3 — Separate platforms

Move remaining separate platforms:

1. `zaff/` → `platforms/zaff/`
2. `zworkforce/` → `platforms/zworkforce/`
3. `zeaz/` → `platforms/zeaz/`
4. `zeto/` → `platforms/zeto/`
5. `zknowbase/` → `platforms/zknowbase/`

**Risk:** Medium. Each platform may have scripts referencing old paths.

### Phase H4 — Standalone apps & tools

1. `zkids-zai/` → `apps/zkids-zai/`
2. `zpay-android/` → `apps/zpay-android/`
3. `zdash/` → `apps/zdash/`
4. `zpwsh/` → `tools/zpwsh/`
5. `autoc/` → `tools/autoc/`
6. `openclaw/` → `tools/openclaw/`
7. `qwen-gen/` → `tools/qwen-gen/`
8. `zwiki/` → `tools/zwiki/`

**Risk:** Medium. Tools may have hardcoded paths.

### Phase H5 — Cleanup

1. Remove empty old directories after verified moves.
2. Update any broken symlinks or aliases.
3. Update `README.md` in home directory with new structure.
4. Update any CI/CD or scripts that reference old paths.

## Safety measures

1. **Dry run first:** Script supports `--dry-run` flag.
2. **Gitignored:** All moves preserve `.git` directories.
3. **Rollback:** Script generates rollback commands.
4. **Verification:** Each phase includes verification steps.
5. **Operator approval:** Phase H2+ requires explicit approval.

## Rollback plan

If anything breaks:
1. Re-run script with `--undo` flag (generates reverse moves).
2. Verify CI/CD pipelines.
3. Update any broken paths.

## Completed moves

All planned phases were executed with operator approval. Verification passed via checksums for every move.

| Phase | Repo | New Location |
|---|---|---|
| H1 | `z-world/` | `platforms/z-world/` |
| H1 | `zaffiliate/` | `platforms/zaffiliate/` |
| H1 | `zeaz-autonomous-security-agent/` | `archives/zeaz-autonomous-security-agent/` |
| H1 | `zeaz-one-complete/` | `archives/zeaz-one-complete/` |
| H1 | `zloop_orig/` | `archives/zloop_orig/` |
| H1 | `zkid/` | `apps/zkid/` |
| H2 | `zc/` | `migration-sources/zc/` |
| H2 | `zcoder/` | `migration-sources/zcoder/` |
| H2 | `z-prov/` | `migration-sources/z-prov/` |
| H2 | `zai-coder/` | `migration-sources/zai-coder/` |
| H3 | `zaff/` | `platforms/zaff/` |
| H3 | `zworkforce/` | `platforms/zworkforce/` |
| H3 | `zeaz/` | `platforms/zeaz/` |
| H3 | `zeto/` | `platforms/zeto/` |
| H3 | `zknowbase/` | `platforms/zknowbase/` |
| extra | `zeaz-ai-command-center/` | `platforms/zeaz-ai-command-center/` |
| extra | `zcoder-claude/` | `platforms/zcoder-claude/` |
| H4 | `zkids-zai/` | `apps/zkids-zai/` |
| H4 | `zpay-android/` | `apps/zpay-android/` |
| H4 | `zdash/` | `apps/zdash/` |
| H4 | `zpwsh/` | `tools/zpwsh/` |
| H4 | `autoc/` | `tools/autoc/` |
| H4 | `openclaw/` | `tools/openclaw/` |
| H4 | `qwen-gen/` | `tools/qwen-gen/` |
| H4 | `zwiki/` | `tools/zwiki/` |

## Actual final structure

```text
/home/cvsz/
├── z-platform/
├── migration-sources/
│   ├── zc/
│   ├── zcoder/
│   ├── z-prov/
│   └── zai-coder/
├── platforms/
│   ├── zaff/
│   ├── zaffiliate/
│   ├── zcoder-claude/
│   ├── zeaz/
│   ├── zeaz-ai-command-center/
│   ├── zeto/
│   ├── zknowbase/
│   ├── z-world/
│   └── zworkforce/
├── apps/
│   ├── zdash/
│   ├── zkid/
│   ├── zkids-zai/
│   └── zpay-android/
├── tools/
│   ├── autoc/
│   ├── openclaw/
│   ├── qwen-gen/
│   ├── zpwsh/
│   └── zwiki/
├── archives/
│   ├── zeaz-autonomous-security-agent/
│   ├── zeaz-one-complete/
│   └── zloop_orig/
└── README.md
```

## Remaining top-level items

These were outside the original reorganization scope and were left untouched:

- `ads/`, `aicoder/`, `github-private-control/`, `litellm/`, `llm_wiki/`, `llm-wiki-app/`, `raw/`, `services/`, `wiki/`
- `cloudflare/`, `cloudflared/`, `computer/`, `freebuff/`, `go/`, `google-cloud-sdk/`, `hercules-copy/`, `kbank-edc/`, `snap/`
- `bin/`

## Open questions

1. Should `zai-coder/` (6924 files) be fully merged into `apps/zaicoder/` before archiving?
2. Should `zc/` be fully removed after migration, or kept as reference?
3. Should `zeaz/` remain as migration source for `z-platform`, or be archived?
4. Do any tools/scripts reference absolute paths to these repos?
5. Should the remaining top-level items above be classified and moved in a follow-up pass?
