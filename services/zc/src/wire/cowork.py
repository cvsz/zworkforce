"""
cowork.py — zAICoder Cowork (All Features)
AI Model Coder CLI v1.8.0

Cowork is zAICoder's autonomous multi-step task execution mode.
Hand off complex tasks and zAICoder breaks them down, executes each step,
uses tools, iterates, and delivers a complete result.

Features modelled on zAICoder Cowork (zc.ai/cowork):
  • Deep Research       — multi-source research with synthesis
  • Writing Assistant   — draft, edit, iterate long-form content
  • Data Analysis       — analyse data files and generate insights
  • Code Review         — full codebase review with structured report
  • Project Planning    — break down complex projects into plans
  • Competitive Intel   — research and compare topics
  • Document Summary    — summarise + QA from large documents
  • Brainstorm          — ideate and evaluate multiple angles
  • Translate & Adapt   — translate with cultural adaptation
  • Task Automation     — multi-step task planning and execution

CLI flags:
  --cowork TASK_TYPE    Run a cowork task type
  --cowork-prompt TEXT  Task description (required with --cowork)
  --cowork-files FILES  Attach files to the cowork task
  --cowork-depth N      Depth of research/analysis (1-5, default 3)
  --cowork-format FMT   Output format: markdown|json|outline|bullets
  --cowork-list         List all cowork task types
"""

import json
import urllib.error
import urllib.request
from pathlib import Path

from wire.exceptions import AICoderError
from wire.resilience import CircuitBreaker, retry, urlopen_json
from typing import Optional

ENDPOINT = "https://api.anthropic.com/v1/messages"
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)


# ── Task type registry ─────────────────────────────────────────────────────

COWORK_TASKS = {
    "research": {
        "name":        "Deep Research",
        "description": "Multi-angle research with source synthesis and structured report",
        "icon":        "🔬",
    },
    "write": {
        "name":        "Writing Assistant",
        "description": "Draft, structure, and polish long-form content",
        "icon":        "✍️",
    },
    "analyse": {
        "name":        "Data Analysis",
        "description": "Analyse data files, generate insights, create summaries",
        "icon":        "📊",
    },
    "review": {
        "name":        "Code Review",
        "description": "Full codebase review: quality, security, performance, tests",
        "icon":        "🔍",
    },
    "plan": {
        "name":        "Project Planning",
        "description": "Break complex goals into structured plans with timelines",
        "icon":        "📋",
    },
    "compare": {
        "name":        "Competitive Intel",
        "description": "Compare options, products, or approaches with pros/cons",
        "icon":        "⚖️",
    },
    "summarise": {
        "name":        "Document Summary",
        "description": "Summarise large documents with key points and Q&A",
        "icon":        "📄",
    },
    "brainstorm": {
        "name":        "Brainstorm",
        "description": "Generate, evaluate, and rank creative ideas",
        "icon":        "💡",
    },
    "translate": {
        "name":        "Translate & Adapt",
        "description": "Translate content with cultural and tonal adaptation",
        "icon":        "🌐",
    },
    "automate": {
        "name":        "Task Automation",
        "description": "Plan and execute multi-step automation workflows",
        "icon":        "⚙️",
    },
    "debug": {
        "name":        "Deep Debug",
        "description": "Systematic debugging: root cause analysis + fix",
        "icon":        "🐛",
    },
    "architect": {
        "name":        "System Architecture",
        "description": "Design system architectures with diagrams and decisions",
        "icon":        "🏗️",
    },
}


# ── System prompts per task type ───────────────────────────────────────────

