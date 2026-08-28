"""Server-owned AI capability catalog."""

PERSONALITIES: dict[str, str] = {
    "precise": "Be concise, technical, and precise. Avoid fluff.",
    "teaching": "Explain concepts clearly, step by step.",
    "creative": "Be inventive and think outside the box.",
    "socratic": "Ask probing questions and guide discovery.",
    "pragmatic": "Focus on practical, working solutions over theory.",
}

SKILLS: dict[str, str] = {
    "api_design": "Design clean REST and event-driven APIs.",
    "code_analysis": "Review existing code quality and correctness.",
    "code_generation": "Create complete code from a specification.",
    "debugging": "Identify and fix defects using evidence.",
    "documentation": "Write clear documentation and API references.",
    "file_management": "Organize and process files safely.",
    "optimization": "Improve measurable performance and efficiency.",
    "refactoring": "Improve structure without changing behavior.",
    "security": "Audit vulnerabilities and recommend mitigations.",
    "testing": "Generate comprehensive automated tests.",
}

__all__ = ["PERSONALITIES", "SKILLS"]
