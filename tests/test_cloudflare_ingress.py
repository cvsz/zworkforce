import re
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
        # DBC must stay in the all-DNS reconciliation path (see dbc.zeaz.dev review).
        self.assertIn('[dbc]="cloudflare_dns_record.dbc"', dns_import)
        self.assertIn('[dbc]="${DBC_HOSTNAME:-dbc.zeaz.dev}"', dns_import)
        self.assertIn('[dbc]="cloudflare_dns_record.dbc"', legacy_dns_import)
        self.assertIn('[dbc]="${DBC_HOSTNAME:-dbc.zeaz.dev}"', legacy_dns_import)
        self.assertIn("dbc", dns_import.split("all_targets=")[1].split("\n")[0])
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

    def test_dashboard_access_application_uses_exact_nonempty_email_allowlist(self):
        main = (ROOT / "infrastructure" / "terraform" / "cloudflare" / "main.tf").read_text(
            encoding="utf-8"
        )
        variables = (
            ROOT / "infrastructure" / "terraform" / "cloudflare" / "variables.tf"
        ).read_text(encoding="utf-8")
        self.assertIn('cloudflare_zero_trust_access_application" "piewdash', main)
        self.assertNotIn('cloudflare_zero_trust_access_application" "qwen', main)
        self.assertIn("enable_binding_cookie      = true", main)
        self.assertIn("http_only_cookie_attribute = true", main)
        self.assertIn("piewdash_access_allowed_emails", main)
        self.assertIn("length(var.piewdash_access_allowed_emails) > 0", variables)
        self.assertNotIn("everyone", main)

    def test_dashboard_access_policy_matches_emails_exactly_not_by_domain(self):
        # The variable name and the absence of "everyone" are not enough. A
        # domain-wide selector computed from the same variable would widen the
        # policy to a whole domain while every other assertion still passed, so
        # the resource is matched on its own and its include block is inspected.
        main = (ROOT / "infrastructure" / "terraform" / "cloudflare" / "main.tf").read_text(
            encoding="utf-8"
        )
        resource = re.search(
            r'resource\s+"cloudflare_zero_trust_access_application"\s+"piewdash"\s*\{'
            r"(?P<body>.*?)\n\}",
            main,
            re.DOTALL,
        )
        self.assertIsNotNone(resource, "piewdash access application not found")
        body = resource.group("body")

        include = re.search(r"include\s*=\s*\[(?P<items>.*?)\]", body, re.DOTALL)
        self.assertIsNotNone(include, "policy has no include block")
        items = include.group("items")

        self.assertIn("var.piewdash_access_allowed_emails", items)
        for domain_wide in ("email_domain", "anyone", "everyone"):
            with self.subTest(selector=domain_wide):
                self.assertNotIn(
                    domain_wide,
                    items,
                    "a domain-wide selector widens the policy past the "
                    "exact allowlist; see cloudflare/README.md",
                )
        self.assertRegex(
            items,
            re.compile(r"\{\s*email\s*=\s*\{\s*email\s*="),
            "each allowlist entry must match one exact address",
        )


if __name__ == "__main__":
    unittest.main()
