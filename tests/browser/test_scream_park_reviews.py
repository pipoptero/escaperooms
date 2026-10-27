"""Release A editorial review on the integrated site and static SEO page."""
import json
import os
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
REVIEW = {
    "schemaVersion": 1,
    "reviews": [{"id": "horrorland-2026-the-vault", "entityId": "horrorland",
                 "seasonId": "horrorland-2026", "title": "Horrorland 2026",
                 "author": "The Vault", "status": "PUBLISHED", "publishedAt": "2026-10-26", "body":
                 "# Horrorland 2026\n\n## Nuestra opinión\n\nPárrafo largo con **negrita**.\n\n"
                 "### Top 3\n\n- Pray For Us\n- Night Hunters\n- McAbro\n\n<script>alert(1)</script>"}]
}


class QuietHandler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".webp": "image/webp"}

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

    def page(self, width, mock=True):
        context = self.browser.new_context(viewport={"width": width, "height": 900}, service_workers="block")
        page = context.new_page()
        if page.evaluate("innerWidth") != width:
            actual = page.evaluate("innerWidth")
            page.set_viewport_size({"width": round(width * width / actual), "height": round(900 * width / actual)})
        if mock:
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
                    page.get_by_role("button", name="LEER REVIEW COMPLETA").click()
                    page.locator("#detail-modal.scream-editorial-modal.open").wait_for()
                    self.assertIn("#scream-park-review/horrorland-2026", page.url)
                    self.assertIn("Pray For Us", page.locator("#detail-modal .sp-editorial-body").inner_text())
                    self.assertIn("Night Hunters", page.locator("#detail-modal .sp-editorial-body").inner_text())
                    self.assertIn("McAbro", page.locator("#detail-modal .sp-editorial-body").inner_text())
                    self.assertEqual(page.locator("#detail-modal .sp-editorial-body script").count(), 0)
                    self.assertEqual(page.locator("#detail-modal a[href='/scream-parks/reviews/horrorland-2026/']").count(), 0)
                    self.assertEqual(page.get_by_role("button", name="Abrir página SEO").count(), 0)
                    self.assertEqual(page.locator("#detail-modal .sp-review-brand").count(), 1)
                    self.assertEqual(page.locator("#detail-modal .sp-editorial-footer button").count(), 2)
                    self.assertEqual(page.evaluate("document.body.style.overflow"), "hidden")
                    self.assertFalse(page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"))
                    self.assertLessEqual(page.locator("#detail-content").evaluate("el => el.scrollWidth - el.clientWidth"), 1)
                    page.locator("#detail-modal .detail-close").focus()
                    page.keyboard.press("Shift+Tab")
                    self.assertTrue(page.locator("#detail-modal .sp-review-return").evaluate("el => document.activeElement === el"))
                    page.keyboard.press("Tab")
                    self.assertTrue(page.locator("#detail-modal .detail-close").evaluate("el => document.activeElement === el"))
                    page.keyboard.press("Escape")
                    self.assertEqual(page.locator("#detail-modal.open").count(), 0)
                    page.locator(".sp-editorial-preview").wait_for()
                    self.assertEqual(page.locator(".sp-editorial-preview").count(), 1)
                    self.assertEqual(errors, [])
                finally:
                    context.close()

    def test_latest_reviews_filter_and_history(self):
        context, page, errors = self.page(390)
        try:
            page.locator(".vault-latest-grid .vault-latest-card").first.wait_for()
            self.assertIn("Horrorland", page.locator(".vault-latest-grid .vault-latest-card").first.inner_text())
            page.locator(".vault-latest-grid .vault-latest-card").first.click()
            page.locator("#detail-modal.open").wait_for()
            page.go_back()
            self.assertEqual(page.locator("#detail-modal.open").count(), 0)
            page.locator("#tab-hecho").click()
            page.locator("[data-review-type=scream]").click()
            self.assertEqual(page.locator("#grid-hechos .scream-editorial-card").count(), 1)
            self.assertEqual(page.locator("#grid-hechos .review-row").count(), 1)
            page.locator("#grid-hechos .scream-editorial-card .rv-read-full").click()
            page.locator("#detail-modal.scream-editorial-modal.open").wait_for()
            page.go_back()
            self.assertEqual(page.locator("#detail-modal.open").count(), 0)
            page.locator("[data-review-type=escape]").click()
            self.assertEqual(page.locator("#grid-hechos .scream-editorial-card").count(), 0)
            self.assertEqual(errors, [])
        finally:
            context.close()

    def test_published_review_and_deep_link(self):
        for width in (1440, 390):
            with self.subTest(width=width):
                context, page, errors = self.page(width, mock=False)
                try:
                    page.locator(".vault-latest-grid .vault-latest-card").first.wait_for()
                    capture_dir = os.getenv("VAULT_V61_CAPTURE_DIR")
                    if capture_dir:
                        Path(capture_dir).mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(Path(capture_dir) / f"{self.browser.browser_type.name}-{width}-home.png"))
                    self.assertIn("Horrorland 2026", page.locator(".vault-latest-grid .vault-latest-card").first.inner_text())
                    self.assertEqual(page.locator(".vault-latest-grid .vault-latest-card").count(), 3)
                    page.locator(".vault-latest-grid .vault-latest-card").first.click()
                    page.locator("#detail-modal.scream-editorial-modal.open").wait_for()
                    page.wait_for_function("() => document.querySelector('.sp-review-banner img')?.naturalWidth === 2048")
                    if capture_dir:
                        page.screenshot(path=str(Path(capture_dir) / f"{self.browser.browser_type.name}-{width}-modal.png"))
                    text = page.locator("#detail-modal .sp-editorial-body").inner_text()
                    self.assertIn("¡GRACIAS POR HACERNOS PASAR TANTO MIEDO", text)
                    self.assertIn("Horrorland 2027", text)
                    self.assertIn("Dr. Heinz's Asylum", text)
                    self.assertIn("Route 666", text)
                    self.assertGreater(len(text), 14000)
                    self.assertEqual(page.locator("#detail-modal .sp-review-qualities .sp-review-fact").count(), 6)
                    self.assertIn("espectacular", page.locator("#detail-modal .sp-review-qualities").inner_text().lower())
                    self.assertNotIn("★", page.locator("#detail-modal .sp-review-qualities").inner_text())
                    banner = page.locator("#detail-modal .sp-review-banner img")
                    self.assertEqual(banner.evaluate("image => [image.naturalWidth, image.naturalHeight]"), [2048, 768])
                    self.assertEqual(banner.evaluate("image => getComputedStyle(image).objectFit"), "contain")
                    self.assertEqual(page.locator("#detail-modal .sp-review-poster img").evaluate("image => image.naturalWidth"), 900)
                    expanded = page.locator("#detail-modal .sp-review-banner a")
                    self.assertEqual(expanded.get_attribute("target"), "_blank")
                    self.assertEqual(expanded.get_attribute("rel"), "noopener noreferrer")
                    asset_response = page.request.get(urljoin(page.url, expanded.get_attribute("href")))
                    self.assertEqual(asset_response.status, 200)
                    self.assertIn("image/webp", asset_response.headers.get("content-type", ""))
                    self.assertEqual(page.locator("#detail-modal .sp-review-hero").count(), 0)
                    self.assertFalse(page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"))
                    self.assertEqual(errors, [])
                    if width == 390:
                        with context.expect_page() as new_page:
                            expanded.click()
                        enlarged = new_page.value
                        enlarged.wait_for_url("**/horrorland-2026-banner.webp*", wait_until="commit")
                        self.assertIn("horrorland-2026-banner.webp", enlarged.url)
                        self.assertEqual(enlarged.locator("img").evaluate("image => image.naturalWidth"), 2048)
                        enlarged.close()
                    if capture_dir:
                        page.locator("#detail-modal .sp-editorial-body p").last.scroll_into_view_if_needed()
                        page.screenshot(path=str(Path(capture_dir) / f"{self.browser.browser_type.name}-{width}-modal-end.png"))
                    page.reload(wait_until="domcontentloaded")
                    page.locator("#detail-modal.scream-editorial-modal.open").wait_for()
                    self.assertIn("Horrorland 2027", page.locator("#detail-modal .sp-editorial-body").inner_text())
                    page.keyboard.press("Escape")
                    self.assertEqual(page.locator("#detail-modal.open").count(), 0)
                    page.locator("#tab-hecho").click()
                    page.locator("#grid-hechos .scream-editorial-card").wait_for()
                    if capture_dir:
                        page.screenshot(path=str(Path(capture_dir) / f"{self.browser.browser_type.name}-{width}-reviews.png"))
                finally:
                    context.close()

    def test_latest_reviews_in_signed_in_home_shell(self):
        context, page, errors = self.page(390, mock=False)
        try:
            page.locator(".vault-latest-grid .vault-latest-card").first.wait_for()
            page.evaluate("AUTH_USER = {uid:'v61-local-test', displayName:'Prueba'}; renderVaultGuide()")
            page.locator(".vault-home-shell .vault-latest-grid .vault-latest-card").first.wait_for()
            self.assertIn("Horrorland", page.locator(".vault-home-shell .vault-latest-grid .vault-latest-card").first.inner_text())
            self.assertEqual(page.locator(".vault-home-shell .vault-latest-grid .vault-latest-card").count(), 3)
            self.assertEqual(errors, [])
        finally:
            context.close()

    def test_short_mobile_viewport_keeps_full_review_and_actions_accessible(self):
        context, page, errors = self.page(390, mock=False)
        try:
            page.set_viewport_size({"width": 390, "height": 560})
            page.locator(".vault-latest-grid .vault-latest-card").first.click()
            page.locator("#detail-modal.scream-editorial-modal.open").wait_for()
            content = page.locator("#detail-content")
            self.assertGreater(content.evaluate("el => el.scrollHeight"), content.evaluate("el => el.clientHeight"))
            content.evaluate("el => { el.scrollTop = el.scrollHeight; }")
            self.assertTrue(page.locator("#detail-modal .sp-review-return").is_visible())
            self.assertTrue(page.locator("#detail-modal .detail-close").is_visible())
            self.assertIn("Horrorland 2027", page.locator("#detail-modal .sp-editorial-body").inner_text())
            self.assertFalse(page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"))
            page.locator("#detail-modal .sp-review-return").click()
            page.locator("#sp-detail:visible").wait_for()
            self.assertEqual(page.locator("#detail-modal.open").count(), 0)
            self.assertIn("Horrorland", page.locator("#sp-detail-content").inner_text())
            self.assertEqual(errors, [])
        finally:
            context.close()

if __name__ == "__main__":
    unittest.main()
