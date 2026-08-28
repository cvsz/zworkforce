"""
projects.py — Feature Projects subsystem
AI Model Coder CLI v1.7.0

Manages full project lifecycles: create, plan, scaffold, track tasks,
run agents across a project, and maintain a project manifest.
"""
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from wire.security import safe_resolve
from typing import Optional

PROJECTS_DIR = os.path.expanduser("~/.ai-coder/projects")


# ── helpers ────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _projects_dir() -> Path:
    p = Path(PROJECTS_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _project_path(project_id: str) -> Path:
    """Resolve project path securely, ensuring it stays within PROJECTS_DIR."""
    return safe_resolve(project_id, PROJECTS_DIR)


def _manifest_path(project_id: str) -> Path:
    return _project_path(project_id) / "project.json"


def _load_manifest(project_id: str) -> dict:
    mp = _manifest_path(project_id)
    if not mp.exists():
        raise FileNotFoundError(f"Project '{project_id}' not found.")
    with open(mp) as f:
        return json.load(f)


def _save_manifest(project_id: str, data: dict):
    mp = _manifest_path(project_id)
    mp.parent.mkdir(parents=True, exist_ok=True)
    with open(mp, "w") as f:
        json.dump(data, f, indent=2)


# ── Project Status ──────────────────────────────────────────────────────────

class ProjectStatus:
    PLANNING = "planning"
    ACTIVE   = "active"
    PAUSED   = "paused"
    DONE     = "done"
    ARCHIVED = "archived"


# ── Task ───────────────────────────────────────────────────────────────────

class Task:
    def __init__(self, title: str, description: str = "", agent: str = "",
                 priority: str = "medium", task_id: Optional[str] = None):
        self.id          = task_id or str(uuid.uuid4())[:8]
        self.title       = title
        self.description = description
        self.agent       = agent            # which agent handles this
        self.priority    = priority         # low / medium / high / critical
        self.status      = "todo"           # todo / in_progress / done / blocked
        self.created_at  = _now()
        self.updated_at  = _now()
        self.result      = ""

    def to_dict(self) -> dict:
        return self.__dict__

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        t = cls.__new__(cls)
        t.__dict__.update(d)
        return t


# ── ProjectManager ─────────────────────────────────────────────────────────

class ProjectManager:
    """Create, manage, and run Feature Projects."""

    # ── CRUD ───────────────────────────────────────────────────────────────

    def create_project(self, name: str, description: str = "",
                       template: str = "blank") -> dict:
        """Create a new project and return its manifest."""
        pid = str(uuid.uuid4())[:12]
        templates = self._builtin_templates()
        tpl = templates.get(template, templates["blank"])

        manifest = {
            "id":          pid,
            "name":        name,
            "description": description,
            "template":    template,
            "status":      ProjectStatus.PLANNING,
            "created_at":  _now(),
            "updated_at":  _now(),
            "tasks":       [t.to_dict() for t in tpl["tasks"]],
            "context":     tpl.get("context", ""),
            "files":       [],
            "tags":        [],
            "agents_used": [],
            "run_log":     [],
        }
        _save_manifest(pid, manifest)

        # Create project workspace directory
        ws = _project_path(pid) / "workspace"
        ws.mkdir(parents=True, exist_ok=True)

        return manifest

    def list_projects(self) -> list:
        projects = []
        base = _projects_dir()
        for d in sorted(base.iterdir()):
            mp = d / "project.json"
            if mp.exists():
                try:
                    with open(mp) as f:
                        m = json.load(f)
                    projects.append({
                        "id":          m["id"],
                        "name":        m["name"],
                        "status":      m["status"],
                        "tasks_total": len(m.get("tasks", [])),
                        "tasks_done":  sum(1 for t in m.get("tasks", []) if t.get("status") == "done"),
                        "created_at":  m.get("created_at", ""),
                        "updated_at":  m.get("updated_at", ""),
                    })
                except Exception:
                    pass
        return projects

    def get_project(self, project_id: str) -> dict:
        return _load_manifest(project_id)

    def update_project(self, project_id: str, **kwargs) -> dict:
        m = _load_manifest(project_id)
        for k, v in kwargs.items():
            if k in m:
                m[k] = v
        m["updated_at"] = _now()
        _save_manifest(project_id, m)
        return m

    def delete_project(self, project_id: str) -> bool:
        pp = _project_path(project_id)
        if pp.exists():
            shutil.rmtree(pp)
            return True
        return False

    def archive_project(self, project_id: str) -> dict:
        return self.update_project(project_id, status=ProjectStatus.ARCHIVED)

    # ── Tasks ──────────────────────────────────────────────────────────────

    def add_task(self, project_id: str, title: str, description: str = "",
                 agent: str = "", priority: str = "medium") -> dict:
        m = _load_manifest(project_id)
        task = Task(title, description, agent, priority)
        m["tasks"].append(task.to_dict())
        m["updated_at"] = _now()
        _save_manifest(project_id, m)
        return task.to_dict()

    def update_task(self, project_id: str, task_id: str, **kwargs) -> dict:
        m = _load_manifest(project_id)
        for t in m["tasks"]:
            if t["id"] == task_id:
                t.update(kwargs)
                t["updated_at"] = _now()
                break
        m["updated_at"] = _now()
        _save_manifest(project_id, m)
        return m

    def complete_task(self, project_id: str, task_id: str, result: str = "") -> dict:
        return self.update_task(project_id, task_id, status="done", result=result)

    # ── AI-powered actions ─────────────────────────────────────────────────

    def generate_plan(self, project_id: str, coder) -> str:
        """Use AI to generate a task plan for the project."""
        m = _load_manifest(project_id)
        prompt = (
            f"Project: {m['name']}\n"
            f"Description: {m['description']}\n"
            f"Template: {m['template']}\n\n"
            "Generate a detailed task plan with 5-10 concrete tasks. "
            "For each task include: title, description, suggested agent "
            "(code_generator/testing_agent/security_auditor/documentation_agent/"
            "optimizer/full_stack), and priority (low/medium/high/critical). "
            "Respond as a JSON array of task objects."
        )
        system = (
            "You are a senior software architect. Output ONLY a JSON array — "
            "no markdown fences, no prose. Each object must have keys: "
            "title, description, agent, priority."
        )
        result = coder.generate(prompt, system=system)

        # Parse and insert tasks
        try:
            # Strip possible markdown fences
            clean = result.strip()
            if clean.startswith("```"):
                clean = "\n".join(clean.split("\n")[1:])
            if clean.endswith("```"):
                clean = "\n".join(clean.split("\n")[:-1])
            tasks_data = json.loads(clean)
            m = _load_manifest(project_id)
            for td in tasks_data:
                task = Task(
                    title=td.get("title", "Task"),
                    description=td.get("description", ""),
                    agent=td.get("agent", ""),
                    priority=td.get("priority", "medium"),
                )
                m["tasks"].append(task.to_dict())
            m["status"] = ProjectStatus.ACTIVE
            m["updated_at"] = _now()
            _save_manifest(project_id, m)
            return f"Generated {len(tasks_data)} tasks for project '{m['name']}'."
        except json.JSONDecodeError:
            # AI returned prose plan — store as context
            m = _load_manifest(project_id)
            m["context"] = result
            m["updated_at"] = _now()
            _save_manifest(project_id, m)
            return result

    def run_task(self, project_id: str, task_id: str, coder) -> str:
        """Run a single task using its assigned agent."""
        m = _load_manifest(project_id)
        task_data = next((t for t in m["tasks"] if t["id"] == task_id), None)
        if not task_data:
            return f"[ERROR] Task {task_id} not found."

        self.update_task(project_id, task_id, status="in_progress")

        prompt = (
            f"Project: {m['name']}\nContext: {m.get('context', '')}\n\n"
            f"Task: {task_data['title']}\n{task_data['description']}"
        )
        system = (
            "You are an expert software developer. Complete the task thoroughly. "
            "Provide complete, runnable code or documentation as appropriate."
        )
        result = coder.generate(prompt, system=system)

        self.complete_task(project_id, task_id, result=result[:500])

        # Log to run_log
        mn = _load_manifest(project_id)
        mn["run_log"].append({
            "timestamp": _now(),
            "task_id":   task_id,
            "task":      task_data["title"],
            "agent":     task_data.get("agent", "ai"),
            "status":    "done",
        })
        _save_manifest(project_id, mn)

        # Save result to workspace
        ws = _project_path(project_id) / "workspace"
        ws.mkdir(exist_ok=True)
        out_file = ws / f"task_{task_id}.md"
        out_file.write_text(f"# {task_data['title']}\n\n{result}")

        return result

    def run_all_pending(self, project_id: str, coder) -> dict:
        """Run all todo tasks in sequence."""
        m = _load_manifest(project_id)
        results = {}
        pending = [t for t in m["tasks"] if t.get("status") == "todo"]
        for t in pending:
            print(f"  → Running: {t['title']}")
            results[t["id"]] = self.run_task(project_id, t["id"], coder)
        return results

    # ── Display ────────────────────────────────────────────────────────────

    def show_project(self, project_id: str) -> str:
        m = _load_manifest(project_id)
        tasks = m.get("tasks", [])
        done  = sum(1 for t in tasks if t.get("status") == "done")
        pct   = int(done / len(tasks) * 100) if tasks else 0
        bar   = "█" * (pct // 5) + "░" * (20 - pct // 5)

        lines = [
            f"\n{'═'*60}",
            f"  PROJECT: {m['name']}",
            f"  ID:      {m['id']}",
            f"  Status:  {m['status']}",
            f"  Created: {m['created_at'][:10]}",
            f"  Progress: [{bar}] {pct}% ({done}/{len(tasks)} tasks)",
            f"{'═'*60}",
        ]
        if m.get("description"):
            lines.append(f"\n  {m['description']}")
        if tasks:
            lines.append("\n  TASKS:")
            icons = {"todo": "○", "in_progress": "◐", "done": "●", "blocked": "✗"}
            pri_colors = {"critical": "31", "high": "33", "medium": "36", "low": "37"}
            for t in tasks:
                icon  = icons.get(t.get("status", "todo"), "○")
                color = pri_colors.get(t.get("priority", "medium"), "37")
                lines.append(
                    f"  {icon} [{t['id']}] \033[{color}m{t['title']}\033[0m"
                    f" ({t.get('priority','medium')}) — {t.get('status','todo')}"
                )
        return "\n".join(lines)

    # ── Templates ──────────────────────────────────────────────────────────

    def _builtin_templates(self) -> dict:
        def tasks(*specs):
            return [Task(title=s[0], description=s[1], agent=s[2], priority=s[3]) for s in specs]

        return {
            "blank": {"tasks": [], "context": ""},
            "web_app": {
                "context": "Full-stack web application project.",
                "tasks": tasks(
                    ("Architecture Design", "Define system architecture and tech stack.", "code_generator", "high"),
                    ("Backend API",         "Implement REST API with authentication.",    "code_generator", "high"),
                    ("Frontend UI",         "Build responsive frontend interface.",        "code_generator", "medium"),
                    ("Database Schema",     "Design and implement database schema.",       "code_generator", "high"),
                    ("Unit Tests",          "Write comprehensive test suite.",            "testing_agent",  "medium"),
                    ("Security Audit",      "Review for common vulnerabilities.",         "security_auditor","high"),
                    ("Documentation",       "API docs and README.",                       "documentation_agent","low"),
                ),
            },
            "api": {
                "context": "REST API project.",
                "tasks": tasks(
                    ("API Design",     "Design endpoints and data models.", "code_generator",      "high"),
                    ("Implementation", "Implement all endpoints.",          "code_generator",      "high"),
                    ("Auth Layer",     "Add JWT/OAuth authentication.",     "code_generator",      "high"),
                    ("Tests",          "Integration and unit tests.",       "testing_agent",       "medium"),
                    ("Security",       "Rate limiting, input validation.",  "security_auditor",    "high"),
                    ("Docs",           "OpenAPI/Swagger documentation.",    "documentation_agent", "medium"),
                ),
            },
            "cli_tool": {
                "context": "Command-line tool project.",
                "tasks": tasks(
                    ("CLI Design",    "Define commands and flags.",         "code_generator",      "high"),
                    ("Core Logic",    "Implement main functionality.",      "code_generator",      "high"),
                    ("Config",        "Config file and env var support.",   "code_generator",      "medium"),
                    ("Tests",         "Unit tests for all commands.",       "testing_agent",       "medium"),
                    ("Packaging",     "setup.py and distribution.",         "code_generator",      "low"),
                    ("README",        "Usage guide with examples.",         "documentation_agent", "medium"),
                ),
            },
            "data_pipeline": {
                "context": "Data pipeline / ETL project.",
                "tasks": tasks(
                    ("Schema Design",  "Define input/output schemas.",     "code_generator",      "high"),
                    ("Ingestion",      "Data ingestion from sources.",     "code_generator",      "high"),
                    ("Transform",      "Transformation and cleaning.",     "code_generator",      "high"),
                    ("Validation",     "Data quality checks.",             "testing_agent",       "medium"),
                    ("Optimization",   "Performance tuning.",              "optimizer",           "medium"),
                    ("Monitoring",     "Logging and alerting.",            "code_generator",      "low"),
                    ("Docs",           "Pipeline documentation.",          "documentation_agent", "low"),
                ),
            },
            "ml_model": {
                "context": "Machine learning model project.",
                "tasks": tasks(
                    ("Data Prep",      "Data loading and preprocessing.",  "code_generator",      "high"),
                    ("EDA",            "Exploratory data analysis.",       "code_generator",      "medium"),
                    ("Model Design",   "Architecture selection.",          "code_generator",      "high"),
                    ("Training",       "Training loop implementation.",    "code_generator",      "high"),
                    ("Evaluation",     "Metrics and validation.",          "testing_agent",       "high"),
                    ("Serving",        "Inference API or export.",         "code_generator",      "medium"),
                    ("Docs",           "Model card and usage guide.",      "documentation_agent", "low"),
                ),
            },
        }

    def list_templates(self) -> list:
        return list(self._builtin_templates().keys())


# ── CLI helpers (called from main.py) ─────────────────────────────────────

def cmd_project_create(name, description="", template="blank"):
    pm = ProjectManager()
    m = pm.create_project(name, description, template)
    print(f"\033[92m✓ Project created: {m['name']} (ID: {m['id']})\033[0m")
    print(f"  Template: {template}  |  Tasks: {len(m['tasks'])}")
    print(f"  Workspace: {_project_path(m['id']) / 'workspace'}")
    return m


def cmd_project_list():
    pm = ProjectManager()
    projects = pm.list_projects()
    if not projects:
        print("No projects yet. Create one with --project-create <name>")
        return
    print(f"\n{'ID':<14}{'NAME':<25}{'STATUS':<12}{'PROGRESS':<12}{'UPDATED'}")
    print("─" * 75)
    for p in projects:
        done  = p["tasks_done"]
        total = p["tasks_total"]
        prog  = f"{done}/{total}" if total else "—"
        print(f"{p['id']:<14}{p['name'][:24]:<25}{p['status']:<12}{prog:<12}{p['updated_at'][:10]}")


def cmd_project_show(project_id):
    pm = ProjectManager()
    print(pm.show_project(project_id))


def cmd_project_plan(project_id, coder):
    pm = ProjectManager()
    print(f"\033[94mℹ Generating AI plan for project {project_id}…\033[0m")
    result = pm.generate_plan(project_id, coder)
    print(result)
    print(pm.show_project(project_id))


def cmd_project_run(project_id, task_id, coder):
    pm = ProjectManager()
    if task_id == "all":
        results = pm.run_all_pending(project_id, coder)
        print(f"\033[92m✓ Completed {len(results)} tasks.\033[0m")
    else:
        result = pm.run_task(project_id, task_id, coder)
        print(result)


def cmd_project_add_task(project_id, title, description="", agent="", priority="medium"):
    pm = ProjectManager()
    t = pm.add_task(project_id, title, description, agent, priority)
    print(f"\033[92m✓ Task added: [{t['id']}] {t['title']}\033[0m")


def cmd_project_templates():
    pm = ProjectManager()
    templates = pm.list_templates()
    print("\nAvailable project templates:")
    descriptions = {
        "blank":         "Empty project — start from scratch",
        "web_app":       "Full-stack web app (backend + frontend + DB + security)",
        "api":           "REST API with auth, tests, and OpenAPI docs",
        "cli_tool":      "Command-line tool with packaging and README",
        "data_pipeline": "ETL/data pipeline with validation and monitoring",
        "ml_model":      "Machine learning project from data prep to serving",
    }
    for t in templates:
        print(f"  {t:<18} — {descriptions.get(t, '')}")
