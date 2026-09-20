import os
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[2]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class PublicProfileBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.playwright = sync_playwright().start()
        cls.browser_name = os.getenv("VAULT_TEST_BROWSER", "chromium")
        cls.browser = getattr(cls.playwright, cls.browser_name).launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 1280, "height": 900})
        self.page = self.context.new_page()

    def tearDown(self):
        self.context.close()

    def goto(self, username):
        self.page.goto(f"{self.url}/escapista/?u={username}&demo=1", wait_until="load")
        self.page.wait_for_function("document.getElementById('profile-loading').hidden")

    def test_full_profile_uses_only_public_projection(self):
        private_uid = "private-fixture-uid-should-never-render"
        private_email = "private-fixture@example.test"
        self.goto("isaac")
        expect(self.page.locator("#profile-public")).to_be_visible()
        expect(self.page.get_by_role("heading", name="Isaac", exact=True)).to_be_visible()
        expect(self.page.get_by_role("heading", name="Estadísticas personales")).to_be_visible()
        expect(self.page.get_by_role("heading", name="Mapa escapista")).to_be_visible()
        expect(self.page.get_by_role("heading", name="Logros")).to_be_visible()
        expect(self.page.get_by_role("heading", name="Rutas")).to_be_visible()
        expect(self.page.locator(".group-count strong")).to_have_text("3")
        expect(self.page.locator(".group-count span")).to_have_text("grupos escapistas")
        body = self.page.locator("body").inner_text()
        html = self.page.content()
        urls = self.page.evaluate("performance.getEntriesByType('resource').map(entry => entry.name).join('\\n')")
        for secret in (private_uid, private_email):
            self.assertNotIn(secret, body)
            self.assertNotIn(secret, html)
            self.assertNotIn(secret, urls)
        self.assertFalse(self.page.evaluate("Object.keys(VaultPublicProfilePage.currentView).some(key => /uid|email/i.test(key))"))

    def test_partial_profile_does_not_render_or_receive_hidden_sections(self):
        self.goto("LAURA")
        expect(self.page.get_by_role("heading", name="Laura", exact=True)).to_be_visible()
        expect(self.page.get_by_role("heading", name="Logros")).to_be_visible()
        for heading in ("Estadísticas personales", "Mapa escapista", "Rutas", "Grupos"):
            expect(self.page.get_by_role("heading", name=heading)).to_have_count(0)
        self.assertEqual(
            self.page.evaluate("['stats','map','routes','groupCount'].filter(key => Object.hasOwn(VaultPublicProfilePage.currentView,key))"),
            [],
        )

    def test_private_and_missing_profiles_are_indistinguishable(self):
        states = []
        for username in ("privado", "inexistente"):
            self.goto(username)
            expect(self.page.locator("#profile-unavailable")).to_be_visible()
            states.append(self.page.locator("#profile-unavailable").inner_text())
        self.assertEqual(states[0], states[1])

    def test_invalid_username_has_controlled_state(self):
        self.goto("ab")
        expect(self.page.locator("#profile-invalid")).to_be_visible()
        expect(self.page.get_by_role("heading", name="No podemos abrir este perfil.")).to_be_visible()

    def test_share_actions_and_card_respect_visible_sections(self):
        self.goto("laura")
        self.page.get_by_role("button", name="Compartir perfil").click()
        expect(self.page.locator("#share-dialog")).to_be_visible()
        self.assertGreater(self.page.locator("#share-card").evaluate("canvas => canvas.toDataURL().length"), 1000)
        whatsapp = self.page.locator("#share-whatsapp").get_attribute("href")
        self.assertIn("thevaultescape.com%2Fescapista%2F%3Fu%3Dlaura", whatsapp)
        self.assertEqual(self.page.evaluate("VaultPublicProfilePage.currentView.visibility.showStats"), False)
        self.assertEqual(self.page.evaluate("VaultPublicProfilePage.currentView.visibility.showRoutes"), False)

    def test_native_share_and_clipboard_fallback_use_the_public_url(self):
        self.context.add_init_script("""
          window.__sharedPayload = null;
          Object.defineProperty(navigator, 'share', { configurable: true, value: async value => { window.__sharedPayload = value; } });
          Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async value => { window.__copiedText = value; } } });
        """)
        self.goto("isaac")
        self.page.get_by_role("button", name="Compartir perfil").click()
        self.page.locator("#share-native").click()
        self.assertEqual(
            self.page.evaluate("window.__sharedPayload.url"),
            "https://thevaultescape.com/escapista/?u=isaac",
        )
        self.page.evaluate("delete navigator.share")
        self.page.locator("#share-native").click()
        expect(self.page.locator("#share-status")).to_have_text("Enlace copiado.")
        self.assertEqual(
            self.page.evaluate("window.__copiedText"),
            "https://thevaultescape.com/escapista/?u=isaac",
        )

    def test_share_dialog_keeps_keyboard_focus_and_closes_with_escape(self):
        self.goto("isaac")
        trigger = self.page.get_by_role("button", name="Compartir perfil")
        trigger.focus()
        trigger.click()
        expect(self.page.locator("#share-dialog")).to_be_visible()
        self.assertTrue(self.page.evaluate("document.querySelector('#share-dialog').contains(document.activeElement)"))
        self.page.keyboard.press("Escape")
        expect(self.page.locator("#share-dialog")).not_to_be_visible()

    def test_http_failure_has_a_controlled_error_state(self):
        self.page.route("**/firebase-config.js", lambda route: route.fulfill(
            status=200,
            content_type="application/javascript",
            body="window.THE_VAULT_FIREBASE_CONFIG={databaseURL:'https://profile-test.invalid'};",
        ))
        self.page.route("https://profile-test.invalid/**", lambda route: route.fulfill(status=500, body="{}"))
        self.page.goto(f"{self.url}/escapista/?u=isaac", wait_until="load")
        self.page.wait_for_function("document.getElementById('profile-loading').hidden")
        expect(self.page.locator("#profile-error")).to_be_visible()

    def test_public_profile_has_no_horizontal_overflow(self):
        self.goto("isaac")
        for width, height in ((375, 812), (390, 844), (430, 900), (768, 1024), (1280, 900)):
            with self.subTest(viewport=f"{width}x{height}"):
                self.page.set_viewport_size({"width": width, "height": height})
                dimensions = self.page.evaluate("({scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth})")
                available = width if self.browser_name == "webkit" else dimensions["clientWidth"]
                self.assertLessEqual(dimensions["scrollWidth"], available + 1)


if __name__ == "__main__":
    unittest.main()
