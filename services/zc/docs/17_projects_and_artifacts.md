# Feature Projects & Artifacts — AI Model Coder CLI v1.7.0

## Overview

Two new subsystems added in v1.7.0:

- **Feature Projects** — Full project lifecycle management: create, plan, scaffold, track tasks, and run agents across a project.
- **Artifacts** — Named, versioned, AI-generated outputs: code files, docs, schemas, diagrams, configs, and more.

---

## Feature Projects

### Concepts

| Concept | Description |
|---------|-------------|
| **Project** | A container for a feature or application with tasks, context, and a workspace directory |
| **Task** | A unit of work with title, description, assigned agent, priority, and status |
| **Template** | Pre-built task sets for common project types |
| **Workspace** | `~/.ai-coder/projects/<id>/workspace/` — AI output saved here |

### Templates

| Template | Description |
|----------|-------------|
| `blank` | Empty — define your own tasks |
| `web_app` | Full-stack app (backend, frontend, DB, security, docs) |
| `api` | REST API with auth, tests, OpenAPI docs |
| `cli_tool` | CLI tool with config, tests, packaging, README |
| `data_pipeline` | ETL/data pipeline with validation and monitoring |
| `ml_model` | ML project from data prep to model serving |

### Commands

```bash
# Create a project
ai-coder --project-create "My API" --project-desc "User management REST API" --project-template api

# List all projects
ai-coder --project-list

# Show project details and task status
ai-coder --project-show <id>

# AI-generate a task plan (calls zAICoder to design tasks)
ai-coder --project-plan <id>

# Add a custom task
ai-coder --project-add-task <id> --task-title "Add OAuth2" --task-agent code_generator --task-priority high

# Run a specific task
ai-coder --project-run <id> --task <task_id>

# Run all pending tasks
ai-coder --project-run <id> --task all

# Archive a project
ai-coder --project-archive <id>

# Delete a project
ai-coder --project-delete <id>

# List available templates
ai-coder --project-templates
```

### Task Priorities & Statuses

**Priorities:** `low` · `medium` · `high` · `critical`

**Statuses:** `todo` · `in_progress` · `done` · `blocked`

### Example Workflow

```bash
# 1. Create project from template
ai-coder --project-create "E-commerce API" --project-template api

# 2. Generate AI task plan (adds intelligent tasks based on your description)
ai-coder --project-plan <id>

# 3. Review the plan
ai-coder --project-show <id>

# 4. Add a custom task
ai-coder --project-add-task <id> --task-title "Rate limiting middleware" --task-priority high

# 5. Run all tasks (each saved to workspace/)
ai-coder --project-run <id> --task all

# 6. Results are saved to ~/.ai-coder/projects/<id>/workspace/task_<task_id>.md
```

---

## Artifacts

### Concepts

| Concept | Description |
|---------|-------------|
| **Artifact** | A named, versioned, AI-generated output |
| **Version** | Each iteration creates a new version; all versions are kept |
| **Type** | The kind of content (code, docs, tests, schema, etc.) |
| **Tag** | Searchable labels attached to artifacts |

### Artifact Types

| Type | Description | Default Extension |
|------|-------------|-------------------|
| `code` | Source code in any language | `.py` |
| `docs` | Documentation, README, API reference | `.md` |
| `tests` | Test suites and test cases | `.py` |
| `schema` | Database schemas, JSON schemas, Pydantic models | `.json` |
| `config` | Config files, YAML/TOML/JSON settings | `.yaml` |
| `diagram` | Architecture / flow diagrams (Mermaid or ASCII) | `.md` |
| `report` | Analysis, audit, or performance reports | `.md` |
| `plan` | Project plans, task breakdowns, roadmaps | `.md` |
| `changelog` | CHANGELOG entries and release notes | `.md` |
| `prompt` | Reusable system prompts and few-shot examples | `.txt` |
| `script` | Shell / build / deployment scripts | `.sh` |
| `template` | Code or document templates | `.txt` |

### Commands

