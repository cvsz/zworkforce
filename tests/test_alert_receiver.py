import json
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from tempfile import TemporaryDirectory

from deploy.observability.alert_receiver import ReceiptHTTPServer


class AlertReceiverTests(unittest.TestCase):
    token = "test-token-0123456789-abcdefghijklmnopqrstuvwxyz"

    def setUp(self):
        self.tempdir = TemporaryDirectory()
        self.data_dir = Path(self.tempdir.name)
        self.server = ReceiptHTTPServer(("127.0.0.1", 0), self.token, self.data_dir)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tempdir.cleanup()

    def request(self, method, path, body=None, auth=True):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=2)
        headers = {"Connection": "close"}
        if auth:
            headers["Authorization"] = f"Bearer {self.token}"
        if body is not None:
            headers["Content-Type"] = "application/json"
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        content = response.read()
        connection.close()
        return response.status, json.loads(content) if content else None

    def test_health_is_available_without_receipt_authorization(self):
        status, payload = self.request("GET", "/healthz", auth=False)
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"status": "ok"})

    def test_alert_is_stored_as_queryable_metadata(self):
        evidence_id = "stage-g-test-123"
        body = json.dumps(
            {
                "alerts": [
                    {"labels": {"alertname": "Test", "evidence_id": evidence_id}}
                ]
            }
        )
        status, payload = self.request("POST", "/ingest", body=body)
        self.assertEqual(status, 202)
        self.assertEqual(payload, {"accepted": True, "receipt_count": 1})

        status, receipt = self.request(
            "GET", f"/receipt?evidence_id={evidence_id}"
        )
        self.assertEqual(status, 200)
        self.assertEqual(receipt["evidence_id"], evidence_id)
        self.assertEqual(receipt["alert_count"], 1)
        self.assertRegex(receipt["payload_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(len(list(self.data_dir.glob("*.json"))), 1)

    def test_receipts_require_bearer_authorization(self):
        status, payload = self.request(
            "GET", "/receipt?evidence_id=stage-g-test-123", auth=False
        )
        self.assertEqual(status, 401)
        self.assertIsNone(payload)

    def test_invalid_evidence_id_is_not_written(self):
        body = json.dumps({"alerts": [{"labels": {"evidence_id": "../escape"}}]})
        status, payload = self.request("POST", "/ingest", body=body)
        self.assertEqual(status, 202)
        self.assertEqual(payload, {"accepted": True, "receipt_count": 0})
        self.assertEqual(list(self.data_dir.glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
