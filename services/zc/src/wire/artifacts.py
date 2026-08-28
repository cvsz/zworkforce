"""
artifacts.py — Artifacts subsystem
AI Model Coder CLI v1.7.0

An Artifact is any named, versioned, AI-generated output:
  code, documentation, test suites, architecture diagrams (as text/mermaid),
  schemas, configs, changelogs, reports, etc.

Artifacts can be:
  • Created from a prompt                 --artifact-create
  • Listed and searched                   --artifact-list [query]
  • Viewed / diffed across versions       --artifact-show <id>
  • Exported to a file                    --artifact-export <id>
  • Iterated / regenerated with feedback  --artifact-iterate <id>
  • Tagged for search                     --artifact-tag <id> <tag>
  • Attached to a project                 --artifact-attach <artifact_id> <project_id>
  • Deleted                               --artifact-delete <id>
"""
import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ARTIFACTS_DIR = os.path.expanduser("~/.ai-coder/artifacts")


# ── helpers ────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _artifacts_dir() -> Path:
    p = Path(ARTIFACTS_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _artifact_path(artifact_id: str) -> Path:
    """Resolve artifact path securely, ensuring it stays within ARTIFACTS_DIR."""
    from wire.security import safe_resolve
    return safe_resolve(artifact_id, ARTIFACTS_DIR)


def _meta_path(artifact_id: str) -> Path:
    return _artifact_path(artifact_id) / "meta.json"


def _load_meta(artifact_id: str) -> dict:
    mp = _meta_path(artifact_id)
    if not mp.exists():
        raise FileNotFoundError(f"Artifact '{artifact_id}' not found.")
    with open(mp) as f:
        return json.load(f)


def _save_meta(artifact_id: str, data: dict):
    mp = _meta_path(artifact_id)
    mp.parent.mkdir(parents=True, exist_ok=True)
    with open(mp, "w") as f:
        json.dump(data, f, indent=2)


def _version_path(artifact_id: str, version: int) -> Path:
    return _artifact_path(artifact_id) / f"v{version:04d}.txt"


def _checksum(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:12]


# ── Artifact types ─────────────────────────────────────────────────────────

ARTIFACT_TYPES = {
    "code":         "Source code in any language",
    "docs":         "Documentation, README, API reference",
    "tests":        "Test suites and test cases",
    "schema":       "Database schemas, JSON schemas, Pydantic models",
    "config":       "Config files, YAML/TOML/JSON settings",
    "diagram":      "Architecture / flow diagrams (Mermaid or ASCII)",
    "report":       "Analysis, audit, or performance reports",
    "plan":         "Project plans, task breakdowns, roadmaps",
    "changelog":    "CHANGELOG entries and release notes",
    "prompt":       "Reusable system prompts and few-shot examples",
    "script":       "Shell / build / deployment scripts",
    "template":     "Code or document templates",
}

# Extensions to suggest for each type
TYPE_EXTENSIONS = {
    "code":      ".py",
    "docs":      ".md",
    "tests":     ".py",
    "schema":    ".json",
    "config":    ".yaml",
    "diagram":   ".md",
    "report":    ".md",
    "plan":      ".md",
    "changelog": ".md",
    "prompt":    ".txt",
    "script":    ".sh",
    "template":  ".txt",
}


# ── ArtifactManager ────────────────────────────────────────────────────────

class ArtifactManager:
    """Create, version, search, and export AI-generated artifacts."""

    # ── Create ─────────────────────────────────────────────────────────────

    def create(self, name: str, prompt: str, artifact_type: str = "code",
               language: str = "", tags: Optional[list] = None, project_id: str = "",
               coder=None) -> dict:
        """Generate an artifact from a prompt and store v1."""
        aid = str(uuid.uuid4())[:12]

        system = self._build_system(artifact_type, language)
        content = coder.generate(prompt, system=system) if coder else f"[No coder] {prompt}"

        meta = {
            "id":           aid,
            "name":         name,
            "type":         artifact_type,
            "language":     language,
            "tags":         tags or [],
            "project_id":   project_id,
            "prompt":       prompt,
            "version":      1,
            "versions":     [{"v": 1, "checksum": _checksum(content), "created_at": _now(), "note": "Initial generation"}],
            "created_at":   _now(),
            "updated_at":   _now(),
        }
        _save_meta(aid, meta)
        _version_path(aid, 1).write_text(content, encoding="utf-8")

        return meta

    # ── Iterate (new version) ──────────────────────────────────────────────

    def iterate(self, artifact_id: str, feedback: str, coder) -> dict:
        """Generate a new version of an artifact based on feedback."""
        meta    = _load_meta(artifact_id)
        current = self.get_content(artifact_id)

        prompt = (
            f"Original prompt: {meta['prompt']}\n\n"
            f"Current version (v{meta['version']}):\n{current}\n\n"
            f"Feedback / changes requested:\n{feedback}\n\n"
            "Produce an improved version addressing the feedback. "
            "Keep everything that is good, change what was requested."
        )
        system = self._build_system(meta["type"], meta.get("language", ""))
        new_content = coder.generate(prompt, system=system)

        new_v = meta["version"] + 1
        _version_path(artifact_id, new_v).write_text(new_content, encoding="utf-8")

        meta["version"] = new_v
        meta["versions"].append({
            "v":          new_v,
            "checksum":   _checksum(new_content),
            "created_at": _now(),
            "note":       feedback[:80],
        })
        meta["updated_at"] = _now()
        _save_meta(artifact_id, meta)

        return meta

    # ── Read ───────────────────────────────────────────────────────────────

    def get_content(self, artifact_id: str, version: Optional[int] = None) -> str:
        meta = _load_meta(artifact_id)
        v    = version or meta["version"]
        vp   = _version_path(artifact_id, v)
        if not vp.exists():
            raise FileNotFoundError(f"Version {v} not found for artifact {artifact_id}.")
        return vp.read_text(encoding="utf-8")

    def list_artifacts(self, query: str = "", artifact_type: str = "",
                       project_id: str = "", tag: str = "") -> list:
        results = []
        base = _artifacts_dir()
        for d in sorted(base.iterdir()):
            mp = d / "meta.json"
            if not mp.exists():
                continue
            try:
                with open(mp) as f:
                    m = json.load(f)
                # Filters
                if artifact_type and m.get("type") != artifact_type:
                    continue
                if project_id and m.get("project_id") != project_id:
                    continue
                if tag and tag not in m.get("tags", []):
                    continue
                if query:
                    q = query.lower()
                    haystack = (m.get("name", "") + " " + m.get("prompt", "") + " " + " ".join(m.get("tags", []))).lower()
                    if q not in haystack:
                        continue
                results.append({
                    "id":         m["id"],
                    "name":       m["name"],
                    "type":       m["type"],
                    "version":    m["version"],
                    "tags":       m.get("tags", []),
                    "project_id": m.get("project_id", ""),
                    "updated_at": m.get("updated_at", ""),
                })
            except Exception:
                pass
        return results

    def get_meta(self, artifact_id: str) -> dict:
        return _load_meta(artifact_id)

    # ── Tag ────────────────────────────────────────────────────────────────

    def add_tag(self, artifact_id: str, tag: str) -> dict:
        meta = _load_meta(artifact_id)
        if tag not in meta["tags"]:
            meta["tags"].append(tag)
            meta["updated_at"] = _now()
            _save_meta(artifact_id, meta)
        return meta

    def remove_tag(self, artifact_id: str, tag: str) -> dict:
        meta = _load_meta(artifact_id)
        meta["tags"] = [t for t in meta["tags"] if t != tag]
        meta["updated_at"] = _now()
        _save_meta(artifact_id, meta)
        return meta

    # ── Attach to project ──────────────────────────────────────────────────

    def attach_to_project(self, artifact_id: str, project_id: str) -> dict:
        meta = _load_meta(artifact_id)
        meta["project_id"] = project_id
        meta["updated_at"] = _now()
        _save_meta(artifact_id, meta)
        return meta

    # ── Export ─────────────────────────────────────────────────────────────

    def export(self, artifact_id: str, output_path: str = "",
               version: Optional[int] = None) -> str:
        meta    = _load_meta(artifact_id)
        content = self.get_content(artifact_id, version)
        v       = version or meta["version"]

        if not output_path:
            ext          = TYPE_EXTENSIONS.get(meta["type"], ".txt")
            safe_name    = meta["name"].lower().replace(" ", "_").replace("/", "_")
            output_path  = f"{safe_name}_v{v}{ext}"

        Path(output_path).write_text(content, encoding="utf-8")
        return output_path

    def export_all(self, project_id: str, output_dir: str = "") -> list:
        """Export all artifacts for a project to a directory."""
        arts    = self.list_artifacts(project_id=project_id)
        out_dir = Path(output_dir or f"artifacts_{project_id}")
        out_dir.mkdir(parents=True, exist_ok=True)
        exported = []
        for a in arts:
            ext      = TYPE_EXTENSIONS.get(a["type"], ".txt")
            safe     = a["name"].lower().replace(" ", "_")
            out_file = out_dir / f"{safe}_v{a['version']}{ext}"
            content  = self.get_content(a["id"])
            out_file.write_text(content, encoding="utf-8")
            exported.append(str(out_file))
        return exported

    # ── Delete ─────────────────────────────────────────────────────────────

    def delete(self, artifact_id: str) -> bool:
        ap = _artifact_path(artifact_id)
        if ap.exists():
            shutil.rmtree(ap)
            return True
        return False

    # ── Diff ───────────────────────────────────────────────────────────────

    def diff(self, artifact_id: str, v1: int, v2: int) -> str:
        """Simple line-by-line diff between two versions."""
        import difflib
        c1 = self.get_content(artifact_id, v1).splitlines(keepends=True)
        c2 = self.get_content(artifact_id, v2).splitlines(keepends=True)
        diff = list(difflib.unified_diff(c1, c2, fromfile=f"v{v1}", tofile=f"v{v2}"))
        return "".join(diff) if diff else "No differences."

    # ── Display ────────────────────────────────────────────────────────────

    def show(self, artifact_id: str, version: Optional[int] = None, preview_lines: int = 40) -> str:
        meta    = _load_meta(artifact_id)
        content = self.get_content(artifact_id, version)
        v       = version or meta["version"]

        lines = [
            f"\n{'═'*60}",
            f"  ARTIFACT: {meta['name']}",
            f"  ID:       {meta['id']}",
            f"  Type:     {meta['type']}{'  Language: ' + meta['language'] if meta.get('language') else ''}",
            f"  Version:  v{v} of {meta['version']}  |  Checksum: {meta['versions'][v-1]['checksum']}",
            f"  Tags:     {', '.join(meta['tags']) or '—'}",
            f"  Project:  {meta['project_id'] or '—'}",
            f"  Updated:  {meta['updated_at'][:19]}",
            f"{'═'*60}",
            "\n--- Version History ---",
        ]
        for vh in meta["versions"]:
            lines.append(f"  v{vh['v']}  {vh['created_at'][:19]}  {vh.get('note','')[:60]}")
        lines.append(f"\n--- Content (v{v}) ---")

        content_lines = content.splitlines()
        if len(content_lines) > preview_lines:
            lines.extend(content_lines[:preview_lines])
            lines.append(f"\n… ({len(content_lines) - preview_lines} more lines — export to see full content)")
        else:
            lines.extend(content_lines)
        return "\n".join(lines)

    # ── Internal ───────────────────────────────────────────────────────────

    def _build_system(self, artifact_type: str, language: str = "") -> str:
        base = {
            "code":      "You are an expert software engineer. Write clean, well-commented, production-ready code.",
            "docs":      "You are a technical writer. Write clear, comprehensive documentation in Markdown.",
            "tests":     "You are a QA engineer. Write thorough, runnable tests with good coverage.",
            "schema":    "You are a data architect. Design clean, well-annotated schemas.",
            "config":    "You are a DevOps engineer. Write clean, commented configuration files.",
            "diagram":   "You are a software architect. Create clear diagrams using Mermaid syntax or ASCII art.",
            "report":    "You are a senior engineer. Write detailed, structured analysis reports.",
            "plan":      "You are a project manager. Create clear, actionable plans with priorities.",
            "changelog": "You are a release engineer. Write clear, conventional changelog entries.",
            "prompt":    "You are a prompt engineer. Write precise, reusable prompts.",
            "script":    "You are a DevOps engineer. Write robust, portable shell scripts with error handling.",
            "template":  "You are a senior developer. Write flexible, well-documented templates.",
        }.get(artifact_type, "You are an expert assistant. Produce high-quality output.")

        if language:
            base += f" Use {language}."
        return base


# ── CLI helpers ─────────────────────────────────────────────────────────────

def cmd_artifact_create(name, prompt, artifact_type="code", language="",
                        tags=None, project_id="", coder=None):
    am = ArtifactManager()
    print(f"\033[94mℹ Generating artifact '{name}' (type: {artifact_type})…\033[0m")
    meta = am.create(name, prompt, artifact_type, language, tags, project_id, coder)
    print(f"\033[92m✓ Artifact created: {meta['name']} (ID: {meta['id']}, v1)\033[0m")
    print(am.show(meta["id"]))
    return meta


def cmd_artifact_list(query="", artifact_type="", project_id="", tag=""):
    am   = ArtifactManager()
    arts = am.list_artifacts(query, artifact_type, project_id, tag)
    if not arts:
        print("No artifacts found.")
        return
    print(f"\n{'ID':<14}{'NAME':<25}{'TYPE':<12}{'VER':<6}{'TAGS':<20}{'UPDATED'}")
    print("─" * 85)
    for a in arts:
        tags = ", ".join(a["tags"][:3]) or "—"
        print(f"{a['id']:<14}{a['name'][:24]:<25}{a['type']:<12}v{a['version']:<5}{tags[:19]:<20}{a['updated_at'][:10]}")
    print(f"\n{len(arts)} artifact(s)")


def cmd_artifact_show(artifact_id, version=None):
    am = ArtifactManager()
    print(am.show(artifact_id, version))


def cmd_artifact_iterate(artifact_id, feedback, coder):
    am = ArtifactManager()
    print(f"\033[94mℹ Generating new version of artifact {artifact_id}…\033[0m")
    meta = am.iterate(artifact_id, feedback, coder)
    print(f"\033[92m✓ Artifact updated to v{meta['version']}\033[0m")
    print(am.show(artifact_id))


def cmd_artifact_export(artifact_id, output_path="", version=None):
    am   = ArtifactManager()
    path = am.export(artifact_id, output_path, version)
    print(f"\033[92m✓ Exported to: {path}\033[0m")


def cmd_artifact_tag(artifact_id, tag):
    am   = ArtifactManager()
    meta = am.add_tag(artifact_id, tag)
    print(f"\033[92m✓ Tag '{tag}' added. Tags: {', '.join(meta['tags'])}\033[0m")


def cmd_artifact_attach(artifact_id, project_id):
    am   = ArtifactManager()
    am.attach_to_project(artifact_id, project_id)
    print(f"\033[92m✓ Artifact {artifact_id} attached to project {project_id}\033[0m")


def cmd_artifact_diff(artifact_id, v1, v2):
    am   = ArtifactManager()
    diff = am.diff(artifact_id, int(v1), int(v2))
    print(diff)


def cmd_artifact_delete(artifact_id):
    am = ArtifactManager()
    ok = am.delete(artifact_id)
    if ok:
        print(f"\033[92m✓ Artifact {artifact_id} deleted.\033[0m")
    else:
        print(f"\033[91m✗ Artifact {artifact_id} not found.\033[0m")


def cmd_artifact_types():
    print("\nAvailable artifact types:")
    for t, desc in ARTIFACT_TYPES.items():
        print(f"  {t:<14} — {desc}")


def cmd_artifact_export_all(project_id, output_dir=""):
    am       = ArtifactManager()
    exported = am.export_all(project_id, output_dir)
    print(f"\033[92m✓ Exported {len(exported)} artifacts:\033[0m")
    for p in exported:
        print(f"  {p}")
