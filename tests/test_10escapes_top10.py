"""Exact official TOP 10 positions, canonical identities, and exclusions."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TenEscapesTopTenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.positions = json.loads((ROOT / "tests/fixtures/tenescapes_top10_2026.json").read_text(encoding="utf-8"))["positions"]
        cls.catalog = {r["id"]: r for r in json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))["catalogo"]}
        cls.awards = json.loads((ROOT / "extra_awards.json").read_text(encoding="utf-8"))["awards"]

    def test_all_thirty_positions_have_one_decision(self):
        self.assertEqual(len(self.positions), 30)
        self.assertEqual({(p["category"], p["rank"]) for p in self.positions},
                         {(category, rank) for category in ("ROOM", "HORROR", "WILD") for rank in range(1, 11)})
        self.assertEqual(sum(p["status"] == "VISIBLE" for p in self.positions), 30)
        self.assertEqual(sum(p["status"] == "NO EXISTE EN CATÁLOGO" for p in self.positions), 0)
        for position in self.positions:
            with self.subTest(category=position["category"], rank=position["rank"]):
                matches = [a for a in self.awards if a.get("source_id") == "10escapes" and a.get("year") == 2026
                           and a.get("category") == "Top " + position["category"].title()
                           and a.get("rank") == position["rank"]]
                if position["canonical_room_id"]:
                    room_id = position["canonical_room_id"]
                    self.assertIn(room_id, self.catalog)
                    self.assertEqual(len(matches), 1)
                    self.assertEqual(matches[0]["canonical_room_id"], room_id)
                    self.assertEqual(matches[0]["room"], self.catalog[room_id]["nombre"])
                    self.assertEqual(matches[0]["source_url"], "https://10escapes.com/ganadores26/")
                    self.assertTrue(position["identity_evidence_url"].startswith("https://"))
                else:
                    self.assertFalse(matches)
                    self.assertTrue(position["reason"])

    def test_no_duplicate_award_or_wrong_room(self):
        top = [a for a in self.awards if a.get("source_id") == "10escapes" and a.get("year") == 2026
               and a.get("category") in ("Top Room", "Top Horror", "Top Wild")
               and isinstance(a.get("rank"), int) and 1 <= a["rank"] <= 10]
        self.assertEqual(len(top), 30)
        self.assertEqual(len({(a["category"], a["rank"]) for a in top}), 30)
        self.assertEqual([sum(a["category"] == "Top " + category for a in top)
                          for category in ("Room", "Horror", "Wild")], [10, 10, 10])

    def test_gastro_escape_keeps_identity_with_owner_material(self):
        room = self.catalog["gastro-escape-experiencity"]
        self.assertEqual(sum(r["nombre"].casefold() == "gastro escape" and
                             r["empresa"].casefold() == "experiencity"
                             for r in self.catalog.values()), 1)
        self.assertEqual(room["nombre"], "Gastro Escape")
        self.assertEqual(room["empresa"], "Experiencity")
        self.assertEqual(room["ciudad"], "Madrid")
        self.assertEqual(room["web"], "https://gastroescaperoom.com/")
        self.assertGreater(len(room["descripcion"]), 100)
        self.assertEqual(room["imagen"], "images/catalgo_propio_web_escape/optimized/gastro-escape-experiencity.webp")
        self.assertIsNone(room["duracion"])
        self.assertIsNone(room["min_personas"])
        self.assertIsNone(room["max_personas"])


if __name__ == "__main__":
    unittest.main()
