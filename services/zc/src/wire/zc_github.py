"""
zc_github.py — GitHub Integration
AI Model Coder CLI v1.9.1

Connects zAICoder to GitHub via the GitHub REST API (no external SDK —
pure stdlib urllib). Review PRs, triage issues, summarise commit history,
and generate PR descriptions automatically.

CLI flags:
  --gh-review-pr REPO/NUMBER    AI review of a pull request diff
  --gh-triage-issues REPO       Triage open issues and suggest labels/owners
  --gh-summarise-commits REPO   Summarise recent commit history
  --gh-pr-description REPO/N   Generate a PR description from its diff
  --gh-token TOKEN              GitHub personal access token (or GITHUB_TOKEN env var)
  --gh-max-items N              Max issues/commits to process (default: 20)
"""

import os
import urllib.error
import urllib.request
from typing import Optional

import anthropic

from wire.exceptions import AICoderError
from wire.resilience import CircuitBreaker, retry, urlopen_json, urlopen_text
from wire.utils import sampling_kwargs

GITHUB_API = "https://api.github.com"
# Shared across all GitHub call sites in this module (issues, PRs, commits,
# diffs) — they're all the same downstream dependency, so repeated GitHub
# outages/rate-limiting should trip one breaker rather than one per call site.
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)


@retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
def _gh_get(path: str, token: str) -> dict | list:
    url = f"{GITHUB_API}{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ai-coder-cli/1.9.1",
    })
    try:
        return urlopen_json(req, timeout=20)
    except AICoderError as e:
        raise RuntimeError(f"GitHub API error: {e.message}") from e


@retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
def _gh_fetch_diff(diff_url: str, token: str, max_chars: int) -> str:
    """Fetch a PR diff. Was previously inlined (and unretried/unhandled) at
    both of review_pr()'s and generate_pr_description()'s call sites."""
    req = urllib.request.Request(diff_url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.diff",
    })
    try:
        return urlopen_text(req, timeout=30)[:max_chars]
    except AICoderError as e:
        raise RuntimeError(f"GitHub diff fetch error: {e.message}") from e


def _gh_token(explicit: Optional[str]) -> str:
    token = explicit or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        raise ValueError(
            "GitHub token not found. Pass --gh-token or set GITHUB_TOKEN env var. "
            "Create one at https://github.com/settings/tokens (needs 'repo' scope)."
        )
    return token


