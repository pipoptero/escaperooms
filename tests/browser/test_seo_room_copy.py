"""SEO room copy with real browser layout; all data is local and read-only."""

import importlib.util
import json
import os
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("build_seo_pages", ROOT / "scripts" / "build_seo_pages.py")
SEO = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SEO)


class SeoRoomCopyBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def handle(self):
                try:
                    super().handle()
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                    pass

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.playwright = sync_playwright().start()
        cls.browser = getattr(cls.playwright, os.getenv("VAULT_TEST_BROWSER", "chromium")).launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def test_all_availability_cases_at_desktop_and_mobile_width(self):
        village = next(room for room in json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))["catalogo"]
                       if room.get("id") == "the-village")
        cases = (
            ("both", {"duracion": 60, "min_personas": 2, "max_personas": 4}, "ubicación, duración, jugadores"),
            ("duration", {"duracion": 60}, "ubicación, duración"),
            ("players", {"min_personas": 2}, "ubicación, jugadores"),
            ("neither", {}, "ubicación y enlaces"),
            ("the-village", village, "ubicación y enlaces"),
        )
        for width in (1440, 390):
            for label, values, expected in cases:
                with self.subTest(width=width, case=label):
                    room = {"id": "seo-copy-fixture", "nombre": "Prueba", "empresa": "Operador", "ciudad": "Bilbao", **values}
                    if label == "the-village":
                        room = values
                    html = SEO.room_page({"room": room, "rating": {}, "meta": {}}, 0)
                    context = self.browser.new_context(viewport={"width": width, "height": 850}, service_workers="block")
                    target = self.url + "/salas/seo-copy-fixture/"
                    context.route("**/*", lambda route: (
                        route.fulfill(status=200, content_type="text/html; charset=utf-8", body=html)
                        if route.request.url == target else
                        route.continue_() if urlparse(route.request.url).hostname == "127.0.0.1" else
                        route.abort()
                    ))
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    try:
                        page.goto(target, wait_until="domcontentloaded")
                        copy = page.locator("main .detail-hero > div > p").first.inner_text()
                        self.assertIn(expected, copy)
                        if label in ("neither", "the-village"):
                            self.assertNotIn("duración", copy)
                            self.assertNotIn("jugadores", copy)
                        self.assertFalse(page.evaluate("document.documentElement.scrollWidth > innerWidth"))
                        self.assertEqual(errors, [])
                    finally:
                        context.close()


if __name__ == "__main__":
    unittest.main()
