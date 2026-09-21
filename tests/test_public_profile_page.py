import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicProfilePageTests(unittest.TestCase):
    def test_public_shell_is_noindex_and_has_neutral_unavailable_copy(self):
        html = (ROOT / "escapista" / "index.html").read_text(encoding="utf-8")
        self.assertIn('content="noindex,nofollow,noarchive,nosnippet"', html)
        self.assertIn("Este perfil no está disponible.", html)
        self.assertNotIn("publicProfileOwners", html)
        self.assertNotIn("publicProfileControls", html)

    def test_public_page_only_reads_the_sanitized_view(self):
        script = (ROOT / "escapista" / "public-profile-page.js").read_text(encoding="utf-8")
        self.assertIn("/publicProfiles/", script)
        self.assertIn("/view.json", script)
        for private_path in (
            "profiles/", "users/", "groupRooms/", "groupPendingRooms/",
            "userGroups/", "groupMembers/", "groupInvites/", "userRoutes/", "groupRoutes/",
        ):
            self.assertNotIn(private_path, script)

    def test_fixture_partial_omits_hidden_sections_in_source_data(self):
        fixture = (ROOT / "public-profile-fixtures.js").read_text(encoding="utf-8")
        laura_start = fixture.index("const laura")
        private_start = fixture.index("const fixtures")
        laura_source = fixture[laura_start:private_start]
        self.assertIn("showStats: false", laura_source)
        self.assertIn("showMap: false", laura_source)
        self.assertIn("showRoutes: false", laura_source)
        self.assertNotIn("stats:", laura_source)
        self.assertNotIn("mapRoomIds:", laura_source)
        self.assertNotIn("routes:", laura_source)

    def test_deployment_and_pwa_include_the_public_profile_assets(self):
        workflow = (ROOT / ".github" / "workflows" / "deploy-pages.yml").read_text(encoding="utf-8")
        service_worker = (ROOT / "service-worker.js").read_text(encoding="utf-8")
        self.assertIn("public-profile.js", workflow)
        self.assertIn("public-profile-fixtures.js", workflow)
        self.assertIn(" escapista ", workflow)
        self.assertIn("the-vault-v51", service_worker)
        for asset in ("public-profile.js", "public-profile-firebase.js", "public-profile-fixtures.js", "escapista/public-profile-page.js"):
            self.assertIn(asset.split("/")[-1], service_worker)

    def test_firebase_rules_file_is_valid_json(self):
        rules = json.loads((ROOT / "database.rules.json").read_text(encoding="utf-8"))
        root = rules["rules"]
        self.assertIn("publicProfileControls", root)
        self.assertIn("publicProfileOwners", root)
        self.assertIn("publicProfiles", root)
        self.assertNotIn(".read", root["publicProfiles"])


if __name__ == "__main__":
    unittest.main()
