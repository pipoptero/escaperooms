"""Province-only labels in the catalog UI. Run with VAULT_TEST_BROWSER=chromium|webkit."""

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

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass


class LocationFallbackTests(unittest.TestCase):
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

    def test_location_scope_and_existing_catalog_cards(self):
        for width, height in ((1440, 900), (390, 844)):
            with self.subTest(width=width):
                context = self.browser.new_context(
                    viewport={"width": width, "height": height},
                    service_workers="block",
                )
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                try:
                    page.goto(
                        f"http://127.0.0.1:{self.server.server_port}/",
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )
                    page.wait_for_function(
                        "typeof CATALOGO !== 'undefined' && "
                        "CATALOGO.some(room => room.id === 'el-casino-royal') && "
                        "document.body.classList.contains('app-ready')",
                        timeout=60000,
                    )
                    cases = page.evaluate("""() => [
                      {ciudad:'Berga',provincia:'Barcelona',comunidad:'Catalunya'},
                      {ciudad:'Madrid',provincia:'Madrid',comunidad:'Madrid'},
                      {ciudad:'',provincia:'Barcelona',comunidad:'Catalunya'},
                      {ciudad:'',provincia:'',comunidad:'Catalunya'},
                      {ciudad:'',provincia:'',comunidad:''}
                    ].map(room => [publicRoomLocation(room), publicRoomLocation(room,true)])""")
                    self.assertEqual(cases, [
                        ["Berga - Barcelona", "Berga - Barcelona - Catalunya"],
                        ["Madrid - Madrid", "Madrid - Madrid - Madrid"],
                        ["Provincia de Barcelona", "Provincia de Barcelona - Catalunya"],
                        ["", "Catalunya"],
                        ["", ""],
                    ])
                    blast_radius = page.evaluate("""() => {
                      const changedCard=[], changedDetail=[];
                      CATALOGO.forEach(room => {
                        const oldCard=[cleanValue(room.ciudad),cleanValue(room.provincia)]
                          .filter(Boolean).join(' - ');
                        const oldDetail=[
                          cleanValue(room.ciudad),cleanValue(room.provincia),
                          cleanValue(communityOf(room))
                        ].filter(Boolean).join(' - ');
                        if(oldCard!==publicRoomLocation(room)) changedCard.push(room.id);
                        if(oldDetail!==publicRoomLocation(room,true)) changedDetail.push(room.id);
                      });
                      return {changedCard,changedDetail,expected:CATALOGO
                        .filter(room=>!room.ciudad && room.provincia).map(room=>room.id)};
                    }""")
                    self.assertEqual(sorted(blast_radius["changedCard"]), sorted(blast_radius["expected"]))
                    self.assertEqual(sorted(blast_radius["changedDetail"]), sorted(blast_radius["expected"]))
                    self.assertNotIn("the-village", blast_radius["expected"])
                    cards = page.evaluate("""() => {
                      const ids=['el-casino-royal','base-secreta','la-sucursal'];
                      return ids.map(id => {
                        const room=CATALOGO.find(item => item.id===id);
                        return [id,room && cardCatalogo(room,0)];
                      });
                    }""")
                    self.assertTrue(all(html for _, html in cards))
                    self.assertIn("Provincia de Barcelona", cards[0][1])
                    self.assertIn("Provincia de Madrid", cards[1][1])
                    self.assertIn("Sant Feliu de Codines - Barcelona", cards[2][1])
                    page.evaluate("""() => {
                      const room=CATALOGO.find(item=>item.id==='el-casino-royal');
                      openDetail('catalogo',roomKey(room));
                    }""")
                    self.assertIn(
                        "Provincia de Barcelona",
                        page.locator("#detail-content").inner_text(),
                    )
                    self.assertFalse(errors, errors)
                    self.assertTrue(
                        page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
                    )
                finally:
                    context.close()


if __name__ == "__main__":
    unittest.main()
