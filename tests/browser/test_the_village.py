"""The Village catalog, location, cover and official vertical video smoke."""

import os
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
EMBED = "https://www.tiktok.com/player/v1/7693957517554060566"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class TheVillageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT))
        )
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.playwright = sync_playwright().start()
        cls.browser = getattr(
            cls.playwright, os.getenv("VAULT_TEST_BROWSER", "chromium")
        ).launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def test_catalog_and_static_page(self):
        for width, height in ((1440, 900), (390, 844)):
            with self.subTest(width=width):
                context = self.browser.new_context(
                    viewport={"width": width, "height": height}, service_workers="block"
                )
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                try:
                    base = f"http://127.0.0.1:{self.server.server_port}"
                    page.goto(base + "/", wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_function(
                        "typeof CATALOGO !== 'undefined' && "
                        "CATALOGO.some(room => room.id === 'the-village') && "
                        "OFFICIAL_VIDEOS_LOADED === true && "
                        "document.body.classList.contains('app-ready')",
                        timeout=60000,
                    )
                    self.assertEqual(
                        page.evaluate("CATALOGO.filter(r => r.id === 'the-village').length"), 1
                    )
                    page.evaluate("openDetail('catalogo','the-village')")
                    page.locator(".detail-video-preview").wait_for(timeout=15000)
                    self.assertEqual(
                        page.locator(".detail-video-source").text_content().strip(),
                        "TikTok oficial",
                    )
                    detail = page.locator("#detail-content").inner_text()
                    self.assertIn("Provincia de Barcelona", detail)
                    self.assertIn("cerca de Berga", detail)
                    self.assertNotIn("300 min", detail)
                    self.assertIn(
                        "the-village.webp",
                        page.locator("#detail-media img").first.get_attribute("src"),
                    )
                    page.locator(".detail-video-preview").click()
                    frame = page.locator("#detail-content iframe.detail-video-frame")
                    frame.wait_for(timeout=10000)
                    self.assertEqual(frame.get_attribute("src"), EMBED)
                    self.assertNotIn("autoplay=1", frame.get_attribute("src"))
                    box = frame.bounding_box()
                    self.assertGreater(box["height"], box["width"] * 1.6)
                    self.assertTrue(
                        page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
                    )
                    page.goto(base + "/salas/the-village/", wait_until="domcontentloaded")
                    page.wait_for_function(
                        "[...document.styleSheets].some(sheet => "
                        "sheet.href && sheet.href.endsWith('/seo.css'))",
                        timeout=15000,
                    )
                    self.assertIn("The Village", page.locator("h1").inner_text())
                    self.assertIn("Provincia de Barcelona", page.locator(".meta .pill").inner_text())
                    description = page.locator('meta[name="description"]').get_attribute("content")
                    self.assertIn("provincia de Barcelona", description)
                    self.assertNotIn("jugadores", description.lower())
                    self.assertNotIn("duración", description.lower())
                    self.assertEqual(page.locator("iframe.video-frame.portrait").get_attribute("src"), EMBED)
                    self.assertIn("the-village.webp", page.locator("img.cover").get_attribute("src"))
                    self.assertTrue(
                        page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
                    )
                    self.assertFalse(errors, errors)
                finally:
                    context.close()


if __name__ == "__main__":
    unittest.main()
