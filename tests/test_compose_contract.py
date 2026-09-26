from pathlib import Path
import os
import re
import shutil
import subprocess
import unittest


COMPOSE = Path(__file__).resolve().parents[1] / "compose.yaml"
DOCKERFILE = Path(__file__).resolve().parents[1] / "Dockerfile"
HA_COMPOSES = (
    Path(__file__).resolve().parents[1] / "deploy" / "ha" / "compose.vm-a.yaml",
    Path(__file__).resolve().parents[1] / "deploy" / "ha" / "compose.vm-b.yaml",
)
HA_ENV_EXAMPLE = Path(__file__).resolve().parents[1] / "deploy" / "ha" / "compose.shared.env.example"


COMPOSE_REQUIRED_ENV = {
    "ZWORKFORCE_POSTGRES_PASSWORD": "ci-only-postgres-password",
    "ZWORKFORCE_API_KEYS": "ci-only-key:superadmin:default:bootstrap:*",
    "ZARVIS_LOCAL_OWNER_TOKEN": "ci-only-owner-token-at-least-32-bytes-long",
    "ZARVIS_ACTION_WORKER_TOKEN": "ci-only-action-worker-token-at-least-32-bytes",
    "ZARVIS_PROACTIVE_WORKER_TOKEN": "ci-only-proactive-worker-token-at-least-32-bytes",
}

# Secrets the base Compose file treats as optional. They belong to services
# behind the `zarvis-local` / `all` profiles, so the default render must succeed
# without them and must not carry insecure development defaults.
COMPOSE_OPTIONAL_ENV = frozenset(
    {
        "ZARVIS_LOCAL_OWNER_TOKEN",
        "ZARVIS_ACTION_WORKER_TOKEN",
        "ZARVIS_PROACTIVE_WORKER_TOKEN",
    }
)


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

    def test_ha_non_http_roles_disable_inherited_api_healthcheck(self):
        for path in HA_COMPOSES:
            source = path.read_text(encoding="utf-8")
            for role in ("worker", "scheduler", "outbox"):
                with self.subTest(path=path.name, role=role):
                    block = service_block(source, role)
                    self.assertRegex(block, r"(?m)^    healthcheck:\n      disable: true$")

    def test_ha_runtime_identity_is_propagated_through_shared_environment(self):
        self.assertIn("ZWORKFORCE_INSTANCE_ID: ${ZWORKFORCE_INSTANCE_ID:-}", self.source)

    def test_supabase_s3_example_uses_direct_storage_hostname(self):
        source = HA_ENV_EXAMPLE.read_text(encoding="utf-8")
        self.assertIn(".storage.supabase.co/storage/v1/s3", source)
        self.assertNotIn(".supabase.co/storage/v1/s3", source.replace(".storage.supabase.co/storage/v1/s3", ""))

    def test_zarvis_tokens_are_profile_scoped_without_insecure_defaults(self):
        expected_tokens = {
            "zarvis-action-gateway": ("ZARVIS_LOCAL_OWNER_TOKEN", "ZARVIS_ACTION_WORKER_TOKEN"),
            "zarvis-action-worker": ("ZARVIS_ACTION_WORKER_TOKEN",),
            "zarvis-proactive": ("ZARVIS_LOCAL_OWNER_TOKEN", "ZARVIS_PROACTIVE_WORKER_TOKEN"),
            "zarvis-proactive-worker": ("ZARVIS_PROACTIVE_WORKER_TOKEN",),
        }
        for service, tokens in expected_tokens.items():
            with self.subTest(service=service):
                block = service_block(self.source, service)
                self.assertNotIn("development-owner-token", block)
                self.assertNotIn("development-worker-token", block)
                self.assertIn('profiles: ["zarvis-local", "all"]', block)
                for token in tokens:
                    self.assertIn(f"{token}: ${{{token}:-}}", block)
                    self.assertNotIn(f"${{{token}:?", block)


class ComposeSecretRenderingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docker = shutil.which("docker")
        if cls.docker is None:
            raise unittest.SkipTest("docker CLI is required for Compose rendering tests")
        version = subprocess.run(
            [cls.docker, "compose", "version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if version.returncode != 0:
            raise unittest.SkipTest("Docker Compose plugin is required for rendering tests")

    def render_compose(self, environment):
        return subprocess.run(
            [self.docker, "compose", "--env-file", "/dev/null", "config", "-q"],
            cwd=COMPOSE.parent,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_render_fails_without_required_secrets(self):
        # Only the always-required secrets are enforced in the default render.
        # The ZARVIS tokens are deliberately profile-scoped and optional in the
        # base file (see test_zarvis_tokens_are_profile_scoped_without_insecure_defaults),
        # so they are asserted as optional here rather than as fail-closed.
        # Each required variable is checked in isolation: every other secret is
        # supplied so the only missing one is the variable under test. Asserting
        # that one render lists them all is fragile, because Compose stops at
        # the first interpolation error and the number of reported variables
        # differs between Compose versions.
        for missing in COMPOSE_REQUIRED_ENV:
            with self.subTest(missing=missing):
                environment = {"PATH": os.environ.get("PATH", "")}
                environment.update(COMPOSE_REQUIRED_ENV)
                environment.pop(missing)

                result = self.render_compose(environment)

                if missing in COMPOSE_OPTIONAL_ENV:
                    self.assertEqual(
                        result.returncode,
                        0,
                        f"{missing} must stay optional in the default render: {result.stderr}",
                    )
                else:
                    self.assertNotEqual(result.returncode, 0, result.stderr)
                    self.assertIn(f"required variable {missing}", result.stderr)

    def test_render_succeeds_with_explicit_ci_only_secrets(self):
        environment = {"PATH": os.environ.get("PATH", "")}
        environment.update(COMPOSE_REQUIRED_ENV)

        result = self.render_compose(environment)

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
