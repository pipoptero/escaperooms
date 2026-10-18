"""S8: the five primary mobile tabs fit without scrolling."""

import math
import os
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
IDS = ("vault", "cat", "scream", "hecho", "rank")
PANELS = ("thevault", "catalogo", "scream-parks", "hechos", "ranking")
LABELS = ("The Vault", "Escapes", "Scream Parks", "Reviews", "Ranking")


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class MobileNavigationTests(unittest.TestCase):
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

    def open_page(self, width, height):
        context = self.browser.new_context(viewport={"width": width, "height": height}, has_touch=width < 641, service_workers="block")
        page = context.new_page()
        css_width = page.evaluate("innerWidth")
        if css_width != width:  # Headless WebKit viewport correction.
            page.set_viewport_size({"width": round(width * width / css_width), "height": round(height * width / css_width)})
        self.assertEqual(page.evaluate("innerWidth"), width)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        response = page.goto(f"http://127.0.0.1:{self.server.server_port}/", wait_until="domcontentloaded")
        self.assertEqual(response.status, 200)
        page.locator(".vault-brand-logo").evaluate("img => img.decode()")
        return context, page, errors

    def test_five_mobile_tabs_safe_area_and_navigation(self):
        for width, height in ((390, 844), (375, 812), (320, 700)):
            with self.subTest(width=width):
                context, page, errors = self.open_page(width, height)
                try:
                    state = page.evaluate("""() => {
                      const nav=document.getElementById('main-tabs');
                      const tabs=[...nav.querySelectorAll('.tab')].filter(el=>getComputedStyle(el).display!=='none');
                      const box=nav.getBoundingClientRect();
                      const logo=document.querySelector('.vault-brand-logo').getBoundingClientRect();
                      return {
                        names:tabs.map(el=>el.textContent.trim().replace(/\\s+/g,' ')),
                        icons:tabs.map(el=>({url:el.querySelector('img')?.getAttribute('src'),
                          bottom:el.querySelector('img').getBoundingClientRect().bottom})),
                        labels:tabs.map(el=>{
                          const text=[...el.childNodes].find(node=>node.nodeType===Node.TEXT_NODE && node.textContent.trim());
                          const range=document.createRange();range.selectNodeContents(text);
                          const r=range.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom};
                        }),
                        rects:tabs.map(el=>{const r=el.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height}}),
                        rows:new Set(tabs.map(el=>Math.round(el.getBoundingClientRect().top))).size,
                        navLeft:box.left,navRight:box.right,
                        scrollWidth:nav.scrollWidth,clientWidth:nav.clientWidth,
                        overflowX:getComputedStyle(nav).overflowX,
                        htmlWidth:document.documentElement.getBoundingClientRect().width,
                        documentWidth:document.documentElement.scrollWidth,
                        logoTop:logo.top,logoBottom:logo.bottom,
                        headerBottom:document.querySelector('header').getBoundingClientRect().bottom,
                        naturalWidth:document.querySelector('.vault-brand-logo').naturalWidth,
                        badgeDisplay:getComputedStyle(document.getElementById('badge-cat')).display
                      };
                    }""")
                    self.assertEqual(len(state["names"]), 5)
                    self.assertTrue(all(name.startswith(label) for name, label in zip(state["names"], LABELS)))
                    self.assertTrue(all(icon["url"].endswith(".png") for icon in state["icons"]))
                    self.assertEqual(state["rows"], 1)
                    self.assertLessEqual(max(r["width"] for r in state["rects"]) - min(r["width"] for r in state["rects"]), 1)
                    self.assertTrue(all(r["height"] >= 44 and r["width"] >= 44 for r in state["rects"]))
                    self.assertTrue(all(r["left"] >= state["navLeft"] - 1 and r["right"] <= state["navRight"] + 1 for r in state["rects"]))
                    self.assertTrue(all(icon["bottom"] <= label["top"] for icon, label in zip(state["icons"], state["labels"])))
                    self.assertTrue(all(label["left"] >= rect["left"] - 1 and label["right"] <= rect["right"] + 1 and label["bottom"] <= rect["bottom"] + 1 for label, rect in zip(state["labels"], state["rects"])))
                    self.assertLessEqual(state["scrollWidth"], state["clientWidth"] + 1)
                    self.assertNotEqual(state["overflowX"], "auto")
                    self.assertLessEqual(state["documentWidth"], math.ceil(state["htmlWidth"]))
                    self.assertEqual(state["badgeDisplay"], "none")
                    self.assertGreater(state["naturalWidth"], 0)
                    self.assertGreaterEqual(state["logoTop"], 8)
                    self.assertLessEqual(state["logoBottom"], state["headerBottom"])
                    self.assertEqual(page.locator("nav.main-tabs-shell").get_attribute("aria-label"), "Secciones principales")

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

                    page.evaluate("document.getElementById('main-tabs').scrollLeft=100")
                    self.assertEqual(page.evaluate("document.getElementById('main-tabs').scrollLeft"), 0)
                    for tab_id, panel in zip(IDS, PANELS):
                        page.locator(f"#tab-{tab_id}").click()
                        self.assertTrue(page.locator(f"#panel-{panel}").is_visible())
                        self.assertEqual(page.locator(f"#tab-{tab_id}").get_attribute("aria-current"), "page")
                    page.locator("#tab-vault").focus()
                    self.assertEqual(page.evaluate("document.activeElement.id"), "tab-vault")
                    self.assertFalse(errors, errors)
                finally:
                    context.close()

    def test_authenticated_shortcuts_are_outside_the_five_tab_row(self):
        context, page, errors = self.open_page(320, 700)
        try:
            page.evaluate("""() => {
              AUTH_USER={uid:'local-test'};
              document.querySelectorAll('.auth-tab').forEach(el=>el.style.display='');
              document.getElementById('mobile-user-shortcuts').style.display='';
            }""")
            self.assertEqual(page.locator("#main-tabs .tab:visible").count(), 5)
            self.assertTrue(page.locator("#mobile-user-shortcuts").is_visible())
            for section in ("pendientes", "mis-hechos"):
                page.locator(f".mobile-user-shortcut[data-section='{section}']").click()
                self.assertTrue(page.locator(f"#panel-{section}").is_visible())
                self.assertEqual(page.locator(f".mobile-user-shortcut[data-section='{section}']").get_attribute("aria-current"), "page")
            self.assertFalse(errors, errors)
        finally:
            context.close()

    def test_desktop_navigation_is_unchanged(self):
        context, page, errors = self.open_page(1440, 900)
        try:
            state = page.evaluate("""() => {
              const nav=document.getElementById('main-tabs');
              const tabs=[...nav.querySelectorAll('.tab')].filter(el=>getComputedStyle(el).display!=='none');
              return {rows:new Set(tabs.map(el=>Math.round(el.getBoundingClientRect().top))).size,
                scrollWidth:nav.scrollWidth,clientWidth:nav.clientWidth,
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
            page.evaluate("document.getElementById('mobile-user-shortcuts').style.display=''")
            self.assertFalse(page.locator("#mobile-user-shortcuts").is_visible())
            self.assertFalse(errors, errors)
        finally:
            context.close()


if __name__ == "__main__":
    unittest.main()
