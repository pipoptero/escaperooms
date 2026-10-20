"""The Village is one Scream Park entity, never an escape-room identity."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TheVillageReleaseTests(unittest.TestCase):
    def test_only_scream_park_identity_remains(self):
        catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
        parks = json.loads((ROOT / "scream-parks/data-2026.json").read_text(encoding="utf-8"))["entries"]
        self.assertEqual(len(parks), 22)
        self.assertEqual(len({park["id"] for park in parks}), 22)
        self.assertEqual(len(catalog["catalogo"]), 1740)
        self.assertEqual(catalog["meta"]["count"], 1740)
        self.assertFalse(any(room.get("id") == "the-village" for room in catalog["catalogo"]))
        village = [park for park in parks if park.get("id") == "the-village"]
        self.assertEqual(len(village), 1)
        self.assertEqual(village[0]["seasonId"], "the-village-2026")
        self.assertEqual(village[0]["type"], "scream_park")
        self.assertEqual(len(village[0]["sessionDates"]), 8)
        self.assertEqual(len(village[0]["images"]), 1)
        self.assertTrue((ROOT / village[0]["images"][0]).exists())
        self.assertEqual(village[0]["officialVideo"]["embedUrl"], "https://www.tiktok.com/player/v1/7693957517554060566")
        self.assertIn("Cerca de Berga", village[0]["practical"]["locationApprox"])
        self.assertNotIn("the-village", (ROOT / "sitemap-rooms.xml").read_text(encoding="utf-8"))

    def test_old_url_is_nonindexable_redirect_to_park(self):
        page = (ROOT / "salas/the-village/index.html").read_text(encoding="utf-8")
        self.assertIn('name="robots" content="noindex, follow"', page)
        self.assertIn('url=/#scream-park/the-village', page)
        self.assertIn('href="/#scream-park/the-village"', page)
        self.assertNotIn('EntertainmentBusiness', page)

    def test_video_is_preserved_without_fake_rating_or_review(self):
        videos = json.loads((ROOT / "official_videos.json").read_text(encoding="utf-8"))["videos"]
        self.assertEqual(videos["the-village"]["embed_url"], "https://www.tiktok.com/player/v1/7693957517554060566")
        self.assertNotIn("the-village", (ROOT / "video-sitemap.xml").read_text(encoding="utf-8"))



if __name__ == "__main__":
    unittest.main()
