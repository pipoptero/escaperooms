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
        self.assertEqual(sum(p["status"] == "VISIBLE" for p in self.positions), 26)
        self.assertEqual(sum(p["status"] == "NO EXISTE EN CATÁLOGO" for p in self.positions), 4)
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
                    self.assertEqual(position["identity_evidence_url"], self.catalog[room_id]["web"])
                else:
                    self.assertFalse(matches)
                    self.assertTrue(position["reason"])

    def test_no_duplicate_award_or_wrong_room(self):
        top = [a for a in self.awards if a.get("source_id") == "10escapes" and a.get("year") == 2026
               and a.get("category") in ("Top Room", "Top Horror", "Top Wild")
               and isinstance(a.get("rank"), int) and 1 <= a["rank"] <= 10]
        self.assertEqual(len(top), 26)
        self.assertEqual(len({(a["category"], a["rank"]) for a in top}), 26)
        self.assertEqual([sum(a["category"] == "Top " + category for a in top)
                          for category in ("Room", "Horror", "Wild")], [9, 9, 8])


if __name__ == "__main__":
    unittest.main()
