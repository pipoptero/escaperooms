"""Scope guards for the November 2026 editorial catalog release."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEW_IDS = {
    "umbra", "la-leyenda-del-tiempo", "ecos-de-los-antiguos", "oh-fortuna",
    "la-ultima-habitante", "la-feria-express-games", "cain-vitoria-gasteiz",
    "el-ultimo-sonador", "salvar-a-las-abejas",
    "la-maldicion-mas-de-las-matas", "mario-vs-luigi-sevilla",
    "guarida-del-doctor-raimon", "el-castillo-de-dracula-salamanca",
}
EDITORIAL_IDS = {
    "academia-de-detectives", "adrenalina", "csi-investigacion-en-equipo",
    "ecos-de-los-antiguos", "gastro-escape-experiencity", "haunt",
    "la-leyenda-del-tiempo", "oh-fortuna",
    "experiencia-roble-los-siete-enanitos", "the-monster", "umbra",
}


class CatalogMaterialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))["catalogo"]
        cls.rooms = {room["id"]: room for room in cls.catalog}

    def test_new_ids_and_existing_media_scope(self):
        self.assertEqual(len(self.catalog), 1759)
        self.assertEqual(len(self.rooms), 1759)
        self.assertTrue(NEW_IDS <= self.rooms.keys())
        self.assertTrue(EDITORIAL_IDS <= self.rooms.keys())
        for room_id in EDITORIAL_IDS:
            room = self.rooms[room_id]
            self.assertGreater(len(room["descripcion"]), 1000)
            self.assertEqual(room.get("descripcion_formato"), "markdown")
            self.assertTrue(room["imagen"].startswith("images/catalgo_propio_web_escape/optimized/"))
            self.assertTrue((ROOT / room["imagen"]).is_file())
            self.assertFalse({"source_checkpoint", "raw_response", "external_source_id"} & room.keys())

    def test_park_references_are_exact(self):
        parks = {park["id"]: park for park in json.loads(
            (ROOT / "scream-parks/data-2026.json").read_text(encoding="utf-8"))["entries"]}
        for room_id, park_id in {
            "umbra": "the-village", "oh-fortuna": "terrorland",
            "ecos-de-los-antiguos": "terrorland",
        }.items():
            room = self.rooms[room_id]
            self.assertEqual(room["scream_park_id"], park_id)
            self.assertEqual(room["scream_park_season_id"], parks[park_id]["seasonId"])
        self.assertNotIn("the-village", self.rooms)

    def test_haunt_three_official_embeds(self):
        videos = json.loads((ROOT / "official_videos.json").read_text(encoding="utf-8"))["videos"]["haunt"]["videos"]
        self.assertEqual(
            [video["embed_url"].split("?")[0] for video in videos],
            [f"https://videopress.com/embed/{key}" for key in ("mKQdybBt", "4vmJX0GT", "wjk1Ii7F")],
        )
        self.assertEqual({video["source_page_url"] for video in videos}, {"https://hauntescaperoom.com/"})

    def test_other_product_counts(self):
        self.assertEqual(len(json.loads((ROOT / "published_reviews.json").read_text(encoding="utf-8"))["reviews"]), 43)
        self.assertEqual(len(json.loads((ROOT / "scream-parks/data-2026.json").read_text(encoding="utf-8"))["entries"]), 22)


if __name__ == "__main__":
    unittest.main()
