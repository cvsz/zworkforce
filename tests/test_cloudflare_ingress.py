import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TERRAFORM = ROOT / "infrastructure" / "terraform" / "cloudflare" / "zworkforce.tf"
OUTPUTS = ROOT / "infrastructure" / "terraform" / "cloudflare" / "outputs.tf"
INGRESS = ROOT / "deploy" / "cloudflare" / "tunnel-ingress.yml"
HA_WORKFLOW = ROOT / ".github" / "workflows" / "ha-infrastructure.yml"
DNS_IMPORT = ROOT / "scripts" / "cloudflare-import-dns.sh"
CLOUDFLARE_PLAN = ROOT / "scripts" / "cloudflare-plan.sh"
CLOUDFLARE_LEGACY_PLAN = ROOT / "scripts" / "cloudflare" / "cloudflare-plan.sh"
CLOUDFLARE_APPLY = ROOT / "scripts" / "cloudflare-apply.sh"
CLOUDFLARE_LEGACY_APPLY = ROOT / "scripts" / "cloudflare" / "cloudflare-apply.sh"


class CloudflareIngressTests(unittest.TestCase):
    def test_zwf_api_is_a_single_canonical_tunnel_route(self):
        terraform = TERRAFORM.read_text(encoding="utf-8")
        outputs = OUTPUTS.read_text(encoding="utf-8")
        ingress = INGRESS.read_text(encoding="utf-8")
        workflow = HA_WORKFLOW.read_text(encoding="utf-8")
        dns_import = DNS_IMPORT.read_text(encoding="utf-8")

        self.assertEqual(terraform.count('default     = "zwf-api.zeaz.dev"'), 1)
        self.assertEqual(terraform.count('name    = var.zwf_api_hostname'), 1)
        self.assertIn(
            "{ hostname = var.zwf_api_hostname, service = var.zwf_origin },",
            terraform,
        )
        self.assertIn('resource "cloudflare_dns_record" "zwf_api"', terraform)
        self.assertIn('resource "cloudflare_dns_record" "zworkforce"', terraform)
        self.assertIn("Retiring this", terraform)
        self.assertIn('output "zwf_api_url"', terraform)
        self.assertIn("local.zworkforce_ingress", outputs)
        self.assertIn(
            "hostname: zwf-api.zeaz.dev\n    service: http://127.0.0.1:9570",
            ingress,
        )
        self.assertIn('"zwf-api.zeaz.dev": "http://127.0.0.1:9570"', workflow)
        self.assertIn('[zwf-api]="cloudflare_dns_record.zwf_api"', dns_import)
        self.assertIn('[zwf-api]="${ZWF_API_HOSTNAME:-zwf-api.zeaz.dev}"', dns_import)

    def test_cloudflare_plan_ignores_operator_tfvars_for_source_format_check(self):
        for script_path in (
            CLOUDFLARE_PLAN,
            CLOUDFLARE_LEGACY_PLAN,
            CLOUDFLARE_APPLY,
            CLOUDFLARE_LEGACY_APPLY,
        ):
            script = script_path.read_text(encoding="utf-8")
            self.assertIn("find", script)
            self.assertIn("-name '*.tf'", script)
            self.assertNotIn("fmt -check -recursive", script)


if __name__ == "__main__":
    unittest.main()
