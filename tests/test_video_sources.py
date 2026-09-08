import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import collect_official_video_candidates as videos


class EscapistasVideoSourceTest(unittest.TestCase):
    def setUp(self):
        self.parser = videos.parse_page(
            "<title>Escape Room 'La Mina' de Unreal Room Escape - Hospitalet</title>"
        )

    def test_matching_room_and_company_is_accepted(self):
        room = {"nombre": "La Mina", "empresa": "Unreal Room Escape"}
        self.assertTrue(videos.escapistas_page_matches(room, self.parser))

    def test_same_name_from_another_company_is_rejected(self):
        room = {"nombre": "La Mina", "empresa": "Share-Lock"}
        self.assertFalse(videos.escapistas_page_matches(room, self.parser))

    def test_generic_company_video_is_not_high_confidence(self):
        room = {"nombre": "The Narcos", "empresa": "Unreal Room Escape"}
        parser = videos.parse_page(
            "<title>Unreal Room Escape - La Mina - The Narcos - Vikingos</title>"
        )
        item = {
            "url": "https://www.youtube.com/embed/McHENnNXlpc",
            "source_type": "iframe",
            "label": "",
            "attrs": {},
        }
        normalized = videos.canonical_video(item["url"], "https://unrealroomescape.es/")
        score, confidence = videos.score_video(
            item, normalized, room, parser, "https://unrealroomescape.es/"
        )
        self.assertLess(score, 78)
        self.assertNotEqual(confidence, "high")


if __name__ == "__main__":
    unittest.main()
