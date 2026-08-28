"""skills.py — Skills system"""

SKILLS = [
    {"name": "code_generation",    "description": "Create production-ready code from a description"},
    {"name": "code_analysis",      "description": "Review and analyse existing code quality"},
    {"name": "testing",            "description": "Generate comprehensive test suites"},
    {"name": "documentation",      "description": "Write docs, README, and API references"},
    {"name": "refactoring",        "description": "Improve code structure and maintainability"},
    {"name": "debugging",          "description": "Identify and fix bugs"},
    {"name": "optimization",       "description": "Improve performance and efficiency"},
    {"name": "security",           "description": "Security audit and vulnerability review"},
    {"name": "file_management",    "description": "Organise and process files"},
    {"name": "spreadsheet_analysis","description": "Build financial models, clean messy data, "
                                                    "and create tables/charts (see --excel)"},
    {"name": "api_design",         "description": "Design clean REST/GraphQL APIs"},
    {"name": "voice",              "description": "Generate voice/TTS scripts (gTTS/ElevenLabs)"},
    {"name": "video",              "description": "Generate video production scripts (MoviePy/FFmpeg)"},
    {"name": "music",              "description": "Generate music/MIDI scripts (music21)"},
    {"name": "animation",          "description": "Generate animation code (CSS/Manim/SVG)"},
]


class SkillManager:
    def list_skills(self):
        return SKILLS

    def get_skill(self, name):
        return next((s for s in SKILLS if s["name"] == name), None)
