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

    def test_empty_provider_inventory_is_not_a_pass(self):
        for result in ({"data": []}, {"data": [{}]}, {"data": [{"id": ""}]}):
            with self.subTest(result=result), mock.patch.object(probe, "invoke", return_value=result):
                with self.assertRaises(probe.ProbeError):
                    probe.probe_provider("https://provider.example.com/v1", "test-token", "", False)

    def test_empty_inference_output_is_not_a_pass(self):
        inventory = {"data": [{"id": "qwen2.5-coder:7b"}]}
        for invalid in ({"choices": []}, {"choices": [{}]},
                        {"choices": [{"message": {"content": ""}}]},
                        {"choices": [{"message": {"content": None}}]}):
            with self.subTest(invalid=invalid), mock.patch.object(
                    probe, "invoke", side_effect=(inventory, invalid)):
                with self.assertRaises(probe.ProbeError):
                    probe.probe_provider("https://provider.example.com/v1",
                                         "test-token", "qwen2.5-coder:7b", True)

    def test_mcp_requires_result_object(self):
        for bad_response in ({"jsonrpc": "2.0", "id": 1},
                             {"jsonrpc": "2.0", "id": 1, "result": None},
                             {"jsonrpc": "2.0", "id": 1, "result": []},
                             {"jsonrpc": "2.0", "id": 1, "error": {"code": -32601}}):
            with self.subTest(bad_response=bad_response), mock.patch.object(
                    probe, "invoke", return_value=bad_response):
                with self.assertRaises(probe.ProbeError):
                    probe.probe_mcp("https://workforce.example.com/mcp", "test-token")

    def test_mcp_without_token_fails_closed(self):
        with self.assertRaises(probe.ProbeError):
            probe.probe_mcp("https://workforce.example.com/mcp", "")

    def test_service_token_pair_requires_https(self):
        with mock.patch.dict("os.environ", {
            "ZWORKFORCE_CF_ACCESS_CLIENT_ID": "fake-id",
            "ZWORKFORCE_CF_ACCESS_CLIENT_SECRET": "fake-secret"}, clear=True):
            self.assertEqual(probe.access_headers("https://api.example.net/v1"), {
                "CF-Access-Client-Id": "fake-id",
                "CF-Access-Client-Secret": "fake-secret",
            })
            with self.assertRaisesRegex(probe.ProbeError, "HTTPS"):
                probe.access_headers("http://10.0.0.10:8080/v1")
        with mock.patch.dict("os.environ", {
            "ZWORKFORCE_CF_ACCESS_CLIENT_ID": "fake-id"}, clear=True):
            with self.assertRaisesRegex(probe.ProbeError, "Both"):
                probe.access_headers("https://api.example.net/v1")

    def test_provider_probe_includes_service_token_headers(self):
        with mock.patch.dict("os.environ", {
            "ZWORKFORCE_CF_ACCESS_CLIENT_ID": "fake-id",
            "ZWORKFORCE_CF_ACCESS_CLIENT_SECRET": "fake-secret"}, clear=True), \\
             mock.patch.object(probe, "invoke", return_value={"data": [{"id": "zeaz-free"}]}) as invoke:
            probe.probe_provider("https://api.example.net/v1", "fake-provider-token", "zeaz-free", False)
        sent = invoke.call_args.kwargs["headers"]
        self.assertEqual(sent["CF-Access-Client-Id"], "fake-id")
        self.assertEqual(sent["Authorization"], "Bearer fake-provider-token")

    def test_no_shell_or_dotenv(self):
        source = SCRIPT.read_text()
        self.assertNotIn("shell=True", source)
        self.assertNotIn("load_dotenv", source)
        self.assertNotIn("subprocess", source)


if __name__ == "__main__":
    unittest.main()
