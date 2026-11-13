"""Private artifacts must never enter the public tree or the staging index."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_public_repository import is_private_path, check  # noqa: E402


class PublicRepositoryGuardTests(unittest.TestCase):
    def test_private_path_classes(self):
        for path in ("research.xlsx", "private/ledger.json", "foo/raw-response-1.json",
                     "scripts/import_private_rooms_to_catalog.py", "backup/example.json",
                     "source-checkpoint.json", "users.sqlite", ".env.production", "service-account.pem",
                     "AGENTS.md", "docs/standards/BRAND_AND_DESIGN.md", "workspace-governance/inventory.md",
                     "gestion-jobs/job.json", "logs/session.log", "snapshots/state.json", "research.csv",
                     "scripts/collect_private_source.py", "scripts/scrape_private_source.py"):
            self.assertTrue(is_private_path(path), path)
        for path in ("catalog.json", "scream-parks/data-2026.json", "images/cover.webp",
                     "extra_awards.json", "image_sources.example.csv", "external_ratings.json",
                     "README.md", "docs/FIREBASE_SECURITY.md", "images/progress/achievements/badges/collector.webp"):
            self.assertFalse(is_private_path(path), path)

    def test_staged_secret_and_worktree_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            (repo / "safe.txt").write_text("safe", encoding="utf-8")
            subprocess.run(["git", "add", "safe.txt"], cwd=repo, check=True)
            previous = Path.cwd()
            try:
                import os
                os.chdir(repo)
                self.assertEqual(check(staged=True), [])
                (repo / "research.xlsx").write_bytes(b"private")
                subprocess.run(["git", "add", "-f", "research.xlsx"], cwd=repo, check=True)
                self.assertTrue(any("Archivo privado" in item and "research.xlsx" not in item
                                    for item in check(staged=True)))
            finally:
                os.chdir(previous)

    def test_content_checks_staged_and_tracked_without_exposing_values(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            public = repo / "external_ratings.json"
            public.write_text('{"source": "public award attribution"}', encoding="utf-8")
            subprocess.run(["git", "add", public.name], cwd=repo, check=True)
            previous = Path.cwd()
            try:
                import os
                os.chdir(repo)
                self.assertEqual(check(staged=True), [])
                self.assertEqual(check(staged=False), [])
                private_key = '"source_' + 'checkpoint":'
                public.write_text("{" + private_key + '"sample"}', encoding="utf-8")
                subprocess.run(["git", "add", public.name], cwd=repo, check=True)
                self.assertTrue(any("Posible secreto" in item for item in check(staged=True)))
                self.assertTrue(any("Posible secreto" in item for item in check(staged=False)))
                public.write_text('{"source": "public award attribution"}', encoding="utf-8")
                subprocess.run(["git", "add", public.name], cwd=repo, check=True)
                self.assertEqual(check(staged=True), [])
                self.assertEqual(check(staged=False), [])
                doc = repo / "README.md"
                doc.write_text("local " + "C:" + "/Users/Example/project", encoding="utf-8")
                subprocess.run(["git", "add", doc.name], cwd=repo, check=True)
                self.assertTrue(any("Posible secreto" in item for item in check(staged=True)))
                self.assertTrue(any("Posible secreto" in item for item in check(staged=False)))
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
