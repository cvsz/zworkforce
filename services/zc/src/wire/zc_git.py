"""
zc_git.py — AI-powered git integration: commit messages, PR
descriptions, changelogs, diff review, and blame explanations.
AI Model Coder CLI v1.10.0
"""

import subprocess
from typing import Optional

import anthropic

from wire.utils import sampling_kwargs

SYS = ("You are a senior software engineer writing git artifacts. "
       "Be concise, specific, and follow conventional commit conventions where applicable.")


def _git(cmd: str, cwd: str = ".") -> str:
    import shlex
    cmd_args = shlex.split(cmd) if isinstance(cmd, str) else cmd
    r = subprocess.run(cmd_args, shell=False, cwd=cwd, capture_output=True, text=True, timeout=30)
    return r.stdout.strip() or r.stderr.strip()


def _call(api_key: str, model: str, user: str, max_tokens: int = 1024) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model, max_tokens=max_tokens,
        **sampling_kwargs(model, temperature=0.3),
        system=SYS, messages=[{"role": "user", "content": user}])
    return resp.content[0].text.strip()


# ── Core functions ────────────────────────────────────────────────────────────

def staged_diff(cwd: str = ".") -> str:
    diff = _git("git diff --cached", cwd)
    return diff or _git("git diff HEAD", cwd) or "(no changes detected)"


def commit_message(diff: str, api_key: str, model: str,
                   style: str = "conventional") -> str:
    style_note = {
        "conventional": "Use Conventional Commits format (type(scope): short desc).",
        "imperative":   "Use imperative mood (Add X, Fix Y, Remove Z).",
        "detailed":     "Include a subject line and a bullet-point body.",
    }.get(style, "")
    return _call(api_key, model,
        f"{style_note}\nWrite a git commit message for this diff:\n\n{diff}",
        max_tokens=256)


def pr_description(base: str, head: str, cwd: str, api_key: str, model: str) -> str:
    log  = _git(f"git log {base}..{head} --oneline", cwd)
    diff = _git(f"git diff {base}..{head} --stat", cwd)
    return _call(api_key, model,
        f"Write a PR description (## Summary, ## Changes, ## Testing) for a pull "
        f"request from '{head}' into '{base}'.\n\nCommits:\n{log}\n\nFiles changed:\n{diff}",
        max_tokens=1024)


def changelog(since_tag: str, cwd: str, api_key: str, model: str) -> str:
    log = _git(f"git log {since_tag}..HEAD --oneline", cwd)
    if not log: return "(no commits since that tag)"
    return _call(api_key, model,
        f"Generate a Markdown changelog from these commits since {since_tag}. "
        "Group by: Features, Fixes, Docs, Chores.\n\n" + log, max_tokens=1024)


def diff_review(diff: str, api_key: str, model: str) -> str:
    return _call(api_key, model,
        "Review this diff for bugs, style issues, and missing tests. "
        "Be specific — reference exact lines.\n\n" + diff, max_tokens=2048)


def explain_blame(file: str, line_start: int, line_end: int,
                  cwd: str, api_key: str, model: str) -> str:
    blame = _git(f"git log --oneline {file}", cwd)
    try:
        with open(f"{cwd}/{file}") as f:
            code = "\n".join(f.readlines()[line_start-1:line_end])
    except Exception:
        code = "(could not read file)"
    return _call(api_key, model,
        f"Explain the history and purpose of {file} lines {line_start}–{line_end}.\n\n"
        f"Commit history for this file:\n{blame}\n\nCode:\n{code}", max_tokens=512)


# ── CLI commands ──────────────────────────────────────────────────────────────

def cmd_git_commit(api_key: str, model: str, style: str = "conventional",
                   cwd: str = ".", write: bool = False):
    diff = staged_diff(cwd)
    msg  = commit_message(diff, api_key, model, style)
    print(msg)
    if write:
        result = subprocess.run(["git", "commit", "-m", msg], cwd=cwd, capture_output=True, text=True)
        if result.returncode == 0: print("\n✓ Committed.")
        else: print(f"\n✗ Commit failed:\n{result.stderr}")


def cmd_git_pr(base: str, head: str, api_key: str, model: str, cwd: str = "."):
    print(pr_description(base, head, cwd, api_key, model))


def cmd_git_changelog(since_tag: str, api_key: str, model: str,
                      cwd: str = ".", output: Optional[str] = None):
    md = changelog(since_tag, cwd, api_key, model)
    if output:
        from pathlib import Path; Path(output).write_text(md)
        print(f"✓ Changelog saved to {output}")
    else:
        print(md)


def cmd_git_review(api_key: str, model: str, cwd: str = "."):
    diff = staged_diff(cwd)
    print(diff_review(diff, api_key, model))


def cmd_git_blame_explain(file: str, line_start: int, line_end: int,
                          api_key: str, model: str, cwd: str = "."):
    print(explain_blame(file, line_start, line_end, cwd, api_key, model))
