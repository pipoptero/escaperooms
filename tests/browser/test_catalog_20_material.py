"""Real card/detail smoke for the catalog editorial batch and Haunt videos."""

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


class CatalogMaterialBrowserTests(unittest.TestCase):
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

    def test_cards_synopses_and_haunt_videos(self):
        for width in (1440, 390):
            with self.subTest(width=width):
                context = self.browser.new_context(
                    viewport={"width": width, "height": 900}, service_workers="block"
                )
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                try:
                    page.goto(f"http://127.0.0.1:{self.server.server_port}/", wait_until="domcontentloaded")
                    result = page.evaluate("""async () => {
                      await Promise.all([loadCatalogo(), loadOfficialVideos()]);
                      const ids = ['umbra', 'oh-fortuna', 'ecos-de-los-antiguos', 'haunt',
                        'gastro-escape-experiencity', 'academia-de-detectives'];
                      return {
                        count: CATALOGO.length,
                        cards: ids.map(id => {
                          const room = CATALOGO.find(r => r.id === id);
                          const container = document.createElement('div');
                          if (room) container.innerHTML = cardCatalogo(room, 0);
                          return {id, found: !!room, cover: !!container.querySelector('img'),
                            synopsis: (room?.descripcion || '').length};
                        })
                      };
                    }""")
                    self.assertEqual(result["count"], 1752)
                    self.assertTrue(all(card["found"] and card["cover"] and card["synopsis"] > 100
                                        for card in result["cards"]), result["cards"])
                    page.evaluate("openDetail('catalogo', 'haunt')")
                    self.assertEqual(page.locator("#detail-content .detail-video-card").count(), 3)
                    self.assertEqual(page.locator("#detail-content .detail-video-source-link").count(), 3)
                    text = page.locator("#detail-content .detail-desc").inner_text()
                    for mode in ("MISTERIO", "TERROR", "HAUNT"):
                        self.assertIn(mode, text.upper())
                    page.locator("#detail-content .detail-video-preview").first.click()
                    self.assertIn("videopress.com/embed/mKQdybBt",
                                  page.locator("#detail-content iframe.detail-video-frame").get_attribute("src"))
                    self.assertEqual(errors, [])
                    self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2"))
                finally:
                    context.close()


if __name__ == "__main__":
    unittest.main()
