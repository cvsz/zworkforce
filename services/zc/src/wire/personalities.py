"""personalities.py — Personality styles"""

PERSONALITIES = {
    "precise":    "Be concise, technical, and precise. Avoid fluff.",
    "teaching":   "Explain concepts clearly, step by step, as if teaching a beginner.",
    "creative":   "Be inventive and think outside the box.",
    "socratic":   "Ask probing questions and guide the user to discover answers.",
    "pragmatic":  "Focus on practical, working solutions over theory.",
}


class PersonalityManager:
    def list_personalities(self):
        return [{"name": k, "description": v} for k, v in PERSONALITIES.items()]

    def build_prompt_addition(self, style):
        return PERSONALITIES.get(style, "")
