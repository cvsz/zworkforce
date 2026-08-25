from pathlib import Path
import unittest

from zworkforce import __version__


ROOT = Path(__file__).resolve().parents[1]


class StaticAssetTests(unittest.TestCase):
    def test_dashboard_version_matches_package_version(self):
        html = (ROOT / "zworkforce" / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn(f"zWorkforce v{__version__}", html)
        self.assertIn(f'class="version">v{__version__}</span>', html)
        self.assertNotIn("v2.0.0", html)

    def test_dashboard_exposes_prometa_install_action(self):
        html = (ROOT / "zworkforce" / "static" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "zworkforce" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("prometaInstallBtn", html)
        self.assertIn("/api/v1/prometa/install", app)

    def test_dashboard_exposes_accessible_zarvis_push_to_talk_card(self):
        html = (ROOT / "zworkforce" / "static" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "zworkforce" / "static" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "zworkforce" / "static" / "styles.css").read_text(encoding="utf-8")
        worklet = (ROOT / "zworkforce" / "static" / "zarvis-voice-worklet.js").read_text(encoding="utf-8")
        self.assertIn('id="zarvisCard"', html)
        self.assertIn('id="zarvisPtt"', html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn("/api/v1/zarvis/voice/session", app)
        # Keyboard/pointer semantics now live in the shared voice client and are
        # behavior-tested by packages/zarvis/packages/voice-client/test/browser.test.mjs.
        # The dashboard contract is that it delegates PTT to that shared client.
        self.assertIn("ZarvisVoiceClient", app)
        self.assertIn("VC.bindPushToTalk", app)
        self.assertIn("response.cancel", app)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("zworkforce-voice-capture", worklet)

    def test_dashboard_exposes_accessible_zarvis_agent_reasoning_hud(self):
        html = (ROOT / "zworkforce" / "static" / "index.html").read_text(encoding="utf-8")
        hud_js = (ROOT / "zworkforce" / "static" / "zarvis-hud.js").read_text(encoding="utf-8")
        hud_css = (ROOT / "zworkforce" / "static" / "zarvis-hud.css").read_text(encoding="utf-8")

        self.assertIn('id="zarvisReasoningWeb"', html)
        self.assertIn('id="zarvisAgentOverview"', html)
        self.assertIn('id="zarvisHudState"', html)
        self.assertIn('src="/zarvis-hud.js"', html)
        self.assertIn('href="/zarvis-hud.css"', html)
        self.assertIn("MutationObserver", hud_js)
        self.assertIn("aria-label", hud_js)
        self.assertIn("event.key==='Enter'", hud_js)
        self.assertIn("event.key==='Escape'", hud_js)
        self.assertIn("prefers-reduced-motion", hud_css)
        self.assertNotIn("three", hud_js.lower())
        self.assertNotIn("webgl", hud_js.lower())

    def test_static_voice_assets_contain_no_server_secret_configuration_names(self):
        combined = "\n".join(
            (ROOT / "zworkforce" / "static" / name).read_text(encoding="utf-8")
            for name in (
                "index.html",
                "app.js",
                "styles.css",
                "zarvis-voice-worklet.js",
                "zarvis-hud.js",
                "zarvis-hud.css",
            )
        )
        for forbidden in (
            "ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN",
            "Z_PLATFORM_SERVICE_TOKEN",
            "VOICE_TICKET_SECRET",
            "ZARVIS_EDGE_SHARED_SECRET",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
