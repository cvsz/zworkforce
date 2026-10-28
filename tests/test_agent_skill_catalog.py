"""Contract tests for the declarative agent/skill catalog."""
import importlib.util
import unittest
from pathlib import Path
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_agent_skill_catalog.py"
SPEC = importlib.util.spec_from_file_location("validate_agent_skill_catalog", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class AgentSkillCatalogTests(unittest.TestCase):
    def test_manifest_and_referenced_files_are_valid(self):
        self.assertEqual(MODULE.validate(), [])

    def test_frontmatter_requires_delimiters(self):
        with self.assertRaises(ValueError):
            MODULE.frontmatter("name: invalid\n")

    def test_frontmatter_parses_metadata(self):
        parsed = MODULE.frontmatter("---\nname: example\ndescription: A test\n---\n")
        self.assertEqual(parsed["name"], "example")
        self.assertEqual(parsed["description"], "A test")

if __name__ == "__main__":
    unittest.main()