def _call(client: anthropic.Anthropic, model: str, system: str, user: str,
          max_tokens: int = 3000) -> str:
    resp = client.messages.create(
        model=model, max_tokens=max_tokens,
        **sampling_kwargs(model, temperature=0.3),
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text.strip()


def review_pr(repo: str, pr_number: int,
              gh_token: str, client: anthropic.Anthropic, model: str) -> str:
    pr = _gh_get(f"/repos/{repo}/pulls/{pr_number}", gh_token)
    diff_url = pr.get("diff_url", "")
    diff = _gh_fetch_diff(diff_url, gh_token, 15000)

    context = (
        f"PR #{pr_number}: {pr.get('title', '')}\n"
        f"Author: {pr.get('user', {}).get('login', '')}\n"
        f"Branch: {pr.get('head', {}).get('ref', '')} → {pr.get('base', {}).get('ref', '')}\n"
        f"Body: {(pr.get('body') or '')[:1000]}\n\n"
        f"Diff (truncated to 15k chars):\n{diff}"
    )
    return _call(client, model,
                 "You are a senior software engineer reviewing a pull request. "
                 "Comment on correctness, style, test coverage, and potential issues. "
                 "Be specific: cite file names and line context from the diff.",
                 context)


def triage_issues(repo: str, max_items: int,
                  gh_token: str, client: anthropic.Anthropic, model: str) -> str:
    issues_raw = _gh_get(f"/repos/{repo}/issues?state=open&per_page={max_items}", gh_token)
    if not isinstance(issues_raw, list):
        return f"Unexpected response: {str(issues_raw)[:200]}"
    issues_text = "\n".join(
        f"#{i.get('number')} [{', '.join(l['name'] for l in i.get('labels', []))}] "
        f"{i.get('title', '')} — {(i.get('body') or '')[:200]}"
        for i in issues_raw
    )
    return _call(client, model,
                 "You are a project maintainer triaging a backlog. For each issue: "
                 "suggest a severity (critical/high/medium/low), an appropriate label, "
                 "whether it's a bug/feature/question, and one-sentence resolution advice. "
                 "Format as a concise table.",
                 f"Repository: {repo}\n\nOpen issues:\n{issues_text}")


def summarise_commits(repo: str, max_items: int,
                      gh_token: str, client: anthropic.Anthropic, model: str) -> str:
    commits_raw = _gh_get(f"/repos/{repo}/commits?per_page={max_items}", gh_token)
    if not isinstance(commits_raw, list):
        return f"Unexpected response: {str(commits_raw)[:200]}"
    commits_text = "\n".join(
        f"- [{c['sha'][:7]}] {c['commit']['message'].splitlines()[0]} "
        f"({c['commit']['author']['name']}, {c['commit']['author']['date'][:10]})"
        for c in commits_raw
    )
    return _call(client, model,
                 "You are a technical writer summarising recent development activity. "
                 "Group related commits thematically and highlight breaking changes, "
                 "new features, bug fixes, and dependency updates.",
                 f"Repository: {repo}\n\nRecent commits:\n{commits_text}")


def generate_pr_description(repo: str, pr_number: int,
                             gh_token: str, client: anthropic.Anthropic, model: str) -> str:
    pr = _gh_get(f"/repos/{repo}/pulls/{pr_number}", gh_token)
    diff = _gh_fetch_diff(pr.get("diff_url", ""), gh_token, 12000)
    return _call(client, model,
                 "Write a clear, concise PR description in Markdown. Include: "
                 "## Summary, ## Changes, ## Testing, ## Notes. "
                 "No filler sentences. Return only the Markdown.",
                 f"PR title: {pr.get('title', '')}\nDiff:\n{diff}")


# ── CLI entry points ─────────────────────────────────────────────────────────

def cmd_gh_review_pr(repo_pr: str, gh_token_explicit: Optional[str],
                     api_key: str, model: str):
    repo, _, num = repo_pr.rpartition("/")
    token = _gh_token(gh_token_explicit)
    client = anthropic.Anthropic(api_key=api_key)
    print(f"\n\033[94mReviewing PR #{num} in {repo}\033[0m\n")
    print(review_pr(repo, int(num), token, client, model))


def cmd_gh_triage(repo: str, max_items: int, gh_token_explicit: Optional[str],
                  api_key: str, model: str):
    token = _gh_token(gh_token_explicit)
    client = anthropic.Anthropic(api_key=api_key)
    print(f"\n\033[94mTriaging open issues in {repo}\033[0m\n")
    print(triage_issues(repo, max_items, token, client, model))


def cmd_gh_commits(repo: str, max_items: int, gh_token_explicit: Optional[str],
                   api_key: str, model: str):
    token = _gh_token(gh_token_explicit)
    client = anthropic.Anthropic(api_key=api_key)
    print(f"\n\033[94mCommit summary for {repo}\033[0m\n")
    print(summarise_commits(repo, max_items, token, client, model))


def cmd_gh_pr_description(repo_pr: str, gh_token_explicit: Optional[str],
                           api_key: str, model: str):
    repo, _, num = repo_pr.rpartition("/")
    token = _gh_token(gh_token_explicit)
    client = anthropic.Anthropic(api_key=api_key)
    print(f"\n\033[94mGenerating PR description for #{num} in {repo}\033[0m\n")
    print(generate_pr_description(repo, int(num), token, client, model))
