import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "infrastructure" / "terraform" / "cloudflare"
ZNEON = STACK / "zneon.tf"
MAIN = STACK / "main.tf"
OUTPUTS = STACK / "outputs.tf"
INGRESS = ROOT / "deploy" / "cloudflare" / "tunnel-ingress.yml"


class ZNeonCloudflareTests(unittest.TestCase):
    def test_zneon_domain_is_managed_through_existing_tunnel(self):
        zneon = ZNEON.read_text(encoding="utf-8")
        main = MAIN.read_text(encoding="utf-8")
        outputs = OUTPUTS.read_text(encoding="utf-8")
        ingress = INGRESS.read_text(encoding="utf-8")

        self.assertIn('default     = "zneon.zeaz.dev"', zneon)
        self.assertIn('default     = "http://127.0.0.1:18085"', zneon)
        self.assertIn('resource "cloudflare_dns_record" "zneon"', zneon)
        self.assertIn('content = local.tunnel_cname', zneon)
        self.assertIn('proxied = true', zneon)
        self.assertIn('output "zneon_url"', zneon)

        self.assertIn("local.zneon_ingress", main)
        self.assertIn("local.zneon_ingress", outputs)

        self.assertIn(
            "hostname: zneon.zeaz.dev\n    service: http://127.0.0.1:18085",
            ingress,
        )

    def test_zneon_origin_is_loopback_only_and_non_conflicting(self):
        zneon = ZNEON.read_text(encoding="utf-8")
        self.assertIn(
            'condition     = var.zneon_origin == "http://127.0.0.1:18085"',
            zneon,
        )
        self.assertNotIn("0.0.0.0:18085", zneon)
        self.assertNotIn('default     = "http://127.0.0.1:18081"', zneon)
        self.assertNotIn('default     = "http://127.0.0.1:18083"', zneon)
        self.assertNotIn('default     = "http://127.0.0.1:18084"', zneon)


if __name__ == "__main__":
    unittest.main()
