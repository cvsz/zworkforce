import copy
import json
import unittest
from pathlib import Path

from scripts.validate_center_control_plane import RegistryValidationError, validate_registry


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "center-control-plane.example.json"


class CenterControlPlaneRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_example_semantics_pass(self):
        validate_registry(self.registry)

    def test_rejects_unknown_version(self):
        data = copy.deepcopy(self.registry)
        data["version"] = 2
        with self.assertRaises(RegistryValidationError):
            validate_registry(data)

    def test_rejects_duplicate_repository(self):
        data = copy.deepcopy(self.registry)
        data["repositories"].append(copy.deepcopy(data["repositories"][0]))
        with self.assertRaises(RegistryValidationError):
            validate_registry(data)

    def test_rejects_missing_edge_owner_repository(self):
        data = copy.deepcopy(self.registry)
        data["hostnames"]["zwf.zeaz.dev"]["edgeOwnerRepository"] = "cvsz/missing"
        with self.assertRaises(RegistryValidationError):
            validate_registry(data)

    def test_rejects_edge_owner_without_authority(self):
        data = copy.deepcopy(self.registry)
        data["hostnames"]["zwf.zeaz.dev"]["edgeOwnerRepository"] = "cvsz/ztemplate"
        with self.assertRaises(RegistryValidationError):
            validate_registry(data)

    def test_rejects_verified_hostname_evidence_from_wrong_environment(self):
        data = copy.deepcopy(self.registry)
        host = data["hostnames"]["zwf.zeaz.dev"]
        host["effectiveState"] = "VERIFIED"
        host["evidence"] = {
            "subjectRevision": "0" * 40,
            "environment": "development",
            "observedAt": "2026-09-30T00:00:00Z",
            "commandOrRun": "test",
            "result": "PASS",
            "artifactReference": "artifact://test",
        }
        with self.assertRaises(RegistryValidationError):
            validate_registry(data)


if __name__ == "__main__":
    unittest.main()
