import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TERRAFORM = ROOT / "infrastructure" / "terraform" / "cloudflare" / "zworkforce.tf"
OUTPUTS = ROOT / "infrastructure" / "terraform" / "cloudflare" / "outputs.tf"
INGRESS = ROOT / "deploy" / "cloudflare" / "tunnel-ingress.yml"
INGRESS_EXAMPLE = ROOT / "deploy" / "cloudflare" / "zwf-ingress.yml.example"
HA_WORKFLOW = ROOT / ".github" / "workflows" / "ha-infrastructure.yml"
DNS_IMPORT = ROOT / "scripts" / "cloudflare-import-dns.sh"
LEGACY_DNS_IMPORT = ROOT / "scripts" / "cloudflare" / "cloudflare-import-dns.sh"
CLOUDFLARE_ENV = ROOT / "scripts" / "lib" / "cloudflare-terraform-env.sh"
CLOUDFLARE_PLAN = ROOT / "scripts" / "cloudflare-plan.sh"
CLOUDFLARE_LEGACY_PLAN = ROOT / "scripts" / "cloudflare" / "cloudflare-plan.sh"
CLOUDFLARE_APPLY = ROOT / "scripts" / "cloudflare-apply.sh"
CLOUDFLARE_LEGACY_APPLY = ROOT / "scripts" / "cloudflare" / "cloudflare-apply.sh"


class CloudflareIngressTests(unittest.TestCase):
    def test_zwf_api_is_a_single_canonical_tunnel_route(self):
        terraform = TERRAFORM.read_text(encoding="utf-8")
        outputs = OUTPUTS.read_text(encoding="utf-8")
        ingress = INGRESS.read_text(encoding="utf-8")
        ingress_example = INGRESS_EXAMPLE.read_text(encoding="utf-8")
        workflow = HA_WORKFLOW.read_text(encoding="utf-8")
        dns_import = DNS_IMPORT.read_text(encoding="utf-8")
        legacy_dns_import = LEGACY_DNS_IMPORT.read_text(encoding="utf-8")
        cloudflare_env = CLOUDFLARE_ENV.read_text(encoding="utf-8")

        self.assertEqual(terraform.count('default     = "zwf-api.zeaz.dev"'), 1)
        self.assertEqual(terraform.count('name    = var.zwf_api_hostname'), 1)
        self.assertEqual(terraform.count('default     = "zslog.zeaz.dev"'), 1)
        self.assertIn(
            "{ hostname = var.zwf_api_hostname, service = var.zwf_origin },",
            terraform,
        )
        self.assertIn(
            "{ hostname = var.zslog_hostname, service = var.zslog_origin },",
            terraform,
        )
        self.assertIn('default     = "http://127.0.0.1:9581"', terraform)
        self.assertIn('resource "cloudflare_dns_record" "zwf_api"', terraform)
        self.assertIn('resource "cloudflare_dns_record" "zslog"', terraform)
        self.assertIn('resource "cloudflare_dns_record" "zworkforce"', terraform)
        self.assertIn("Retiring this", terraform)
        self.assertIn('output "zwf_api_url"', terraform)
        self.assertIn('output "zslog_url"', terraform)
        self.assertIn("local.zworkforce_ingress", outputs)
        self.assertIn(
            "hostname: zwf-api.zeaz.dev\n    service: http://127.0.0.1:9570",
            ingress,
        )
        self.assertIn(
            "hostname: zslog.zeaz.dev\n    service: http://127.0.0.1:9581",
            ingress,
        )
        self.assertIn(
            "hostname: zslog.zeaz.dev\n    service: http://127.0.0.1:9581",
            ingress_example,
        )
        self.assertIn('"zwf-api.zeaz.dev": "http://127.0.0.1:9570"', workflow)
        self.assertIn('"zslog.zeaz.dev": "http://127.0.0.1:9581"', workflow)
        self.assertIn('[zwf-api]="cloudflare_dns_record.zwf_api"', dns_import)
        self.assertIn('[zwf-api]="${ZWF_API_HOSTNAME:-zwf-api.zeaz.dev}"', dns_import)
        self.assertIn('[zslog]="cloudflare_dns_record.zslog"', dns_import)
        self.assertIn('[zslog]="${ZSLOG_HOSTNAME:-zslog.zeaz.dev}"', dns_import)
        self.assertIn('[zslog]="cloudflare_dns_record.zslog"', legacy_dns_import)
        self.assertIn('[zslog]="${ZSLOG_HOSTNAME:-zslog.zeaz.dev}"', legacy_dns_import)
        self.assertIn('TF_VAR_zslog_hostname="${ZSLOG_HOSTNAME:-zslog.zeaz.dev}"', cloudflare_env)
        self.assertIn(
            'TF_VAR_zslog_origin="${ZSLOG_ORIGIN:-http://127.0.0.1:9581}"',
            cloudflare_env,
        )

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
