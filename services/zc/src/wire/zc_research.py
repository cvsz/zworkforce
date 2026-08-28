"""
zc_research.py — Deep Research: plan sub-questions, gather
findings (grounded in URLs via the http_get tool when provided),
then synthesize into a cited Markdown report.
AI Model Coder CLI v1.10.0
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import anthropic

from wire.resilience import raise_for_http_error, retry
from wire.utils import sampling_kwargs

SYS_PLAN  = "You are a research planning assistant. Output only valid JSON."
SYS_ANAL  = "You are a careful research analyst. Be precise. Flag uncertainty."
SYS_SYNTH = "You are a research synthesis expert. Connect ideas, note tensions."


@dataclass
class SubQ:
    question:  str
    findings:  list[str] = field(default_factory=list)
    sources:   list[str] = field(default_factory=list)
    answered:  bool = False


@dataclass
class Report:
    topic:        str
    sub_questions: list[SubQ]
    synthesis:    str = ""
    created:      str = field(default_factory=lambda: datetime.now().isoformat())

    def to_markdown(self) -> str:
        lines = [f"# Research Report: {self.topic}",
                 f"_Generated: {self.created}_\n",
                 f"## Summary\n{self.synthesis}\n",
                 "## Sub-Questions Explored"]
        for i, sq in enumerate(self.sub_questions, 1):
            lines.append(f"\n### {i}. {sq.question}")
            for f in sq.findings: lines.append(f"- {f}")
            if sq.sources: lines.append("Sources: " + ", ".join(sq.sources))
        return "\n".join(lines)


class DeepResearchAgent:
    def __init__(self, api_key: str, model: str = "zc-xxx"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model  = model

    def _call(self, system: str, user: str, max_tokens: int = 2048) -> str:
        r = self.client.messages.create(
            model=self.model, max_tokens=max_tokens,
            **sampling_kwargs(self.model, temperature=0.35),
            system=system, messages=[{"role": "user", "content": user}])
        return r.content[0].text

    def _fetch(self, url: str) -> str:
        try:
            return self._fetch_retrying(url)
        except Exception as e:
            return f"[fetch failed: {e}]"

    # No CircuitBreaker here deliberately: each call targets a different,
    # unrelated third-party URL supplied by the caller, not one fixed
    # downstream dependency — a shared breaker would trip on unrelated dead
    # links and start short-circuiting fetches to sites that are fine.
    @retry(max_attempts=2, base_delay=1.0, max_delay=5.0)
    def _fetch_retrying(self, url: str) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": "ai-coder-research/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="replace")[:4000]
        except (urllib.error.HTTPError, TimeoutError, ConnectionError, OSError) as e:
            raise_for_http_error(e)

    def plan(self, topic: str, depth: int = 4) -> list[SubQ]:
        raw = self._call(SYS_PLAN,
            f"Break '{topic}' into exactly {depth} focused, non-overlapping research "
            "sub-questions. Return ONLY a JSON array of strings, nothing else.")
        cleaned = raw.strip()
        if cleaned.startswith("```"): cleaned = "\n".join(cleaned.split("\n")[1:-1])
        try:
            qs = json.loads(cleaned)
        except json.JSONDecodeError:
            qs = [l.lstrip("-· ").strip() for l in raw.splitlines() if l.strip()][:depth]
        return [SubQ(question=q) for q in qs[:depth]]

    def gather(self, sq: SubQ, source_urls: Optional[list[str]] = None) -> SubQ:
        ctx_parts = []
        for url in (source_urls or []):
            body = self._fetch(url)
            ctx_parts.append(f"[{url}]\n{body}")
            sq.sources.append(url)
        ctx = "\n\n".join(ctx_parts)
        raw = self._call(SYS_ANAL,
            f"Answer this research sub-question thoroughly.\n"
            f"Sub-question: {sq.question}\n\n"
            + (f"Source material:\n{ctx}\n\n" if ctx else
               "(No sources — answer from knowledge; flag claims that need verification.)\n\n")
            + "Return 3–6 concise bullet-point findings.")
        sq.findings = [l.lstrip("-· ").strip() for l in raw.splitlines() if l.strip()]
        sq.answered = True
        return sq

    def synthesize(self, topic: str, sqs: list[SubQ]) -> str:
        block = "\n\n".join(
            f"Q: {sq.question}\n" + "\n".join(f"- {f}" for f in sq.findings)
            for sq in sqs)
        return self._call(SYS_SYNTH,
            f'Synthesize these findings on "{topic}" into 4–8 coherent sentences '
            "that connect sub-questions rather than list them. Note tensions or gaps.\n\n"
            + block, max_tokens=1024)

    def run(self, topic: str, depth: int = 4,
            source_urls: Optional[list[str]] = None) -> Report:
        sqs = self.plan(topic, depth)
        for sq in sqs: self.gather(sq, source_urls)
        synthesis = self.synthesize(topic, sqs)
        return Report(topic=topic, sub_questions=sqs, synthesis=synthesis)


def cmd_research(topic: str, api_key: str, model: str,
                 depth: int = 4, source_urls: Optional[list[str]] = None,
                 output: Optional[str] = None):
    print(f"🔎 Deep Research: {topic!r}  (depth={depth})\n")
    agent  = DeepResearchAgent(api_key=api_key, model=model)
    report = agent.run(topic, depth=depth, source_urls=source_urls)
    md     = report.to_markdown()
    if output:
        from pathlib import Path
        Path(output).write_text(md)
        print(f"✓ Report saved to {output}")
    else:
        print(md)
