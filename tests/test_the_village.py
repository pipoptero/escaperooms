"""Release invariants for the single The Village catalog identity."""

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAYER = "https://www.tiktok.com/player/v1/7693957517554060566"
COVER = "images/catalgo_propio_web_escape/optimized/the-village.webp"
COVER_SHA256 = "bdd0dda1d5f79611e7321a2ebe23a3092122dc472969b16b2940dea3c1b47aae"


class TheVillageReleaseTests(unittest.TestCase):
    def test_room_is_one_location_honest_identity_with_approved_cover(self):
        catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))["catalogo"]
        rooms = [room for room in catalog if room["id"] == "the-village"]
        self.assertEqual(len(rooms), 1)
        room = rooms[0]
        self.assertEqual(room["ciudad"], "")
        self.assertEqual(room["provincia"], "Barcelona")
        self.assertEqual(room["empresa"], "Insomnia Corporation")
        self.assertIsNone(room["duracion"])
        self.assertIsNone(room["min_personas"])
        self.assertIsNone(room["max_personas"])
        self.assertEqual(room["imagen"], COVER)
        self.assertEqual(hashlib.sha256((ROOT / COVER).read_bytes()).hexdigest(), COVER_SHA256)

    def test_tiktok_embed_has_no_invented_sitemap_metadata(self):
        videos = json.loads((ROOT / "official_videos.json").read_text(encoding="utf-8"))["videos"]
        video = videos["the-village"]
        self.assertEqual(video["provider"], "tiktok")
        self.assertEqual(video["embed_url"], PLAYER)
        self.assertEqual(video["aspect_ratio"], "9/16")
        self.assertFalse(video["upload_date"])
        self.assertFalse(video["thumbnail"])
        self.assertIn("the-village", (ROOT / "sitemap-rooms.xml").read_text(encoding="utf-8"))
        self.assertNotIn("the-village", (ROOT / "video-sitemap.xml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
