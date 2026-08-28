import contextlib
import importlib.util
import io
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).with_name("install_cloudflare_terraform.py")
SPEC = importlib.util.spec_from_file_location("install_cloudflare_terraform", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CommandLoggingTests(unittest.TestCase):
    def test_command_arguments_are_omitted_from_logs(self):
        command = ["curl", "-H", "Authorization: Bearer sensitive-token", "https://api.example.test"]
        output = io.StringIO()

        with patch.object(MODULE.subprocess, "run") as run, contextlib.redirect_stdout(output):
            MODULE.run(command)

        self.assertNotIn("sensitive-token", output.getvalue())
        self.assertNotIn("Authorization", output.getvalue())
        self.assertEqual("+ executing command (arguments omitted)\n", output.getvalue())
        run.assert_called_once_with(command, cwd=None, env=None, check=True, text=True, capture_output=False)


if __name__ == "__main__":
    unittest.main()
