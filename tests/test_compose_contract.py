from pathlib import Path
import re
import unittest


COMPOSE = Path(__file__).resolve().parents[1] / "compose.yaml"
DOCKERFILE = Path(__file__).resolve().parents[1] / "Dockerfile"
HA_COMPOSES = (
    Path(__file__).resolve().parents[1] / "deploy" / "ha" / "compose.vm-a.yaml",
    Path(__file__).resolve().parents[1] / "deploy" / "ha" / "compose.vm-b.yaml",
)
HA_ENV_EXAMPLE = Path(__file__).resolve().parents[1] / "deploy" / "ha" / "compose.shared.env.example"


def service_block(source: str, service: str) -> str:
    lines = source.splitlines()
    marker = f"  {service}:"
    try:
        start = lines.index(marker) + 1
    except ValueError as exc:
        raise AssertionError(f"service {service!r} not found") from exc
    end = next(
        (index for index in range(start, len(lines)) if re.match(r"^  [^ ]", lines[index])),
        len(lines),
    )
    return "\n".join(lines[start:end])


class ComposeHealthcheckContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = COMPOSE.read_text(encoding="utf-8")

    def test_api_keeps_http_healthcheck_and_host_port_contract(self):
        api = service_block(self.source, "api")
        self.assertNotIn("disable: true", api)
        self.assertIn('${ZWORKFORCE_HOST_PORT:-9570}:9569', api)

    def test_non_http_roles_disable_inherited_api_healthcheck(self):
        for role in ("worker", "scheduler", "outbox"):
            with self.subTest(role=role):
                block = service_block(self.source, role)
                self.assertRegex(block, r"(?m)^    healthcheck:\n      disable: true$")

    def test_production_image_installs_s3_runtime_extra(self):
        dockerfile = DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn("ARG VERSION=3.0.4", dockerfile)
        self.assertIn('python -m pip install --no-cache-dir ".[s3]"', dockerfile)

    def test_ha_healthchecks_use_runtime_python_not_missing_curl(self):
        expected = '["CMD", "python", "-c", "import json,urllib.request;'
        for path in HA_COMPOSES:
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertIn(expected, source)
                self.assertNotIn('["CMD", "curl",', source)

    def test_supabase_s3_example_uses_direct_storage_hostname(self):
        source = HA_ENV_EXAMPLE.read_text(encoding="utf-8")
        self.assertIn(".storage.supabase.co/storage/v1/s3", source)
        self.assertNotIn(".supabase.co/storage/v1/s3", source.replace(".storage.supabase.co/storage/v1/s3", ""))


if __name__ == "__main__":
    unittest.main()
