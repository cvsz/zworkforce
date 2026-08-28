"""
zc_skills_api.py — Agent Skills API (platform, skill_id-based)
AI Model Coder CLI v1.15.0

This is a *different* feature from zAICoder's local skill loader in
zc_code.py (`SkillsRegistry`, `.zc/skills/<name>/SKILL.md`). That
loader reads a directory on the caller's own machine and stuffs SKILL.md
content into the system prompt/context itself — a client-side convention.

This module is the platform-level counterpart: Anthropic-provided
pre-built Skills (PowerPoint, Excel, Word, PDF generation/editing) plus an
account's own custom Skills, referenced by `skill_id` (+ optional
`version`) in a Messages API request's `container.skills` list and loaded
server-side with progressive disclosure — the model only pulls in a
skill's content as needed rather than the whole thing up front. This
requires the code-execution tool container, since Skills are executed
inside it.

Confirmed against platform.zc.com/docs (checked 2026-07-04): up to 8
skills per request, referenced by type ("anthropic" or "custom") + id (+
version for custom skills). `zc_excel.py` / `zc_powerpoint.py`
also reimplement their formats by hand (pandas/openpyxl, python-pptx)
with a denylist-guarded exec loop — a real, working, already-tested
alternative, just not Anthropic's own maintained implementation — so
those two route through this API as an opt-in (--excel-native /
--pptx-native) alongside the hand-rolled default. `zc_word.py` /
`zc_pdf.py` have no such hand-rolled path to fall back to, so
--docx-native / --pdf-native are Skills-only for those two formats.

CLI flags:
  --skills-list             List Anthropic-provided pre-built Skills known to this CLI
  --skills-info ID          Show details for one skill_id (info-only, no API call —
                            mirrors zc_fable5.py's cmd_fable5_info pattern)

v1.16.0 addition — native document routing (--excel-native / --pptx-native),
extended in v1.33.0 to --docx-native / --pdf-native: call_with_skills_turn()
/ build_user_content() / extract_output_file_ids() below are the pieces
zc_excel.py, zc_powerpoint.py, zc_word.py, and zc_pdf.py
all use to run their chat loops entirely server-side through this API
(xlsx/pptx/docx/pdf Skills in a code-execution container). Confirmed
against platform.zc.com/docs/en/build-with-zc/skills-guide
(checked 2026-07-04): container.id reuse for multi-turn, container_upload
content blocks for attaching files, files-api-2025-04-14 beta whenever a
file is attached or downloaded, and generated file_id values surfacing on
either a code_execution_tool_result or bash_code_execution_tool_result
block (Skills can run their work through either the Python or bash
code-execution tool, so callers need to check both).
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from wire.exceptions import AICoderError
from wire.resilience import CircuitBreaker, retry, urlopen_json

MESSAGES_ENDPOINT = "https://api.anthropic.com/v1/messages"
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)

# Skills require the code-execution tool container, gated behind its own
# beta header, plus the Skills-specific beta for the `container.skills`
# field itself.
CODE_EXECUTION_BETA = "code-execution-2025-08-25"
SKILLS_BETA = "skills-2025-10-02"

# Only needed when a turn attaches or downloads a file (container_upload
# blocks / Files API). Mirrors zc_files.py's BETA_HEADER constant —
# kept as a separate constant here rather than importing that module, to
# avoid a hard dependency from this module on zc_files.py for callers
# that only use text-only Skills calls.
FILES_API_BETA = "files-api-2025-04-14"

# Anthropic-provided pre-built Skills, per platform.zc.com/docs (checked
# 2026-07-04). This mirrors zc_code.py's ANTHROPIC_MANAGED_SKILLS dict
# intentionally rather than importing it: that dict describes zAICoder's
# *local* skill-name convention (a filesystem concept), while this one
# describes the platform's `skill_id` values for the Messages API (a wire
# format). They happen to line up 1:1 for the four pre-built skills today,
# but are different concepts, so keeping them as separate small constants
# avoids coupling two modules that don't actually share an implementation.
PREBUILT_SKILLS = {
    "pptx": {"skill_id": "pptx", "description": "Create and edit PowerPoint presentations"},
    "xlsx": {"skill_id": "xlsx", "description": "Create and edit Excel spreadsheets"},
    "docx": {"skill_id": "docx", "description": "Create and edit Word documents"},
    "pdf":  {"skill_id": "pdf",  "description": "Create, fill, and edit PDF files"},
}


@dataclass
class SkillRef:
    """One entry in a Messages request's container.skills list.

    type: "anthropic" for a pre-built skill (see PREBUILT_SKILLS), "custom"
    for one uploaded to your own organization.
    version: required for custom skills; optional (defaults to latest) for
    anthropic-type skills.
    """
    skill_id: str
    type: str = "anthropic"
    version: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"type": self.type, "skill_id": self.skill_id}
        if self.version:
            d["version"] = self.version
        return d

    @classmethod
    def prebuilt(cls, name: str) -> "SkillRef":
        """Build a SkillRef for one of the four pre-built skills by short
        name (pptx/xlsx/docx/pdf), raising a clear error otherwise."""
        info = PREBUILT_SKILLS.get(name)
        if not info:
            raise ValueError(
                f"Unknown pre-built skill {name!r}. Known: {', '.join(PREBUILT_SKILLS)}"
            )
        return cls(skill_id=info["skill_id"], type="anthropic")


def build_container_skills(skills: list) -> dict:
    """Build the container.skills block for a Messages API request from a
    list of SkillRef (or dicts already in wire format). Up to 8 per
    request, per the documented limit."""
    if len(skills) > 8:
        raise ValueError(f"Skills API allows at most 8 skills per request; got {len(skills)}.")
    refs = [s.to_dict() if isinstance(s, SkillRef) else s for s in skills]
    return {"skills": refs}


class SkillsApiClient:
    """Thin Messages API client for calling with Skills attached, following
    the same _post() pattern used throughout this project's zc_*.py
    modules for consistency."""

    def __init__(self, api_key: str, model: str = "zc-xxx", max_tokens: int = 4096):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict, betas: list) -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": ",".join(betas),
        }
        req = urllib.request.Request(
            MESSAGES_ENDPOINT, data=json.dumps(payload).encode(),
            headers=headers, method="POST",
        )
        return urlopen_json(req, timeout=300)

    def _post(self, payload: dict, betas: list) -> dict:
        try:
            return self._call(payload, betas)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    def call_with_skills(self, prompt: str, skills: list,
                         system: Optional[str] = None) -> dict:
        """Call the model with a code-execution container carrying the
        given skills (list of SkillRef or short pre-built names like
        'pptx'). Returns the raw parsed response dict."""
        refs = [s if isinstance(s, SkillRef) else SkillRef.prebuilt(s) for s in skills]
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [{"type": "code_execution_20250825", "name": "code_execution"}],
            "container": build_container_skills(refs),
        }
        if system:
            payload["system"] = system
        return self._post(payload, betas=[CODE_EXECUTION_BETA, SKILLS_BETA])

    def call_with_skills_turn(self, messages: list, skills: list,
                              container_id: Optional[str] = None,
                              has_file_uploads: bool = False,
                              system: Optional[str] = None) -> dict:
        """Multi-turn variant of call_with_skills, for chat-style callers
        (zc_excel.py / zc_powerpoint.py --*-native modes) that need
        to keep working in the same container across several turns rather
        than firing one-off requests.

        messages: the full running conversation (caller-maintained), each
        entry {"role": ..., "content": ...} — content can be a plain
        string or a list of content blocks (use build_user_content() to
        attach files via container_upload).
        container_id: pass container.id from a previous response to reuse
        its container (and therefore anything the model already wrote to
        disk there) instead of starting fresh.
        has_file_uploads: set True on any turn whose messages contain a
        container_upload block, so the files-api beta gets attached —
        required by the API whenever a file is being sent into or
        expected out of the container.
        """
        refs = [s if isinstance(s, SkillRef) else SkillRef.prebuilt(s) for s in skills]
        container = build_container_skills(refs)
        if container_id:
            container["id"] = container_id
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
            "tools": [{"type": "code_execution_20250825", "name": "code_execution"}],
            "container": container,
        }
        if system:
            payload["system"] = system
        betas = [CODE_EXECUTION_BETA, SKILLS_BETA]
        if has_file_uploads:
            betas.append(FILES_API_BETA)
        return self._post(payload, betas=betas)


def build_user_content(text: str, file_ids: Optional[list] = None) -> list:
    """Build a user-turn content block list: the text plus a
    container_upload block per file_id, per the documented shape for
    attaching Files-API uploads to a code-execution container."""
    content = [{"type": "text", "text": text}]
    for fid in (file_ids or []):
        content.append({"type": "container_upload", "file_id": fid})
    return content


def extract_output_file_ids(data: dict) -> list:
    """Walk a Skills-API response for file_id values zAICoder generated
    during code execution. Per Anthropic's own extraction example (docs
    checked 2026-07-04), a Skill's work can come back on either a
    'code_execution_tool_result' block (Python) or a
    'bash_code_execution_tool_result' block (bash) — this checks both
    rather than assuming one, and tolerates the inner result being either
    a single dict or an already-flattened list, since that nesting isn't
    fully pinned down across SDK versions. Returns file_ids in the order
    encountered; callers wanting "the newest file" should take the last
    entry."""
    file_ids = []
    for block in data.get("content", []) or []:
        if block.get("type") not in ("code_execution_tool_result", "bash_code_execution_tool_result"):
            continue
        result = block.get("content")
        if isinstance(result, dict):
            items = result.get("content", [])
        elif isinstance(result, list):
            items = result
        else:
            items = []
        for item in items:
            fid = item.get("file_id") if isinstance(item, dict) else None
            if fid:
                file_ids.append(fid)
    return file_ids


def list_skills() -> list:
    """List the pre-built Skills this CLI knows about. This is a local,
    static list (see PREBUILT_SKILLS docstring) rather than a live API
    call — there is no documented 'list custom skills' endpoint distinct
    from managing them in the Console, so this covers the pre-built set
    only. Returns a list of {skill_id, type, description} dicts."""
    return [
        {"skill_id": info["skill_id"], "type": "anthropic", "description": info["description"]}
        for info in PREBUILT_SKILLS.values()
    ]


def cmd_skills_list():
    print("\n\033[94mAgent Skills (platform API, skill_id-based)\033[0m")
    print("\033[93m⚠ Pre-built skills only — custom skills are managed in the Console,\033[0m")
    print("\033[93m  not listed by a documented API endpoint.\033[0m\n")
    for s in list_skills():
        print(f"  \033[1m{s['skill_id']}\033[0m  ({s['type']})")
        print(f"    {s['description']}")
    print()


def cmd_skills_info(skill_id: str):
    info = PREBUILT_SKILLS.get(skill_id)
    if not info:
        print(f"\033[91m✗ Unknown skill_id: {skill_id}\033[0m")
        print(f"  Known pre-built skills: {', '.join(PREBUILT_SKILLS)}")
        return None
    print(f"\n\033[94m{info['skill_id']}\033[0m (type: anthropic)")
    print(f"  {info['description']}")
    print(f"  Reference in a request as: "
         f"SkillRef.prebuilt({skill_id!r}) -> {SkillRef.prebuilt(skill_id).to_dict()}")
    print(f"  Requires beta headers: {CODE_EXECUTION_BETA}, {SKILLS_BETA}\n")
    return info