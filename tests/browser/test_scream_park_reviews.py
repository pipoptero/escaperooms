"""Release A editorial review on the integrated site and static SEO page."""
import json
import os
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
REVIEW = {
    "schemaVersion": 1,
    "reviews": [{"id": "horrorland-2026-the-vault", "entityId": "horrorland",
                 "seasonId": "horrorland-2026", "title": "Horrorland 2026",
                 "author": "The Vault", "status": "PUBLISHED", "body":
                 "# Horrorland 2026\n\n## Nuestra opinión\n\nPárrafo largo con **negrita**.\n\n"
                 "### Top 3\n\n- Pray For Us\n- Night Hunters\n- McAbro\n\n<script>alert(1)</script>"}]
}


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class V6BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
        Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.playwright = sync_playwright().start()
        cls.browser = getattr(cls.playwright, os.getenv("VAULT_TEST_BROWSER", "chromium")).launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def page(self, width):
        context = self.browser.new_context(viewport={"width": width, "height": 900}, service_workers="block")
        page = context.new_page()
        if page.evaluate("innerWidth") != width:
            actual = page.evaluate("innerWidth")
            page.set_viewport_size({"width": round(width * width / actual), "height": round(900 * width / actual)})
        page.route("**/scream-parks/editorial-reviews.json", lambda route:
                   route.fulfill(status=200, content_type="application/json", body=json.dumps(REVIEW)))
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        response = page.goto(f"http://127.0.0.1:{self.server.server_port}/", wait_until="domcontentloaded")
        self.assertEqual(response.status, 200)
        return context, page, errors

    def test_editorial_review_navigation_and_escape(self):
        for width in (1440, 390):
            with self.subTest(width=width):
                context, page, errors = self.page(width)
                try:
                    page.locator("#tab-scream").click()
                    page.locator("#panel-scream-parks article.card").first.wait_for()
                    page.locator("#panel-scream-parks article.card[data-id=horrorland] button").first.click()
                    self.assertEqual(page.locator(".sp-editorial-preview").count(), 1)
                    page.get_by_role("link", name="LEER REVIEW COMPLETA").click()
                    self.assertIn("/scream-parks/reviews/horrorland-2026/", page.url)
                    self.assertEqual(page.locator("main article h1").count(), 1)
                    self.assertIn("Pray For Us", page.locator(".review").inner_text())
                    self.assertEqual(page.locator(".review script").count(), 0)
                    self.assertFalse(page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"))
                    page.get_by_role("link", name="Ver ficha Scream Park").click()
                    page.locator(".sp-editorial-preview").wait_for()
                    self.assertEqual(page.locator(".sp-editorial-preview").count(), 1)
                    self.assertEqual(errors, [])
                finally:
                    context.close()

if __name__ == "__main__":
    unittest.main()