SYSTEM_PROMPTS = {
    "research": """You are an expert research analyst. Your task is deep, multi-angle research.

WORKFLOW:
1. SCOPE — Clarify what exactly is being researched and why
2. ANGLES — Identify 4-6 distinct research angles or sub-topics
3. FINDINGS — For each angle, provide detailed findings with key facts
4. SYNTHESIS — Synthesise across angles to surface patterns and insights
5. CONCLUSION — Provide clear, actionable conclusions
6. GAPS — Note what is unknown or would require further research

Output as a structured research report. Be thorough, nuanced, and evidence-based.""",

    "write": """You are a world-class writer and editor. Your task is producing excellent written content.

WORKFLOW:
1. AUDIENCE — Identify the target audience and appropriate tone
2. STRUCTURE — Plan the outline and flow before writing
3. DRAFT — Write a complete, polished draft
4. STRENGTHEN — Identify and fix weak sections
5. POLISH — Ensure consistency, flow, and impact

Produce complete, publication-ready content.""",

    "analyse": """You are a senior data analyst. Your task is extracting actionable insights from data.

WORKFLOW:
1. UNDERSTAND — What does this data represent? What are we measuring?
2. CLEAN — Note any data quality issues
3. EXPLORE — Key statistics, distributions, patterns
4. INSIGHTS — What does this tell us? What's surprising?
5. RECOMMENDATIONS — What actions follow from the analysis?

Be precise with numbers. Support claims with evidence from the data.""",

    "review": """You are a senior software engineer conducting a thorough code review.

WORKFLOW:
1. OVERVIEW — What does this code do? Architecture summary
2. QUALITY — Readability, maintainability, style issues
3. CORRECTNESS — Bugs, edge cases, logic errors
4. SECURITY — Vulnerabilities, injection risks, auth issues
5. PERFORMANCE — Bottlenecks, inefficiencies
6. TESTS — Coverage gaps, missing tests
7. RECOMMENDATIONS — Prioritised list of changes

Be specific: cite line numbers or function names where possible.""",

    "plan": """You are an expert project manager and strategist.

WORKFLOW:
1. GOAL — Clarify the objective and success criteria
2. BREAKDOWN — Decompose into phases and milestones
3. TASKS — Detail specific tasks per phase with owners and estimates
4. RISKS — Identify risks and mitigation strategies
5. DEPENDENCIES — Map task dependencies
6. TIMELINE — Realistic timeline with buffer
7. DEFINITION OF DONE — How do we know it's complete?

Produce an actionable, realistic plan.""",

    "compare": """You are a strategic analyst specialising in competitive comparison.

WORKFLOW:
1. CRITERIA — Define the comparison dimensions
2. OPTIONS — Describe each option fairly and completely
3. ANALYSIS — Score/compare each option on each dimension
4. MATRIX — Build a comparison matrix
5. RECOMMENDATION — Clear recommendation with rationale
6. CAVEATS — What assumptions were made? What could change the answer?

Be balanced: find genuine strengths and weaknesses in each option.""",

    "summarise": """You are an expert at distilling complex information.

WORKFLOW:
1. KEY POINTS — The 5-7 most important ideas
2. STRUCTURE — How the document is organised
3. MAIN ARGUMENTS — Core arguments or claims
4. EVIDENCE — Key evidence or data cited
5. CONCLUSIONS — What the document concludes
6. IMPLICATIONS — Why this matters / what follows from it

Then be available for Q&A on the document.""",

    "brainstorm": """You are a creative strategist and idea generator.

WORKFLOW:
1. FRAME — Clarify the problem or opportunity
2. DIVERGE — Generate 10-15 diverse ideas without judgement
3. EXPLORE — Develop the most promising 3-5 ideas further
4. EVALUATE — Assess each on feasibility, impact, novelty
5. SYNTHESISE — Combine ideas where useful
6. RANK — Recommend top 3 with clear rationale

Be genuinely creative. Include unconventional ideas.""",

    "translate": """You are a professional translator and cultural adaptation specialist.

WORKFLOW:
1. ANALYSE SOURCE — Tone, register, cultural references, idioms
2. TRANSLATE — Accurate translation preserving meaning
3. ADAPT — Adjust cultural references, idioms, and examples for target audience
4. REVIEW — Check for unnatural phrasing or lost nuance
5. NOTES — Highlight any translation choices that required judgement

Produce a translation that reads naturally in the target language.""",

    "automate": """You are an automation architect and workflow designer.

WORKFLOW:
1. UNDERSTAND — What process needs automating? What's the current state?
2. MAP — Map the current manual workflow step by step
3. IDENTIFY — Find automation opportunities and the right tools
4. DESIGN — Design the automated workflow
5. IMPLEMENT — Write the automation code or configuration
6. TEST — Outline how to test and validate
7. MAINTAIN — Note what ongoing maintenance is needed""",

    "debug": """You are a senior debugging specialist.

WORKFLOW:
1. REPRODUCE — Confirm understanding of the bug/issue
2. HYPOTHESES — List 3-5 possible root causes
3. ELIMINATE — Systematically rule out causes
4. ROOT CAUSE — Identify the actual root cause with evidence
5. FIX — Implement the fix
6. VERIFY — Explain how to verify the fix works
7. PREVENT — How to prevent recurrence

Be systematic. Show your reasoning.""",

    "architect": """You are a principal software architect.

WORKFLOW:
1. REQUIREMENTS — Functional and non-functional requirements
2. CONSTRAINTS — Technology, team, timeline, budget constraints
3. OPTIONS — 2-3 architectural approaches with trade-offs
4. RECOMMENDATION — Recommended architecture with rationale
5. COMPONENTS — Detailed component breakdown
6. DATA FLOW — How data moves through the system
7. DIAGRAM — ASCII architecture diagram
8. RISKS — Technical risks and mitigations
9. ROADMAP — Implementation order and phases""",
}


# ── CoworkAgent ────────────────────────────────────────────────────────────

