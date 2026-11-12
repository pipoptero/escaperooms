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
                    page.locator("#panel-scream-parks article.card[data-id=horrorland]").get_by_role("button", name="VER FICHA", exact=True).click()
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
            page.locator('.vault-latest-grid button.vault-latest-card[onclick*="horrorland-2026"]').click()
            page.locator("#detail-modal.open").wait_for()
            page.go_back()
            self.assertEqual(page.locator("#detail-modal.open").count(), 0)
            page.locator("#tab-hecho").click()
            self.assertEqual(page.locator("[data-review-type]").count(), 2)
            self.assertEqual(page.locator("[data-review-type=escape]").get_attribute("aria-pressed"), "true")
            self.assertEqual(page.locator("#grid-hechos .scream-editorial-card").count(), 0)
            page.evaluate("""() => { const filter = document.querySelector('#filter-dif-hecho');
              filter.value = filter.querySelector('option:not([value=""])')?.value || '';
              filter.dispatchEvent(new Event('change')); }""")
            page.locator("[data-review-type=scream]").click()
            self.assertEqual(page.locator("#grid-hechos .scream-editorial-card").count(), 1)
            self.assertEqual(page.locator("#grid-hechos .review-row").count(), 1)
            self.assertEqual(page.locator("[data-review-type=scream]").get_attribute("aria-pressed"), "true")
            self.assertTrue(page.locator("#filter-dif-hecho").is_disabled())
            self.assertIn('1 reviews · Scream Parks', page.locator('#result-info-hecho').inner_text())
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
                    self.assertIn("The Village", page.locator(".vault-latest-grid .vault-latest-card").first.inner_text())
                    self.assertEqual(page.locator(".vault-latest-grid .vault-latest-card").count(), 3)
                    page.locator('.vault-latest-grid button.vault-latest-card[onclick*="horrorland-2026"]').click()
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
                    self.assertEqual(page.locator("#detail-modal .sp-editorial-body").count(), 1)
                    self.assertEqual(page.locator("#detail-modal .sp-review-aside").count(), 0)
                    self.assertEqual(page.locator("#detail-modal .sp-review-community").count(), 0)
                    banner = page.locator("#detail-modal .sp-review-banner img")
                    self.assertEqual(banner.evaluate("image => [image.naturalWidth, image.naturalHeight]"), [2048, 768])
                    self.assertEqual(banner.evaluate("image => getComputedStyle(image).objectFit"), "contain")
                    self.assertLess(page.locator("#detail-modal .sp-review-banner").evaluate("figure => figure.getBoundingClientRect().height") - banner.evaluate("image => image.getBoundingClientRect().height"), 2)
                    self.assertEqual(page.locator("#detail-modal .sp-review-expand").count(), 0)
                    self.assertEqual(page.locator("#detail-modal .sp-review-banner a").count(), 0)
                    asset_response = page.request.get(urljoin(page.url, banner.get_attribute("src")))
                    self.assertEqual(asset_response.status, 200)
                    self.assertIn("image/webp", asset_response.headers.get("content-type", ""))
                    self.assertEqual(page.locator("#detail-modal .sp-review-hero").count(), 0)
                    self.assertFalse(page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"))
                    self.assertEqual(errors, [])
                    photos = page.locator("#detail-modal .sp-visit-gallery img")
                    self.assertEqual(photos.count(), 9)
                    videos = page.locator("#detail-modal .sp-visit-video")
                    self.assertEqual(videos.count(), 2)
                    self.assertEqual(videos.evaluate_all("nodes => nodes.map(el => [el.preload, el.controls, el.playsInline, el.autoplay])"),
                                     [["none", True, True, False], ["none", True, True, False]])
                    photos.first.scroll_into_view_if_needed()
                    page.wait_for_function("() => document.querySelector('.scream-editorial-modal .sp-visit-gallery img')?.naturalWidth > 0")
                    page.locator("#detail-modal .sp-visit-gallery a").first.click()
                    self.assertTrue(page.locator("#photo-lightbox.open").is_visible())
                    page.keyboard.press("ArrowRight")
                    self.assertIn("2 / 9", page.locator("#photo-lightbox-count").inner_text())
                    page.keyboard.press("Escape")
                    self.assertEqual(page.locator("#photo-lightbox.open").count(), 0)
                    self.assertTrue(page.locator("#detail-modal .sp-visit-gallery a").first.evaluate("el => document.activeElement === el"))
                    if capture_dir:
                        page.locator("#detail-modal .sp-editorial-body p").last.scroll_into_view_if_needed()
                        page.screenshot(path=str(Path(capture_dir) / f"{self.browser.browser_type.name}-{width}-modal-end.png"))
                    page.reload(wait_until="domcontentloaded")
                    page.locator("#detail-modal.scream-editorial-modal.open").wait_for()
                    self.assertIn("Horrorland 2027", page.locator("#detail-modal .sp-editorial-body").inner_text())
                    page.keyboard.press("Escape")
                    self.assertEqual(page.locator("#detail-modal.open").count(), 0)
                    page.locator("#tab-hecho").click()
                    page.locator("[data-review-type=scream]").click()
                    page.locator("#grid-hechos .scream-editorial-card").first.wait_for()
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
            self.assertIn("The Village", page.locator(".vault-home-shell .vault-latest-grid .vault-latest-card").first.inner_text())
            self.assertEqual(page.locator(".vault-home-shell .vault-latest-grid .vault-latest-card").count(), 3)
            self.assertEqual(errors, [])
        finally:
            context.close()

    def test_short_mobile_viewport_keeps_full_review_and_actions_accessible(self):
        context, page, errors = self.page(390, mock=False)
        try:
            page.set_viewport_size({"width": 390, "height": 560})
            page.locator('.vault-latest-grid button.vault-latest-card[onclick*="horrorland-2026"]').click()
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
            self.assertEqual(page.locator("#sp-detail-content .sp-visit-gallery img").count(), 9)
            self.assertEqual(page.locator("#sp-detail-content .sp-visit-video").count(), 2)
            self.assertEqual(page.locator("#sp-detail-content .sp-visit-video-card figcaption").count(), 0)
            self.assertEqual(page.locator("#sp-detail-content > :last-child").get_attribute("id"), "sp-community")
            self.assertGreater(page.locator("#sp-detail-content #sp-community").evaluate("el => el.getBoundingClientRect().top"),
                               page.locator("#sp-detail-content .sp-visit-gallery").evaluate("el => el.getBoundingClientRect().top"))
            self.assertEqual(errors, [])
        finally:
            context.close()

    def test_visit_videos_play_inline_and_pause_each_other(self):
        context, page, errors = self.page(390, mock=False)
        try:
            media_requests = []
            page.on("request", lambda request: media_requests.append(request.url)
                    if "/horrorland-2026-visit/video-" in request.url and request.url.endswith(".mp4") else None)
            page.locator('.vault-latest-grid button.vault-latest-card[onclick*="horrorland-2026"]').click()
            page.locator("#detail-modal.scream-editorial-modal.open").wait_for()
            videos = page.locator("#detail-modal .sp-visit-video")
            self.assertEqual(videos.count(), 2)
            self.assertEqual(page.locator("#detail-modal .sp-visit-video-card figcaption").count(), 0)
            page.locator("#detail-modal .sp-visit-grid a").first.click()
            self.assertTrue(page.locator("#photo-lightbox-caption").is_hidden())
            self.assertEqual(page.locator("#photo-lightbox-count").inner_text(), "1 / 9")
            page.locator("#photo-lightbox .photo-lightbox-close").click()
            self.assertEqual(media_requests, [])
            self.assertEqual(videos.evaluate_all("nodes => nodes.map(el => el.currentSrc)"), ["", ""])
            for index in range(2):
                video = videos.nth(index)
                page.locator("#detail-modal .sp-visit-play").nth(index).click()
                page.wait_for_function("index => document.querySelectorAll('#detail-modal .sp-visit-video')[index].currentTime > 0", arg=index, timeout=15000)
                self.assertFalse(video.evaluate("el => el.paused && el.currentTime === 0"))
                self.assertTrue(page.locator("#detail-modal .sp-visit-play").nth(index).is_hidden())
            if self.browser.browser_type.name == "chromium":
                self.assertEqual(len(set(media_requests)), 2)
            self.assertTrue(videos.first.evaluate("el => el.paused"))
            self.assertEqual(errors, [])
        finally:
            context.close()

    def test_the_village_review_and_visit_gallery(self):
        for width in (1440, 390):
            with self.subTest(width=width):
                context, page, errors = self.page(width, mock=False)
                try:
                    captures = os.getenv("VAULT_VILLAGE_CAPTURE_DIR")
                    if captures:
                        Path(captures).mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(Path(captures) / f"{self.browser.browser_type.name}-{width}-home.png"))
                    page.locator('#tab-scream').click()
                    page.locator('#panel-scream-parks article.card[data-id="the-village"]').get_by_role("button", name="VER FICHA", exact=True).click()
                    page.locator('#sp-detail-content .sp-visit-gallery').wait_for()
                    self.assertEqual(page.locator('#sp-detail-content .sp-visit-gallery img').count(), 12)
                    self.assertEqual(page.locator('#sp-detail-content .sp-visit-video').count(), 0)
                    self.assertIn('NUESTRA VISITA EN FOTOS', page.locator('#sp-detail-content .sp-visit-gallery h2').inner_text().upper())
                    self.assertNotIn('VÍDEOS', page.locator('#sp-detail-content .sp-visit-gallery h2').inner_text().upper())
                    self.assertEqual(page.locator('#sp-detail-content > :last-child').get_attribute('id'), 'sp-community')
                    if captures:
                        page.screenshot(path=str(Path(captures) / f"{self.browser.browser_type.name}-{width}-detail.png"))
                    page.get_by_role('button', name='LEER REVIEW COMPLETA').click()
                    page.locator('#detail-modal.scream-editorial-modal.open').wait_for()
                    self.assertIn('#scream-park-review/the-village-2026', page.url)
                    self.assertEqual(page.locator('#detail-modal .sp-review-banner').count(), 0)
                    self.assertEqual(page.locator('#detail-modal .sp-review-hero img').count(), 1)
                    body = page.locator('#detail-modal .sp-editorial-body').inner_text()
                    self.assertGreater(len(body), 14000)
                    self.assertIn('Familia Krugger', body)
                    self.assertIn('Panic Test', body)
                    self.assertIn('The Garage', body)
                    self.assertIn('¡SIN DUDA!', body)
                    self.assertNotIn('THE VILLAGE — INSOMNIA', body)
                    self.assertEqual(page.locator('#detail-modal .sp-visit-gallery img').count(), 12)
                    self.assertEqual(page.locator('#detail-modal .sp-visit-video').count(), 0)
                    self.assertEqual(page.locator('#detail-modal .sp-visit-gallery h3').inner_text().upper(), 'NUESTRA VISITA EN FOTOS')
                    if captures:
                        page.screenshot(path=str(Path(captures) / f"{self.browser.browser_type.name}-{width}-modal.png"))
                    page.locator('#detail-modal .sp-visit-gallery a').first.click()
                    self.assertTrue(page.locator('#photo-lightbox.open').is_visible())
                    self.assertTrue(page.locator('#photo-lightbox-caption').is_hidden())
                    page.keyboard.press('ArrowRight')
                    self.assertEqual(page.locator('#photo-lightbox-count').inner_text(), '2 / 12')
                    page.keyboard.press('Escape')
                    self.assertEqual(page.locator('#photo-lightbox.open').count(), 0)
                    page.locator('#detail-modal .sp-editorial-body p').last.scroll_into_view_if_needed()
                    if captures:
                        page.screenshot(path=str(Path(captures) / f"{self.browser.browser_type.name}-{width}-modal-end.png"))
                    page.locator('#detail-modal .sp-review-return').click()
                    page.locator('#sp-detail:visible').wait_for()
                    self.assertEqual(page.locator('#sp-detail-content .sp-visit-gallery img').count(), 12)
                    self.assertEqual(page.locator('#sp-detail-content > :last-child').get_attribute('id'), 'sp-community')
                    page.locator('#tab-hecho').click()
                    page.locator('[data-review-type=scream]').click()
                    page.locator('#grid-hechos .scream-editorial-card').first.wait_for()
                    self.assertEqual(page.locator('#grid-hechos .scream-editorial-card').count(), 2)
                    self.assertEqual(page.locator('#grid-hechos .scream-editorial-card').filter(has_text='The Village').count(), 1)
                    self.assertFalse(page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth'))
                    page.goto(f'http://127.0.0.1:{self.server.server_port}/scream-parks/reviews/the-village-2026/')
                    self.assertEqual(page.locator('link[rel="canonical"]').get_attribute('href'),
                                     'https://thevaultescape.com/scream-parks/reviews/the-village-2026/')
                    self.assertEqual(page.locator('.scream-visit-grid img').count(), 12)
                    self.assertEqual(page.locator('.scream-visit-grid').locator('..').locator('h2').inner_text().upper(), 'NUESTRA VISITA EN FOTOS')
                    self.assertFalse(page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth'))
                    self.assertEqual(errors, [])
                finally:
                    context.close()

    def test_seo_page_uses_same_playable_videos(self):
        context, page, errors = self.page(390, mock=False)
        try:
            base = f"http://127.0.0.1:{self.server.server_port}"
            html = (ROOT / "scream-parks/reviews/horrorland-2026/index.html").read_text(encoding="utf-8")
            html = html.replace("https://thevaultescape.com/images/scream-parks/horrorland-2026-visit/",
                                base + "/images/scream-parks/horrorland-2026-visit/")
            page.route(base + "/scream-parks/reviews/horrorland-2026/",
                       lambda route: route.fulfill(body=html, content_type="text/html"))
            page.goto(base + "/scream-parks/reviews/horrorland-2026/", wait_until="domcontentloaded")
            videos = page.locator(".scream-visit-video-card video")
            self.assertEqual(videos.count(), 2)
            self.assertEqual(page.locator(".scream-visit-video-card figcaption").count(), 0)
            self.assertEqual(videos.evaluate_all("nodes => nodes.map(el => el.preload)"), ["none", "none"])
            self.assertEqual(videos.evaluate_all("nodes => nodes.map(el => el.currentSrc)"), ["", ""])
            for index in range(2):
                page.locator(".scream-visit-video-card .sp-visit-play").nth(index).click()
                page.wait_for_function("index => document.querySelectorAll('.scream-visit-video-card video')[index].currentTime > 0", arg=index, timeout=15000)
            self.assertFalse(page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"),
                             page.evaluate("[...document.querySelectorAll('*')].filter(el => el.getBoundingClientRect().right > innerWidth + 1).slice(0, 12).map(el => [el.tagName, el.className, Math.round(el.getBoundingClientRect().x), Math.round(el.getBoundingClientRect().width), getComputedStyle(el).width, getComputedStyle(el).maxWidth, Math.round(el.parentElement.getBoundingClientRect().width)])"))
            self.assertEqual(errors, [])
        finally:
            context.close()

if __name__ == "__main__":
    unittest.main()
