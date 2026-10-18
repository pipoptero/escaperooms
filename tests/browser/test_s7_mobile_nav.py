"""S7: iPhone safe area and single-row, accessible navigation regression."""

import os
import math
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
TABS = ("The Vault", "Escapes", "Scream Parks", "Reviews", "Ranking")
PANELS = ("thevault", "catalogo", "scream-parks", "hechos", "ranking")


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class MobileNavigationTests(unittest.TestCase):
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

    def open_page(self, width, height):
        context = self.browser.new_context(
            viewport={"width": width, "height": height},
            has_touch=width < 641,
            service_workers="block",
        )
        page = context.new_page()
        # Headless WebKit can expose a wider CSS viewport until it is resized.
        css_width = page.evaluate("innerWidth")
        if css_width != width:
            page.set_viewport_size(
                {"width": round(width * width / css_width), "height": round(height * width / css_width)}
            )
        self.assertEqual(page.evaluate("innerWidth"), width)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        response = page.goto(f"http://127.0.0.1:{self.server.server_port}/", wait_until="domcontentloaded")
        self.assertEqual(response.status, 200)
        page.locator(".vault-brand-logo").evaluate("img => img.decode()")
        return context, page, errors

    def test_mobile_single_row_safe_area_and_active_reveal(self):
        for width, height in ((390, 844), (375, 812), (320, 700)):
            with self.subTest(width=width):
                context, page, errors = self.open_page(width, height)
                try:
                    initial = page.evaluate("""() => {
                      const scroller=document.getElementById('main-tabs');
                      const tabs=[...scroller.querySelectorAll('.tab')].filter(x=>getComputedStyle(x).display!=='none');
                      const logo=document.querySelector('.vault-brand-logo').getBoundingClientRect();
                      const header=document.querySelector('header').getBoundingClientRect();
                      return {names:tabs.map(x=>x.textContent.trim().replace(/\\s+/g,' ')),
                        iconUrls:tabs.map(x=>x.querySelector('img')?.getAttribute('src')),
                        rows:new Set(tabs.map(x=>Math.round(x.getBoundingClientRect().top))).size,
                        scrollWidth:scroller.scrollWidth,clientWidth:scroller.clientWidth,
                        overflow:document.documentElement.scrollWidth-innerWidth,
                        htmlWidth:document.documentElement.getBoundingClientRect().width,
                        documentWidth:document.documentElement.scrollWidth,
                        logoTop:logo.top,logoBottom:logo.bottom,headerBottom:header.bottom,
                        naturalWidth:document.querySelector('.vault-brand-logo').naturalWidth,
                        overflowX:getComputedStyle(scroller).overflowX};
                    }""")
                    self.assertTrue(all(name.startswith(label) for name, label in zip(initial["names"], TABS)))
                    self.assertTrue(all(url and url.endswith(".png") for url in initial["iconUrls"]))
                    self.assertEqual(initial["rows"], 1)
                    self.assertGreater(initial["scrollWidth"], initial["clientWidth"])
                    self.assertLessEqual(initial["overflow"], 1)
                    self.assertLessEqual(initial["documentWidth"], math.ceil(initial["htmlWidth"]))
                    self.assertGreater(initial["naturalWidth"], 0)
                    self.assertGreaterEqual(initial["logoTop"], 8)
                    self.assertLessEqual(initial["logoBottom"], initial["headerBottom"])
                    self.assertEqual(initial["overflowX"], "auto")
                    self.assertEqual(page.locator("nav.main-tabs-shell").get_attribute("aria-label"), "Secciones principales")
                    self.assertTrue(page.locator("nav.main-tabs-shell").evaluate("nav => nav.classList.contains('can-scroll-right')"))

                    # Emulate a notched Safari viewport. Both expanded and collapsed
                    # browser bars must keep the complete wordmark below the safe area.
                    page.evaluate("document.documentElement.style.setProperty('--vault-safe-top','47px')")
                    for mobile_height in (height, max(540, height - 130)):
                        page.set_viewport_size({"width": page.viewport_size["width"], "height": mobile_height})
                        safe = page.evaluate("""() => {
                          const logo=document.querySelector('.vault-brand-logo').getBoundingClientRect();
                          const header=document.querySelector('header').getBoundingClientRect();
                          return {top:logo.top,bottom:logo.bottom,headerBottom:header.bottom};
                        }""")
                        self.assertGreaterEqual(safe["top"], 55)
                        self.assertLessEqual(safe["bottom"], safe["headerBottom"])

                    # Direct horizontal movement models touch scrolling; a tab
                    # selected programmatically must also be brought fully into view.
                    page.evaluate("document.getElementById('main-tabs').scrollLeft = 120")
                    page.wait_for_function("document.getElementById('main-tabs').scrollLeft > 40")
                    self.assertTrue(page.locator("nav.main-tabs-shell").evaluate("nav => nav.classList.contains('can-scroll-left')"))
                    page.locator("#tab-vault").focus()
                    page.evaluate("document.getElementById('main-tabs').scrollLeft = 0")
                    page.evaluate("switchTab('ranking')")
                    page.wait_for_function("""() => {
                      const s=document.getElementById('main-tabs').getBoundingClientRect();
                      const t=document.getElementById('tab-rank').getBoundingClientRect();
                      return t.left >= s.left + 10 && t.right <= s.right - 10;
                    }""")
                    self.assertEqual(page.locator('#tab-rank').get_attribute('aria-current'), 'page')
                    self.assertTrue(page.locator('#panel-ranking').is_visible())

                    for tab_id, panel in zip(
                        ("vault", "cat", "scream", "hecho", "rank"), PANELS
                    ):
                        page.locator(f"#tab-{tab_id}").click()
                        self.assertTrue(page.locator(f"#panel-{panel}").is_visible())
                        self.assertEqual(page.locator(f"#tab-{tab_id}").get_attribute("aria-current"), "page")
                    page.locator("#tab-vault").focus()
                    page.evaluate("""() => {
                      const s=document.getElementById('main-tabs');
                      s.style.scrollBehavior='auto'; s.scrollLeft=0;
                    }""")
                    page.wait_for_function("document.getElementById('main-tabs').scrollLeft < 2")
                    page.locator("#tab-rank").focus()
                    page.wait_for_function("""() => {
                      const s=document.getElementById('main-tabs').getBoundingClientRect();
                      const t=document.getElementById('tab-rank').getBoundingClientRect();
                      return document.activeElement.id==='tab-rank' && t.left>=s.left+10 && t.right<=s.right-10;
                    }""", timeout=5000)
                    page.evaluate("document.getElementById('main-tabs').style.removeProperty('scroll-behavior')")
                    page.emulate_media(reduced_motion="reduce")
                    self.assertEqual(page.locator('#main-tabs').evaluate("el => getComputedStyle(el).scrollBehavior"), "auto")
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth-innerWidth"), 1)
                    self.assertFalse(errors, errors)
                finally:
                    context.close()

    def test_desktop_navigation_remains_unwrapped(self):
        context, page, errors = self.open_page(1440, 900)
        try:
            state = page.evaluate("""() => {
              const s=document.getElementById('main-tabs');
              const tabs=[...s.querySelectorAll('.tab')].filter(x=>getComputedStyle(x).display!=='none');
              return {rows:new Set(tabs.map(x=>Math.round(x.getBoundingClientRect().top))).size,
                scrollWidth:s.scrollWidth,clientWidth:s.clientWidth,
                logoTop:document.querySelector('.vault-brand-logo').getBoundingClientRect().top,
                logoBottom:document.querySelector('.vault-brand-logo').getBoundingClientRect().bottom,
                headerBottom:document.querySelector('header').getBoundingClientRect().bottom,
                overflow:document.documentElement.scrollWidth-innerWidth};
            }""")
            self.assertEqual(state["rows"], 1)
            self.assertEqual(state["scrollWidth"], state["clientWidth"])
            self.assertGreaterEqual(state["logoTop"], 18)
            self.assertLessEqual(state["logoBottom"], state["headerBottom"])
            self.assertEqual(state["overflow"], 0)
            self.assertFalse(errors, errors)
        finally:
            context.close()


if __name__ == "__main__":
    unittest.main()
