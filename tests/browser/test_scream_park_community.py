"""Release B community UI remains functional only with an isolated fake store."""
import os
from pathlib import Path
from tests.browser.test_scream_park_reviews import V6BrowserTests


class CommunityBrowserTests(V6BrowserTests):
    def test_community_follows_cover_and_precedes_gallery(self):
        for width in (1440, 390):
            with self.subTest(width=width):
                context, page, errors = self.page(width)
                try:
                    page.evaluate("""() => {
                      SCREAM_REVIEW_STORE = VaultScreamParkReviews.createStore({
                        getUid: () => null, read: async () => null,
                        call: async () => { throw Error('No backend in visual test'); },
                        onChange: () => TheVaultScreamParksPreview.current?.refreshReviews()
                      });
                      switchTab('scream-parks');
                    }""")
                    page.locator("#panel-scream-parks article.card[data-id=horrorland] button").first.click()
                    page.locator("#sp-community").wait_for()
                    order = page.locator("#panel-scream-parks .detail-grid aside > *").evaluate_all(
                        "nodes => nodes.map(node => node.className || node.id)")
                    self.assertEqual(order[0], "fallback has-cover")
                    self.assertIn("panel", order[1])
                    self.assertEqual(page.locator("#panel-scream-parks .detail-grid aside > :nth-child(2)").get_attribute("id"), "sp-community")
                    self.assertEqual(page.get_by_text("Antes de ir", exact=True).count(), 0)
                    self.assertFalse(page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"))
                    self.assertEqual(errors, [])
                    capture = os.getenv("VAULT_V61_CAPTURE_DIR")
                    if capture:
                        path = Path(capture) / f"{self.browser.browser_type.name}-{width}-park-community.png"
                        path.parent.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(path), full_page=True)
                finally:
                    context.close()

    def test_pending_opinion_never_appears_as_public(self):
        context, page, errors = self.page(390)
        try:
            page.evaluate("""() => {
              const records = window.__v6Records = {};
              AUTH_USER = { uid: 'alice' }; USER_ID = 'alice';
              SCREAM_REVIEW_STORE = VaultScreamParkReviews.createStore({
                getUid: () => AUTH_USER?.uid || null,
                read: async path => records[path] || null,
                call: async (name, payload) => {
                  const path = `screamParkReviews/${payload.seasonId}/submissions/alice`;
                  if (name === 'submitScreamParkReview') records[path] = {
                    ...payload, entityId: 'horrorland', status: 'PENDING',
                    revision: payload.expectedRevision + 1
                  };
                  if (name === 'deleteScreamParkReview') delete records[path];
                },
                onChange: () => TheVaultScreamParksPreview.current?.refreshReviews()
              });
              switchTab('scream-parks');
            }""")
            page.locator("#panel-scream-parks article.card[data-id=horrorland] button").first.click()
            page.get_by_role("button", name="ESCRIBIR MI OPINIÓN").click()
            page.locator(".sp-community-form").wait_for()
            page.locator(".sp-community-form input[type=number]").fill("8.5")
            page.locator(".sp-community-form textarea").fill("Una visita fantástica y bien organizada")
            page.locator(".sp-community-form input[type=checkbox]").check()
            page.get_by_role("button", name="ENVIAR A MODERACIÓN").click()
            page.wait_for_function("!!window.__v6Records['screamParkReviews/horrorland-2026/submissions/alice']")
            data = page.evaluate("window.__v6Records")
            self.assertEqual(data["screamParkReviews/horrorland-2026/submissions/alice"]["status"], "PENDING")
            self.assertEqual(page.locator(".sp-community-opinion").count(), 0)
            self.assertIn("Aún no hay valoraciones aprobadas", page.locator("#sp-community").inner_text())
            self.assertEqual(errors, [])
        finally:
            context.close()
