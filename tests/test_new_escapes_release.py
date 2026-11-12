"""Release guard for the five verified backlog additions and 2026 awards."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEW_IDS = {
    "csi-investigacion-en-equipo", "the-monster",
    "experiencia-roble-los-siete-enanitos", "adrenalina",
    "academia-de-detectives",
}


class NewEscapesReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))["catalogo"]
        cls.awards = json.loads((ROOT / "extra_awards.json").read_text(encoding="utf-8"))["awards"]

    def test_minimal_rooms_and_unique_identity(self):
        self.assertEqual(len(self.catalog), 1745)
        self.assertEqual(len({room["id"] for room in self.catalog}), len(self.catalog))
        rooms = {room["id"]: room for room in self.catalog}
        self.assertEqual(NEW_IDS, NEW_IDS & rooms.keys())
        for identity in NEW_IDS:
            room = rooms[identity]
            self.assertEqual(room["descripcion"], "Sin sinopsis")
            self.assertEqual(room["imagen"], "")
            self.assertTrue(room["web"].startswith("https://"))
            self.assertNotIn("escapecollector.com", room["web"])

    def test_2026_awards_have_exact_catalog_identity(self):
        rooms = {room["id"]: room for room in self.catalog}
        awards = [award for award in self.awards if award.get("source_id") == "10escapes"
                  and award.get("year") == 2026]
        self.assertEqual(len(awards), 240)
        self.assertEqual(len({(a["canonical_room_id"], a["category"], a["rank"])
                              for a in awards}), len(awards))
        for award in awards:
            room = rooms[award["canonical_room_id"]]
            self.assertEqual(award["room"], room["nombre"])
            self.assertEqual(award["company"], room["empresa"])
            self.assertEqual(award["source_url"], "https://10escapes.com/ganadores26/")


if __name__ == "__main__":
    unittest.main()
