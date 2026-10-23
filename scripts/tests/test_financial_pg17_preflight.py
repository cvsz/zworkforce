"""Offline, no-Docker regression tests for financial PG17 disposable admission."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


RUNNER = Path(__file__).resolve().parents[1] / "financial-pg17-disposable-admission.sh"
CONTAINER = "a" * 64
FAKE_DOCKER = '''#!/usr/bin/env python3
import os
import sys
from pathlib import Path

args = sys.argv[1:]
with Path(os.environ["FAKE_DOCKER_LOG"]).open("a", encoding="utf-8") as log:
    log.write(" ".join(args) + "\\n")
if args[0] == "inspect":
    fmt = args[2]
    if fmt == "{{.Config.Image}}":
        print(os.environ.get("FAKE_IMAGE", "postgres:17-alpine"))
    elif "Config.Labels" in fmt:
        print(os.environ.get("FAKE_LABEL", "disposable"))
    elif "Config.Env" in fmt:
        print("POSTGRES_DB=zeaz_financial_acceptance")
    else:
        sys.exit(40)
elif args[0] == "exec":
    if "-i" in args:
        sys.exit(41)  # SQL execution is intentionally never simulated.
    query = args[-1]
    if query == "SHOW server_version_num":
        print(os.environ.get("FAKE_VERSION", "170005"))
    elif "FROM pg_namespace" in query and "FROM pg_class" in query:
        print(os.environ.get("FAKE_EXISTING", "0"))
    else:
        sys.exit(42)
else:
    sys.exit(43)
'''


class DisposablePreflightTests(unittest.TestCase):
    def run_case(self, **overrides):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            runner_copy = tmp / "scripts" / RUNNER.name
            runner_copy.parent.mkdir(parents=True)
            shutil.copy2(RUNNER, runner_copy)
            # A harmless placeholder is redirected into fake Docker only; no SQL runs.
            for relative in (
                "services/billing-ledger/migrations/0001_financial_pg17_disposable.sql",
                "services/billing-ledger/acceptance/pg17_disposable_contract.sql",
            ):
                fixture = tmp / relative
                fixture.parent.mkdir(parents=True, exist_ok=True)
                fixture.write_text("-- synthetic offline fixture\n", encoding="utf-8")
            docker = tmp / "docker"
            docker.write_text(FAKE_DOCKER, encoding="utf-8")
            docker.chmod(0o755)
            log = tmp / "docker.log"
            env = os.environ.copy()
            env.update({
                "PATH": f"{tmp}:{env['PATH']}",
                "FAKE_DOCKER_LOG": str(log),
                "POSTGRES_TEST_CONTAINER_ID": CONTAINER,
                "Z_FINANCIAL_PG17_DISPOSABLE_ATTESTED": "true",
            })
            env.update(overrides)
            result = subprocess.run(["bash", str(runner_copy)], env=env, capture_output=True, text=True, check=False)
            return result, log.read_text(encoding="utf-8") if log.exists() else ""

    def test_missing_attestation_rejected_before_docker(self):
        result, log = self.run_case(Z_FINANCIAL_PG17_DISPOSABLE_ATTESTED="")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(log, "")

    def test_nonempty_database_rejected_before_sql(self):
        result, log = self.run_case(FAKE_EXISTING="1")
        self.assertEqual(result.returncode, 3)
        self.assertIn("pre-existing user objects", result.stderr)
        self.assertNotIn("exec -i", log)

    def test_empty_database_reaches_sql_boundary(self):
        result, log = self.run_case(FAKE_EXISTING="0")
        self.assertEqual(result.returncode, 41)
        self.assertIn("exec -i", log)

    def test_untrusted_image_rejected(self):
        result, log = self.run_case(FAKE_IMAGE="postgres:16-alpine")
        self.assertEqual(result.returncode, 3)
        self.assertNotIn("exec -i", log)

    def test_untrusted_label_rejected(self):
        result, log = self.run_case(FAKE_LABEL="production")
        self.assertEqual(result.returncode, 3)
        self.assertNotIn("exec -i", log)

    def test_wrong_pg_major_rejected(self):
        result, log = self.run_case(FAKE_VERSION="160005")
        self.assertEqual(result.returncode, 3)
        self.assertNotIn("exec -i", log)

    def test_database_query_covers_user_objects(self):
        content = RUNNER.read_text(encoding="utf-8")
        for catalog in ("pg_namespace", "pg_class", "pg_proc", "pg_type", "pg_extension"):
            with self.subTest(catalog=catalog):
                self.assertIn(catalog, content)


if __name__ == "__main__":
    unittest.main()
