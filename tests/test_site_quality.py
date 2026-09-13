import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_site_data.py"
SPEC = importlib.util.spec_from_file_location("validate_site_data", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SiteQualityHelpersTest(unittest.TestCase):
    def test_slug_normalizes_accents_and_symbols(self):
        self.assertEqual(MODULE.slug("Nunca Jamás - Key Play"), "nunca_jamas_key_play")

    def test_alias_cycle_detection(self):
        self.assertTrue(MODULE.detect_alias_cycles({"a": "b", "b": "a"}))
        self.assertFalse(MODULE.detect_alias_cycles({"a": "b", "b": "b"}))

    def test_local_assets_are_resolved_from_site_root(self):
        self.assertTrue(MODULE.local_asset_exists("catalog.json"))
        self.assertFalse(MODULE.local_asset_exists("images/no-existe.png"))

    def test_canonical_metadata_mismatches_show_both_values_and_ignore_historical_aliases(self):
        catalog = [{"id": "room", "nombre": "Current name", "empresa": "Current company"}]
        metadata = {
            "room": {
                "canonical_name": "Old name",
                "canonical_company": "Current company",
                "aliases": ["Old name", "Historical company"],
            }
        }
        self.assertEqual(MODULE.canonical_metadata_mismatches(catalog, metadata), [{
            "key": "room",
            "catalog_id": "room",
            "field": "canonical_name",
            "canonical": "Old name",
            "catalog": "Current name",
        }])

    def test_current_alias_metadata_matches_catalog(self):
        report = MODULE.validate()
        self.assertEqual(report["summary"]["editorial_alias_inconsistencies"], 0)

    def test_editorial_cross_source_mismatch_shows_catalog_and_review_values(self):
        catalog = [{
            "id": "room", "nombre": "Sala", "empresa": "Empresa actual", "ciudad": "Madrid", "duracion": 90,
        }]
        reviews = {"room": {"roomKey": "room", "review": {
            "nombre": "Sala", "empresa": "Empresa histórica", "ciudad": "Madrid", "duracion": 60,
        }}}
        result = MODULE.editorial_cross_source_mismatches(catalog, reviews, {})
        self.assertEqual({item["field"] for item in result}, {"company", "duration"})
        self.assertEqual(result[0]["catalog_id"], "room")
        self.assertIn("catalog", result[0])
        self.assertIn("review", result[0])

    def test_editorial_cross_source_ignores_missing_structured_fields(self):
        catalog = [{"id": "room", "nombre": "Sala", "empresa": "Empresa", "duracion": 90}]
        reviews = {"room": {"roomKey": "room", "review": {"nombre": "Sala", "descripcion": "Dice 60 minutos"}}}
        self.assertEqual(MODULE.editorial_cross_source_mismatches(catalog, reviews, {}), [])


if __name__ == "__main__":
    unittest.main()
