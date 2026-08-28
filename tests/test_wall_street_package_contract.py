from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "wall-street"


class WallStreetPackageContractTests(unittest.TestCase):
    def test_operator_surface_files_exist(self):
        for name in ("index.html", "app.js", "styles.css", "server.mjs", "README.md", "REVERSE_ENGINEERING.md"):
            self.assertTrue((PACKAGE / name).is_file(), name)

    def test_public_interop_only(self):
        app = (PACKAGE / "app.js").read_text(encoding="utf-8")
        report = (PACKAGE / "REVERSE_ENGINEERING.md").read_text(encoding="utf-8")
        self.assertIn("external-embedding/embed-widget-advanced-chart.js", app)
        self.assertIn("window.location.href = 'tradingview:'", app)
        self.assertIn("wss://stream.binance.com:9443", app)
        self.assertIn("https://api.kucoin.com", app)
        self.assertIn("does **not** decompile", report)

    def test_server_keeps_secrets_out_of_browser_and_uses_restricted_csp(self):
        server = (PACKAGE / "server.mjs").read_text(encoding="utf-8")
        app = (PACKAGE / "app.js").read_text(encoding="utf-8")
        self.assertIn("process.env.ZWORKFORCE_URL", server)
        self.assertIn("frame-ancestors 'none'", server)
        self.assertIn("object-src 'none'", server)
        self.assertNotIn("'unsafe-inline'", server)
        self.assertNotIn("ZWORKFORCE_URL", app)
        self.assertNotIn("Authorization", app)
        self.assertNotIn("X-API-Key", app)


if __name__ == "__main__":
    unittest.main()
