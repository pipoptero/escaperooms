"""Managed update-data mode and unchanged legacy writer path."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from managed_release_guard import is_managed_release, verify_validation_only  # noqa: E402


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                          text=True, encoding="utf-8").stdout.strip()


class ManagedReleaseGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Vault Test")
        git(self.repo, "config", "user.email", "vault-test@example.invalid")
        (self.repo / "payload.txt").write_text("first\n", encoding="utf-8")
        git(self.repo, "add", "payload.txt")

    def tearDown(self):
        self.temp.cleanup()

    def commit(self, subject: str, trailer: str | None = None) -> str:
        args = ["commit", "-q", "-m", subject]
        if trailer is not None:
            args.extend(("-m", trailer))
        git(self.repo, *args)
        return git(self.repo, "rev-parse", "HEAD")

    def test_exact_managed_trailer_and_clean_validation(self):
        head = self.commit("Update ranking scores and awards",
                           "Vault-Managed-Release: true\nVault-Manifest-SHA256: abc123")
        self.assertTrue(is_managed_release(self.repo))
        verify_validation_only(head, self.repo)
        (self.repo / "payload.txt").write_text("dirty\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "dirty"):
            verify_validation_only(head, self.repo)

    def test_legacy_and_malformed_trailers_do_not_activate_managed_mode(self):
        self.commit("Legacy Excel update")
        self.assertFalse(is_managed_release(self.repo))
        for message in ("Vault-Managed-Release: TRUE",
                        "Vault-Managed-Release: false",
                        "Vault-Managed-Release true",
                        "Vault-Managed-Release: true\nVault-Managed-Release: false"):
            (self.repo / "payload.txt").write_text(message + "\n", encoding="utf-8")
            git(self.repo, "add", "payload.txt")
            self.commit("Malformed trailer", message)
            self.assertFalse(is_managed_release(self.repo), message)

    def test_child_commit_is_rejected(self):
        head = self.commit("Managed", "Vault-Managed-Release: true")
        (self.repo / "payload.txt").write_text("second\n", encoding="utf-8")
        git(self.repo, "add", "payload.txt")
        self.commit("Unexpected child")
        with self.assertRaisesRegex(ValueError, "HEAD differs"):
            verify_validation_only(head, self.repo)

    def test_workflow_separates_read_only_managed_and_legacy_writers(self):
        workflow = (REPO / ".github" / "workflows" / "update-data.yml").read_text(encoding="utf-8")
        managed = workflow.split("  validate_managed:\n", 1)[1].split("  convert-and-deploy:\n", 1)[0]
        legacy = workflow.split("  convert-and-deploy:\n", 1)[1]
        self.assertIn("if: needs.detect_release.outputs.managed == 'true'", managed)
        self.assertIn("contents: read", managed)
        self.assertIn("persist-credentials: false", managed)
        for writer in ("python convert.py", "python scripts/optimize_generated_covers.py",
                       "python scripts/build_review_photos.py", "python scripts/build_seo_pages.py",
                       "git add", "git commit", "git push"):
            self.assertNotIn(writer, managed)
            self.assertIn(writer, legacy)
        self.assertIn("if: needs.detect_release.outputs.managed != 'true'", legacy)
        self.assertIn("contents: write", legacy)


if __name__ == "__main__":
    unittest.main()
