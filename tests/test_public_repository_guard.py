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
                     "source-checkpoint.json", "users.sqlite", ".env.production", "service-account.pem"):
            self.assertTrue(is_private_path(path), path)
        for path in ("catalog.json", "scream-parks/data-2026.json", "images/cover.webp",
                     "extra_awards.json", "image_sources.example.csv"):
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
                self.assertTrue(any("research.xlsx" in item for item in check(staged=True)))
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
