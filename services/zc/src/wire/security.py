"""
security.py — Input validation and security controls

Centralizes the checks that were previously either missing or duplicated
ad hoc across zc_files.py, zc_code_exec.py, zc_sandbox.py,
projects.py, and artifacts.py — every module that takes a user-supplied
path or writes files to disk. Import from here instead of re-implementing
path checks locally.

Threat model covered:
- Path traversal / arbitrary file read-write (`../../etc/passwd`, absolute
  paths escaping an intended project/artifact directory, symlink escapes).
- Secrets accidentally echoed back to the user or written to disk (API
  keys pasted into a prompt, `.env` contents included in a file upload).
- Oversized input (a multi-GB file handed to --file / --file-upload
  exhausting memory before any API call is made).
- Unvalidated shell/URL schemes reaching url-fetch-style tools.

Not covered here (out of scope for a CLI security module): sandboxing of
arbitrary code the model asks to execute — see zc_sandbox.py, which
already delegates that to Anthropic's hosted code-execution tool rather
than running anything locally.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from wire.exceptions import SecurityError, ValidationError

# ── Path safety ──────────────────────────────────────────────────────────

MAX_FILE_SIZE_BYTES = int(os.getenv("wire_MAX_FILE_SIZE_BYTES", 25 * 1024 * 1024))  # 25 MB default


def safe_resolve(path: str | os.PathLike, base_dir: str | os.PathLike) -> Path:
    """Resolve `path` (possibly relative) against `base_dir` and guarantee
    the result stays inside `base_dir`. Raises SecurityError otherwise.

    Use this anywhere a user-controlled path (a CLI arg, a project/artifact
    name, an agent-produced filename) is about to be opened, written, or
    deleted, e.g.:

        target = safe_resolve(args.project_export, PROJECTS_DIR)
        target.write_text(data)
    """
    base = Path(base_dir).expanduser().resolve()
    candidate = (base / path).resolve() if not os.path.isabs(str(path)) else Path(path).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise SecurityError(
            "Path escapes the allowed base directory",
            details={"path": str(path), "base_dir": str(base)},
        )
    return candidate


def check_file_size(path: str | os.PathLike, max_bytes: int = MAX_FILE_SIZE_BYTES) -> None:
    size = os.path.getsize(path)
    if size > max_bytes:
        raise ValidationError(
            f"File too large ({size} bytes > {max_bytes} byte limit)",
            details={"path": str(path), "size": size, "limit": max_bytes},
        )


# ── Secret detection ─────────────────────────────────────────────────────

_SECRET_LIKE = re.compile(r"sk-ant-[A-Za-z0-9\-_]{10,}")


def contains_secret(text: str) -> bool:
    return bool(text) and bool(_SECRET_LIKE.search(text))


def assert_no_secret(text: str, *, context: str = "input") -> None:
    """Raise if `text` looks like it contains a live API key. Call before
    writing user/model-generated content to a file that might get committed
    or shared (artifacts.py exports, project files, etc)."""
    if contains_secret(text):
        raise SecurityError(f"Refusing to write {context}: looks like it contains an API key")


# ── URL / scheme validation ──────────────────────────────────────────────

_ALLOWED_SCHEMES = ("https",)


def validate_url(url: str, *, allowed_schemes: tuple[str, ...] = _ALLOWED_SCHEMES) -> None:
    """Reject non-https schemes (file://, ftp://, javascript:, data: etc.)
    before handing a URL to any fetch/download code path."""
    scheme = url.split("://", 1)[0].lower() if "://" in url else ""
    if scheme not in allowed_schemes:
        raise SecurityError(f"URL scheme '{scheme or '(none)'}' is not allowed", details={"url": url})


# ── Generic input validation ─────────────────────────────────────────────

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._\- ]{1,200}$")


def validate_name(name: str, *, field: str = "name") -> str:
    """Validate a user-supplied identifier used to build a filesystem path
    (project name, artifact name, skill name). Rejects path separators,
    null bytes, and anything outside a conservative allow-list so it's
    always safe to join onto a base directory."""
    if not name or not _SAFE_NAME.match(name):
        raise ValidationError(
            f"Invalid {field}: only letters, numbers, spaces, '.', '_', '-' are allowed",
            details={field: name},
        )
    if ".." in name or "/" in name or "\\" in name:
        raise ValidationError(f"Invalid {field}: path separators are not allowed", details={field: name})
    return name


def env_flag(name: str, default: bool = False) -> bool:
    """Parse a boolean environment variable consistently across the
    codebase instead of ad hoc `os.getenv(...) == "1"` checks."""
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")