```bash
# Create an artifact
ai-coder --artifact-create "auth_module" -p "Write JWT auth for FastAPI" \
  --artifact-type code --artifact-lang Python --artifact-tags "fastapi,auth,jwt"

# List all artifacts
ai-coder --artifact-list

# Search artifacts
ai-coder --artifact-list --artifact-query "fastapi"

# Filter by type
ai-coder --artifact-list --artifact-type docs

# Filter by project
ai-coder --artifact-list --artifact-project <project_id>

# Filter by tag
ai-coder --artifact-list --tag "auth"

# Show artifact content
ai-coder --artifact-show <id>

# Show a specific version
ai-coder --artifact-show <id> --artifact-version 1

# Iterate with feedback (creates a new version)
ai-coder --artifact-iterate <id> -p "Add refresh token support and token revocation"

# Diff two versions
ai-coder --artifact-diff <id> --v1 1 --v2 2

# Export to file (auto-named by default)
ai-coder --artifact-export <id>

# Export to specific file
ai-coder --artifact-export <id> -o auth.py

# Export specific version
ai-coder --artifact-export <id> --artifact-version 1 -o auth_v1.py

# Export all artifacts for a project
ai-coder --artifact-export-all <project_id> --artifact-output-dir ./my_project_files/

# Add a tag
ai-coder --artifact-tag <id> --tag "production-ready"

# Attach to a project
ai-coder --artifact-attach <artifact_id> --to-project <project_id>

# Delete an artifact
ai-coder --artifact-delete <id>

# List artifact types
ai-coder --artifact-types
```

### Version History

Every time you iterate an artifact, a new version is stored. The `--artifact-show` command displays the full version history with timestamps and notes. You can view or export any past version with `--artifact-version <n>`.

### Example Workflow

```bash
# 1. Create a code artifact
ai-coder --artifact-create "flask_api" \
  -p "Create a Flask REST API with CRUD for users" \
  --artifact-type code --artifact-lang Python \
  --artifact-tags "flask,api,crud"

# 2. Review what was generated
ai-coder --artifact-show <id>

# 3. Iterate with feedback
ai-coder --artifact-iterate <id> -p "Add SQLAlchemy ORM and database migrations"

# 4. Iterate again
ai-coder --artifact-iterate <id> -p "Add JWT authentication to all protected routes"

# 5. Diff v1 vs v3
ai-coder --artifact-diff <id> --v1 1 --v2 3

# 6. Export the final version
ai-coder --artifact-export <id> -o api.py

# 7. Attach to your project
ai-coder --artifact-attach <id> --to-project <project_id>
```

---

## Projects + Artifacts Together

```bash
# Create project
ai-coder --project-create "Chat App" --project-template web_app

# Generate artifacts for the project
ai-coder --artifact-create "db_schema" \
  -p "PostgreSQL schema for chat app with users, rooms, messages" \
  --artifact-type schema --artifact-project <project_id>

ai-coder --artifact-create "api_design" \
  -p "REST API design for the chat app" \
  --artifact-type diagram --artifact-project <project_id>

ai-coder --artifact-create "backend_api" \
  -p "FastAPI backend for the chat app" \
  --artifact-type code --artifact-lang Python \
  --artifact-project <project_id>

# Export all artifacts for the project
ai-coder --artifact-export-all <project_id> --artifact-output-dir ./chat_app/

# Run AI tasks on the project
ai-coder --project-run <project_id> --task all
```

---

## Storage

| Location | Purpose |
|----------|---------|
| `~/.ai-coder/projects/<id>/project.json` | Project manifest |
| `~/.ai-coder/projects/<id>/workspace/` | AI task outputs |
| `~/.ai-coder/artifacts/<id>/meta.json` | Artifact metadata |
| `~/.ai-coder/artifacts/<id>/v0001.txt` | Artifact version 1 content |
| `~/.ai-coder/artifacts/<id>/v0002.txt` | Artifact version 2 content |

---

## What's New in v1.7.0

| Feature | Description |
|---------|-------------|
| `projects.py` | Full project lifecycle: create, plan, tasks, run, archive |
| `artifacts.py` | Versioned AI outputs: create, iterate, diff, export, tag |
| 6 project templates | blank, web_app, api, cli_tool, data_pipeline, ml_model |
| 12 artifact types | code, docs, tests, schema, config, diagram, report, plan, changelog, prompt, script, template |
| AI plan generation | `--project-plan` calls zAICoder to design task lists |
| Version diffing | `--artifact-diff` shows unified diff between any two versions |
| Project export | `--artifact-export-all` bundles all project artifacts |
| 100% backward compatible | All v1.0–v1.6 commands unchanged |
