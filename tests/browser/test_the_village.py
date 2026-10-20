"""The retired room link resolves to the single Scream Park detail."""

import os
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class TheVillageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.playwright = sync_playwright().start()
        cls.browser = getattr(cls.playwright, os.getenv("VAULT_TEST_BROWSER", "chromium")).launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def test_retired_url_and_exclusive_park_detail(self):
        for width in (1440, 390):
            with self.subTest(width=width):
                context = self.browser.new_context(
                    viewport={"width": width, "height": 900}, service_workers="block"
                )
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                try:
                    base = f"http://127.0.0.1:{self.server.server_port}"
                    page.goto(base + "/salas/the-village/", wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_url(base + "/#scream-park/the-village", timeout=60000)
                    page.locator("#sp-detail:not([hidden]) h1").wait_for(timeout=30000)
                    self.assertIn("The Village", page.locator("#sp-detail h1").inner_text())
                    self.assertEqual(page.locator("#tab-scream[aria-current='page']").count(), 1)
                    page.evaluate("ensureStaticEnhancementsLoaded()")
                    self.assertEqual(page.evaluate("CATALOGO.length"), 1733)
                    self.assertEqual(page.evaluate("CATALOGO.filter(r => r.id === 'the-village').length"), 0)
                    self.assertFalse(page.evaluate("rankingRooms().some(r => r.id === 'the-village')"))
                    self.assertEqual(page.locator("#sp-cards .card[data-id='the-village']").count(), 1)
                    self.assertIn("Berga", page.locator("#sp-detail").inner_text())
                    self.assertEqual(page.locator("#sp-detail iframe.sp-official-video").get_attribute("src"),
                                     "https://www.tiktok.com/player/v1/7693957517554060566")
                    self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2"))
                    self.assertEqual(errors, [])
                finally:
                    context.close()


if __name__ == "__main__":
    unittest.main()
