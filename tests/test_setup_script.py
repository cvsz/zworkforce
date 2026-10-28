from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SetupScriptTests(unittest.TestCase):
    def test_setup_uses_its_checkout_and_installs_project_metadata(self):
        script = (ROOT / "setup.sh").read_text(encoding="utf-8")

        self.assertIn('dirname -- "${BASH_SOURCE[0]}"', script)
        self.assertIn('"$VENV_PYTHON" -m pip install "$REPOSITORY_ROOT"', script)
        self.assertNotIn("cd /workspace", script)

    def test_setup_installs_zarvis_from_frozen_lockfile(self):
        script = (ROOT / "setup.sh").read_text(encoding="utf-8")

        self.assertIn('pnpm --dir "$REPOSITORY_ROOT/packages/zarvis"', script)
        self.assertIn("--frozen-lockfile", script)


if __name__ == "__main__":
    unittest.main()
