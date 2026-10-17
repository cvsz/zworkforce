"""Unit contract tests for the optional zwslcore model/MCP diagnostic."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "zwslcore-provider-check.py"
spec = importlib.util.spec_from_file_location("zwslcore_probe", SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ProviderIntegrationProbeTests(unittest.TestCase):
    def test_refuses_public_plaintext_and_credentials(self):
        invalid = (
            "http://example.com/v1", "http://169.254.169.254/v1",
            "https://user:pass@example.com/v1", "http://10.0.0.10:11434/v1?token=x",
            "ftp://localhost/v1", "http://192.168.1.5/v1",
        )
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(probe.ProbeError):
                probe.validate_url(url)
        self.assertEqual(
            probe.validate_url("http://10.0.0.10:11434/v1", private_http=True),
            "http://10.0.0.10:11434/v1",
        )
        with self.assertRaises(probe.ProbeError):
            probe.validate_url("http://127.0.0.1:9569/mcp", mcp=True, private_http=True)

    def test_openai_compatible_model_inventory_and_chat(self):
        seen = []
        def request(url, **kwargs):
            seen.append((url, kwargs))
            if url.endswith("/models"):
                return {"data": [{"id": "qwen2.5-coder:7b"}]}
            return {"choices": [{"message": {"content": "OK"}}]}
        with mock.patch.object(probe, "invoke", side_effect=request):
            probe.probe_provider("https://provider.example.com/v1", "fake-test-token", "qwen2.5-coder:7b", True)
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[1][1]["body"]["model"], "qwen2.5-coder:7b")
        self.assertEqual(seen[1][1]["headers"]["Authorization"], "Bearer fake-test-token")

    def test_modern_mcp_discovery_contract(self):
        with mock.patch.object(probe, "invoke", return_value={"jsonrpc": "2.0", "id": 1, "result": {}}) as invoke:
            probe.probe_mcp("https://workforce.example.com/mcp", "fake-test-token")
        params = invoke.call_args.kwargs["body"]["params"]
        self.assertEqual(params["_meta"]["io.modelcontextprotocol/protocolVersion"], "2026-07-28")
        self.assertEqual(invoke.call_args.kwargs["headers"]["Mcp-Method"], "server/discover")

    def test_mcp_without_token_fails_closed(self):
        with self.assertRaises(probe.ProbeError):
            probe.probe_mcp("https://workforce.example.com/mcp", "")

    def test_no_shell_or_dotenv(self):
        source = SCRIPT.read_text()
        self.assertNotIn("shell=True", source)
        self.assertNotIn("load_dotenv", source)
        self.assertNotIn("subprocess", source)


if __name__ == "__main__":
    unittest.main()
