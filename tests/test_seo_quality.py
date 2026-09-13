import importlib.util
import json
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

    def test_site_stats_count_catalog_source_without_manual_number(self):
        payload = json.loads(MODULE.site_stats_json([], [], []))
        source = json.loads((MODULE.ROOT / "catalog.json").read_text(encoding="utf-8"))["catalogo"]
        self.assertEqual(payload["catalog"], len(source))

    def test_static_home_is_useful_without_dynamic_javascript(self):
        stats = {"catalog": 12, "reviews": 3, "ranking": 8, "locations": 4}
        html = MODULE.static_home_fallback(stats, [{
            "id": "room", "nombre": "Sala", "empresa": "Empresa", "ciudad": "Madrid", "_updatedAt": 10,
        }])
        self.assertIn("Encuentra tu próximo escape", html)
        self.assertIn('id="vault-stat-catalog">12', html)
        self.assertIn("Mi perfil escapista", html)
        self.assertIn("Sala", html)

    def test_reviews_index_supports_filters_incomplete_metadata_and_missing_image(self):
        html = MODULE.reviews_index_page([{
            "id": "minimal", "nombre": "Review mínima", "empresa": "", "ciudad": "", "descripcion": "",
        }])
        self.assertIn('data-review-card', html)
        self.assertIn('review-card-fallback', html)
        self.assertIn('id="review-search"', html)
        self.assertIn('id="review-empty"', html)
        self.assertIn('property="og:image" content="https://thevaultescape.com/images/brand/social-card.png"', html)

    def test_room_page_separates_global_and_the_vault_scores(self):
        item = {
            "room": {"id": "dual", "nombre": "Sala dual", "empresa": "Empresa", "valoracion": 8.7},
            "rating": {"global_score": 9.1, "source_count": 2},
            "meta": {},
        }
        html = MODULE.room_page(item, 1)
        self.assertIn("Índice / nota global", html)
        self.assertIn("The Vault Score", html)
        self.assertIn("¿Cómo se calcula?", html)


if __name__ == "__main__":
    unittest.main()
