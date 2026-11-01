import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_seo_pages import scream_park_review_page, static_home_fallback  # noqa: E402


class ScreamParkReviewSeoTests(unittest.TestCase):
    def test_published_review_has_seasonal_canonical_and_safe_body(self):
        entry = {"id": "horrorland", "seasonId": "horrorland-2026",
                 "name": "Horrorland", "images": ["images/scream-parks/horrorland.webp"]}
        review = {"id": "horrorland-2026-the-vault", "entityId": "horrorland",
                  "seasonId": "horrorland-2026", "title": "Horrorland 2026",
                  "body": "# Nuestra opinión\n\n**Genial** <script>alert(1)</script>",
                  "status": "PUBLISHED", "publishedAt": "2026-10-25T15:00:00Z"}
        html = scream_park_review_page(review, entry)
        self.assertIn('href="https://thevaultescape.com/scream-parks/reviews/horrorland-2026/"', html)
        self.assertIn('Review The Vault · edición 2026', html)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertNotIn('ratingValue', html)
        self.assertIn('"@type": "Article"', html)
        self.assertNotIn('the-village', html)
        self.assertNotIn('property="og:image:width"', html)
        self.assertNotIn('property="og:image:height"', html)

    def test_candidate_is_complete_and_isolated(self):
        registry = json.loads((ROOT / "scream-parks/editorial-reviews.json").read_text(encoding="utf-8"))
        self.assertEqual(len(registry["reviews"]), 1)
        review = registry["reviews"][0]
        self.assertEqual(review["seasonId"], "horrorland-2026")
        self.assertEqual(review["publishedAt"], "2026-10-26")
        self.assertEqual(hashlib.sha256(review["body"].encode()).hexdigest(), review["sourceSha256"])
        self.assertEqual(len(review["images"]), 9)
        for photo in review["images"]:
            for key in ("src", "thumbnail"):
                path = ROOT / photo[key]
                self.assertTrue(path.is_file(), photo[key])
                data = path.read_bytes()
                self.assertEqual(data[:4], b"RIFF")
                self.assertEqual(data[8:12], b"WEBP")
                self.assertNotIn(b"EXIF", data)
        self.assertEqual(len(review["videos"]), 2)
        for video in review["videos"]:
            self.assertEqual((ROOT / video["src"]).read_bytes()[4:8], b"ftyp")
            poster = (ROOT / video["poster"]).read_bytes()
            self.assertEqual(poster[:4], b"RIFF")
            self.assertEqual(poster[8:12], b"WEBP")
            self.assertNotIn(b"EXIF", poster)
        page = (ROOT / "scream-parks/reviews/horrorland-2026/index.html").read_text(encoding="utf-8")
        self.assertIn('https://thevaultescape.com/scream-parks/reviews/horrorland-2026/', page)
        self.assertIn('"datePublished": "2026-10-26"', page)
        self.assertIn('Pray For Us', page)
        self.assertIn('Nuestra visita en fotos y vídeos', page)
        self.assertEqual(page.count('aria-label="Ampliar foto '), 9)
        self.assertEqual(page.count('<video class="sp-visit-video" controls playsinline preload="none"'), 2)
        self.assertEqual(page.count('class="sp-visit-play" type="button" data-video-src='), 2)
        self.assertIn('<script src="/scream-parks/visit-video.js" defer></script>', page)
        self.assertEqual(page.count('"@type": "VideoObject"'), 0)  # No verified video upload date.
        self.assertIn('<meta property="og:image:width" content="900">', page)
        self.assertIn('<meta property="og:image:height" content="1350">', page)
        self.assertNotIn('<meta property="og:image:width" content="1200">', page)
        self.assertIn('https://thevaultescape.com/scream-parks/reviews/horrorland-2026/',
                      (ROOT / "sitemap-reviews.xml").read_text(encoding="utf-8"))
        shell = (ROOT / "service-worker.js").read_text(encoding="utf-8")
        self.assertIn("the-vault-v62", shell)
        self.assertIn("./scream-parks/visit-video.js", shell)
        self.assertIn("./scream-parks/reviews/horrorland-2026/", shell)
        app = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("scream-parks/reviews.js", app)
        self.assertIn("const communityEnabled = FIREBASE_CONFIG.screamReviewsEnabled === true", app)
        self.assertNotIn("FIREBASE_CONFIG.appCheckSiteKey", app)
        self.assertIn("const communityPreview = localPreview || communityEnabled", app)

    def test_static_home_includes_latest_scream_review_without_changing_escape_count(self):
        stats = {"catalog": 1740, "reviews": 43, "ranking": 948, "locations": 44}
        html = static_home_fallback(stats, [])
        self.assertIn('scream-parks/reviews/horrorland-2026/', html)
        self.assertIn('Review The Vault · Scream Park', html)
        self.assertIn('id="vault-stat-reviews">43</strong>', html)
        self.assertNotIn('THE VAULT SCORE', html)

    def test_draft_and_wrong_identity_cannot_generate_public_page(self):
        entry = {"id": "horrorland", "seasonId": "horrorland-2026", "name": "Horrorland"}
        review = {"entityId": "horrorland", "seasonId": "horrorland-2026",
                  "title": "Horrorland", "body": "Texto largo", "status": "DRAFT"}
        with self.assertRaises(ValueError):
            scream_park_review_page(review, entry)
        review["status"] = "PUBLISHED"
        review["entityId"] = "the-village"
        with self.assertRaises(ValueError):
            scream_park_review_page(review, entry)


if __name__ == "__main__":
    unittest.main()
