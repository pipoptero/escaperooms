"""Render every linked 10Escapes 2026 TOP 10 award in the real card and detail components."""
import json
import os
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
POSITIONS = json.loads((ROOT / "tests/fixtures/tenescapes_top10_2026.json").read_text(encoding="utf-8"))["positions"]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class TenEscapesBrowserTests(unittest.TestCase):
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

    def test_card_and_detail_badges_for_all_official_positions(self):
        for width in (1440, 390):
            with self.subTest(width=width):
                context = self.browser.new_context(viewport={"width": width, "height": 900}, service_workers="block")
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                try:
                    page.goto(f"http://127.0.0.1:{self.server.server_port}/", wait_until="domcontentloaded")
                    results = page.evaluate("""async positions => {
                      await loadCatalogo(); await loadExtraAwards();
                      return positions.map(p => {
                        const room = CATALOGO.find(r => r.id === p.canonical_room_id);
                        if (!room) return {id:p.canonical_room_id, card:'', detail:''};
                        const card = document.createElement('div');
                        card.innerHTML = cardCatalogo(room, 0);
                        const detail = document.createElement('div');
                        detail.innerHTML = detailAwardsHtml(room);
                        const cardBadge = [...card.querySelectorAll('.award-seal.award-10escapes')]
                          .find(el => el.textContent.includes('#' + p.rank + ' · 2026') && el.textContent.includes(p.category));
                        const detailBadge = [...detail.querySelectorAll('.detail-award')]
                          .find(el => el.textContent.includes('10Escapes') && el.textContent.includes('Top ' + p.category[0] + p.category.slice(1).toLowerCase()) && el.textContent.includes('#' + p.rank));
                        return {id:room.id, card:!!cardBadge, detail:!!detailBadge,
                          logo:cardBadge?.querySelector('img')?.getAttribute('src') || ''};
                      });
                    }""", [p for p in POSITIONS if p["canonical_room_id"]])
                    self.assertEqual(len(results), 26)
                    for result in results:
                        with self.subTest(id=result["id"]):
                            self.assertTrue(result["card"], result)
                            self.assertTrue(result["detail"], result)
                            self.assertEqual(result["logo"], "images/awards/10escapes-logo.png")
                    self.assertFalse(errors, errors)
                finally:
                    context.close()


if __name__ == "__main__":
    unittest.main()
