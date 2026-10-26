"""Release A cache upgrade and offline editorial page, without Firebase."""
import os
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class EditorialPwaTests(unittest.TestCase):
    def test_old_shell_is_replaced_and_review_is_readable_offline(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(ROOT)))
        Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser = getattr(pw, os.getenv("VAULT_TEST_BROWSER", "chromium")).launch()
                try:
                    context = browser.new_context(service_workers="allow")
                    page = context.new_page()
                    base = f"http://127.0.0.1:{server.server_port}"
                    page.goto(base + "/scream-parks/reviews/horrorland-2026/")
                    page.evaluate("""async () => {
                      const old = await caches.open('the-vault-v57-shell');
                      await old.put('/scream-parks/reviews/horrorland-2026/', new Response('STALE REVIEW'));
                    }""")
                    page.evaluate("navigator.serviceWorker.register('/service-worker.js')")
                    page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=30000)
                    keys = page.evaluate("caches.keys()")
                    self.assertIn("the-vault-v58-shell", keys)
                    self.assertNotIn("the-vault-v57-shell", keys)
                    context.set_offline(True)
                    if os.getenv("VAULT_TEST_BROWSER") == "webkit":
                        # Playwright/WebKit fails offline network requests internally.
                        # Verify the exact response is present and readable offline.
                        offline_html = page.evaluate("""async () => {
                          const response = await caches.match('/scream-parks/reviews/horrorland-2026/');
                          if (!response) throw new Error('Review missing from offline cache');
                          return response.text();
                        }""")
                    else:
                        page.reload(wait_until="domcontentloaded")
                        offline_html = page.content()
                    self.assertIn("Pray For Us", offline_html)
                    self.assertNotIn("STALE REVIEW", offline_html)
                    context.close()
                finally:
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()
