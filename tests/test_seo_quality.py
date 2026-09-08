import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_seo_pages.py"
SPEC = importlib.util.spec_from_file_location("build_seo_pages", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SeoQualityTest(unittest.TestCase):
    def test_thin_room_is_not_indexable(self):
        item = {"room": {"id": "thin", "nombre": "Thin", "descripcion": "Sin sinopsis"}, "rating": {}}
        self.assertFalse(MODULE.room_is_indexable(item))

    def test_descriptive_room_is_indexable(self):
        item = {
            "room": {
                "id": "complete",
                "nombre": "Completa",
                "descripcion": "Una experiencia narrativa con información propia y suficiente para explicar la misión, el contexto y el tipo de juego al visitante antes de reservar." * 2,
            },
            "rating": {},
        }
        self.assertTrue(MODULE.room_is_indexable(item))

    def test_metadata_only_room_is_not_indexable(self):
        item = {
            "room": {
                "id": "metadata",
                "nombre": "Solo datos",
                "empresa": "Empresa",
                "ciudad": "Barcelona",
                "provincia": "Barcelona",
                "web": "https://example.com",
                "duracion": 60,
                "imagen": "images/example.webp",
                "descripcion": "Sin sinopsis",
            },
            "rating": {"global_score": 9},
        }
        self.assertFalse(MODULE.room_is_indexable(item))

    def test_sitemap_index_lists_children(self):
        xml = MODULE.sitemap_index_xml(["sitemap-core.xml", "sitemap-rooms.xml"])
        self.assertIn("<sitemapindex", xml)
        self.assertIn("https://thevaultescape.com/sitemap-rooms.xml", xml)


if __name__ == "__main__":
    unittest.main()
