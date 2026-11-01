"""Release B community UI against an isolated in-browser store, with no real Firebase."""
import os
from pathlib import Path
from tests.browser.test_scream_park_reviews import V6BrowserTests


class CommunityBrowserTests(V6BrowserTests):
    def test_community_is_full_width_and_last(self):
        for width in (1440, 900, 640, 390):
            with self.subTest(width=width):
                context, page, errors = self.page(width, mock=False)
                try:
                    page.evaluate("""() => {
                      SCREAM_REVIEW_STORE = VaultScreamParkReviews.createStore({
                        getUid: () => null, read: async () => null,
                        put: async () => { throw Error('No backend in visual test'); },
                        remove: async () => { throw Error('No backend in visual test'); },
                        onChange: () => TheVaultScreamParksPreview.current?.refreshReviews()
                      });
                      switchTab('scream-parks');
                    }""")
                    page.locator("#panel-scream-parks article.card[data-id=horrorland] button").first.click()
                    page.locator("#sp-community").wait_for()
                    self.assertEqual(page.locator("#sp-detail-content > :last-child").get_attribute("id"), "sp-community")
                    self.assertEqual(page.locator("#sp-detail-content #sp-community").count(), 1)
                    bounds = page.locator("#sp-detail-content").evaluate("el => el.getBoundingClientRect().width")
                    community_width = page.locator("#sp-community").evaluate("el => el.getBoundingClientRect().width")
                    self.assertLess(abs(bounds - community_width), 2)
                    if width <= 900:
                        order = page.locator("#sp-detail-content .detail-grid > div > *").evaluate_all(
                            "nodes => nodes.map(node => node.className.split(' ')[0])")
                        self.assertEqual(order[:5], ["sp-detail-intro", "detail-panel", "detail-panel", "fallback", "sp-detail-rest"])
                        self.assertIn("NUESTRA VISITA EN FOTOS Y VÍDEOS", page.locator("#sp-detail-content .sp-visit-gallery").inner_text())
                    else:
                        self.assertEqual(page.locator("#sp-detail-content .detail-grid > aside > :first-child").get_attribute("class"), "fallback has-cover")
                    self.assertEqual(page.get_by_text("Antes de ir", exact=True).count(), 0)
                    self.assertFalse(page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"))
                    self.assertEqual(errors, [])
                    photos = page.locator("#sp-detail-content .sp-visit-gallery img")
                    self.assertEqual(photos.count(), 9)
                    for photo in photos.all():
                        photo.scroll_into_view_if_needed()
                        page.wait_for_function("el => el.naturalWidth > 0", arg=photo.element_handle())
                    capture = os.getenv("VAULT_V61_CAPTURE_DIR")
                    if capture:
                        path = Path(capture) / f"{self.browser.browser_type.name}-{width}-park-community.png"
                        path.parent.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(path), full_page=True)
                finally:
                    context.close()

    def test_opinion_publishes_directly_and_can_be_edited_or_deleted(self):
        context, page, errors = self.page(390)
        try:
            page.evaluate("""() => {
              const records = window.__v6Records = {};
              AUTH_USER = { uid: 'alice' }; USER_ID = 'alice';
              SCREAM_REVIEW_STORE = VaultScreamParkReviews.createStore({
                getUid: () => AUTH_USER?.uid || null,
                read: async path => records[path] || null,
                put: async (path, value) => {
                  const parent = path.slice(0, path.lastIndexOf('/'));
                  records[parent] ||= {};
                  records[parent][path.slice(path.lastIndexOf('/') + 1)] = value;
                },
                remove: async path => {
                  const parent = path.slice(0, path.lastIndexOf('/'));
                  delete records[parent][path.slice(path.lastIndexOf('/') + 1)];
                },
                onChange: () => TheVaultScreamParksPreview.current?.refreshReviews()
              });
              switchTab('scream-parks');
            }""")
            page.locator("#panel-scream-parks article.card[data-id=horrorland] button").first.click()
            page.get_by_role("button", name="ESCRIBIR MI OPINIÓN").click()
            page.locator(".sp-community-form").wait_for()
            for category in ("ambientacion", "acting", "organizacion", "terror", "variedad"):
                page.locator(f'.sp-community-form .review-stars[data-category="{category}"]').click(position={"x": 70, "y": 10})
            page.locator(".sp-community-form textarea").fill("Una visita fantástica y bien organizada")
            page.get_by_role("button", name="PUBLICAR OPINIÓN").click()
            page.wait_for_function("!!window.__v6Records['screamParkReviews/horrorland-2026']?.alice")
            data = page.evaluate("window.__v6Records")
            self.assertEqual(data["screamParkReviews/horrorland-2026"]["alice"]["revision"], 1)
            self.assertEqual(page.locator(".sp-community-opinion").count(), 1)
            self.assertIn("Nota global", page.locator("#sp-community").inner_text())
            page.get_by_role("button", name="EDITAR MI OPINIÓN").click()
            page.locator(".sp-community-form textarea").fill("Segunda versión de nuestra visita")
            page.get_by_role("button", name="ACTUALIZAR OPINIÓN").click()
            page.wait_for_function("window.__v6Records['screamParkReviews/horrorland-2026'].alice.revision === 2")
            page.on("dialog", lambda dialog: dialog.accept())
            page.get_by_role("button", name="ELIMINAR MI OPINIÓN").click()
            page.wait_for_function("!window.__v6Records['screamParkReviews/horrorland-2026'].alice")
            self.assertEqual(page.locator(".sp-community-opinion").count(), 0)
            self.assertEqual(errors, [])
        finally:
            context.close()