class CoworkAgent:
    """Autonomous multi-step task executor."""

    def __init__(self, api_key: str, model: str = "zc-xxx",
                 max_tokens: int = 8192):
        self.api_key    = api_key
        self.model      = model
        self.max_tokens = max_tokens

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict) -> dict:
        headers = {
            "Content-Type":      "application/json",
            "x-api-key":         self.api_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        return urlopen_json(req, timeout=300)

    def _post(self, payload: dict) -> dict:
        try:
            return self._call(payload)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    def run(
        self,
        task_type:   str,
        prompt:      str,
        files: Optional[list[str]] = None,
        depth:       int = 3,
        output_fmt:  str = "markdown",
        stream_progress: bool = True,
    ) -> dict:
        """Execute a Cowork task. Returns {"output": str, "steps": list, "usage": dict}"""
        task_type = task_type.lower()
        if task_type not in COWORK_TASKS:
            return {"output": f"[ERROR] Unknown task type: {task_type}. Use --cowork-list.", "steps": []}

        task = COWORK_TASKS[task_type]
        sys_prompt = SYSTEM_PROMPTS.get(task_type, "You are an expert assistant.")

        # Attach files
        file_content = ""
        for fp in (files or []):
            try:
                text = Path(fp).read_text()[:12000]
                file_content += f"\n\n--- File: {fp} ---\n{text}\n"
            except Exception as e:
                file_content += f"\n[Could not read {fp}: {e}]"

        # Build depth instruction
        depth_map = {
            1: "Provide a concise focused response.",
            2: "Provide a thorough response covering the main points.",
            3: "Provide a comprehensive, detailed response.",
            4: "Provide an exhaustive, deeply detailed response.",
            5: "Provide the most thorough analysis possible, leaving nothing out.",
        }
        depth_instr = depth_map.get(depth, depth_map[3])

        # Format instruction
        fmt_map = {
            "markdown": "Format output as clean Markdown with headers.",
            "json":     "Output as a valid JSON object with logical keys.",
            "outline":  "Format as a structured outline with numbered sections.",
            "bullets":  "Format as concise bullet points.",
        }
        fmt_instr = fmt_map.get(output_fmt, fmt_map["markdown"])

        full_prompt = (
            f"TASK: {prompt}"
            + (f"\n\nATTACHED FILES:{file_content}" if file_content else "")
            + f"\n\nDEPTH: {depth_instr}"
            + f"\nFORMAT: {fmt_instr}"
        )

        if stream_progress:
            print(f"\n{task['icon']} \033[94m{task['name']}\033[0m")
            print(f"  Depth: {depth}/5  |  Format: {output_fmt}\n")
            print(f"\033[90m{'─'*50}\033[0m\n")

        payload = {
            "model":      self.model,
            "max_tokens": self.max_tokens,
            "system":     sys_prompt,
            "messages":   [{"role": "user", "content": full_prompt}],
        }

        data = self._post(payload)
        if "error" in data:
            return {"output": f"[ERROR] {data['error']}", "steps": [], "usage": {}}

        output = "".join(
            b.get("text", "") for b in data.get("content", [])
            if b.get("type") == "text"
        )
        usage  = data.get("usage", {})

        return {
            "output":    output,
            "task_type": task_type,
            "task_name": task["name"],
            "steps":     [],
            "usage":     usage,
        }

    # ── Multi-turn iterative cowork ────────────────────────────────────────

    def iterate(
        self,
        task_type: str,
        initial_prompt: str,
        follow_ups: list[str],
        files: Optional[list[str]] = None,
    ) -> list[str]:
        """
        Multi-turn cowork session: initial task + follow-up refinements.
        Returns list of responses (one per turn).
        """
        sys_prompt = SYSTEM_PROMPTS.get(task_type, "You are an expert assistant.")
        messages   = []
        responses  = []

        # File content once
        file_content = ""
        for fp in (files or []):
            try:
                file_content += f"\n\n--- {fp} ---\n{Path(fp).read_text()[:6000]}"
            except Exception:
                pass

        first = initial_prompt
        if file_content:
            first += f"\n\nATTACHED:{file_content}"

        for _i, user_msg in enumerate([first] + follow_ups):
            messages.append({"role": "user", "content": user_msg})
            payload = {
                "model":      self.model,
                "max_tokens": self.max_tokens,
                "system":     sys_prompt,
                "messages":   messages,
            }
            data = self._post(payload)
            if "error" in data:
                responses.append(f"[ERROR] {data['error']}")
                break
            resp = "".join(
                b.get("text", "") for b in data.get("content", [])
                if b.get("type") == "text"
            )
            responses.append(resp)
            messages.append({"role": "assistant", "content": resp})

        return responses


# ── CLI entry points ───────────────────────────────────────────────────────

def cmd_cowork(task_type: str, prompt: str, api_key: str, model: str,
               files: Optional[list[str]] = None, depth: int = 3,
               output_fmt: str = "markdown", output_file: Optional[str] = None):
    agent  = CoworkAgent(api_key=api_key, model=model)
    result = agent.run(task_type, prompt, files=files, depth=depth, output_fmt=output_fmt)

    print(result["output"])

    u = result.get("usage", {})
    print(f"\n\033[90m[{result['task_name']}  in={u.get('input_tokens',0)}  out={u.get('output_tokens',0)}]\033[0m")

    if output_file:
        Path(output_file).write_text(result["output"])
        print(f"\033[92m✓ Saved to {output_file}\033[0m")

    return result


def cmd_cowork_list():
    print("\nCowork task types:")
    print(f"\n  {'TYPE':<14}{'NAME':<26}DESCRIPTION")
    print("  " + "─" * 70)
    for key, task in COWORK_TASKS.items():
        print(f"  {key:<14}{(task['icon']+' '+task['name']):<26}{task['description']}")
    print("\n  Usage: ai-coder --cowork <type> --cowork-prompt \"your task\"")
