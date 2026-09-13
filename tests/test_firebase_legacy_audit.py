import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_firebase_legacy.py"
BRANCHES = ("users", "groupRooms", "groupPendingRooms", "groups", "groupMembers", "userGroups")


class FirebaseLegacyAuditTest(unittest.TestCase):
    def test_group_and_editorial_inconsistencies_are_reported_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            snapshots = base / "snapshots"
            output = base / "output"
            snapshots.mkdir()
            values = {name: {} for name in BRANCHES}
            values["groups"] = {"group_without_owner": {"name": "Broken test group"}}
            for name, value in values.items():
                (snapshots / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--snapshot-dir", str(snapshots), "--output-dir", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            plan = json.loads((output / "firebase-legacy-plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["summary"]["groupMembershipInconsistencies"], 1)
            self.assertEqual(plan["summary"]["editorialAliasInconsistencies"], 0)
            self.assertNotIn("membershipOrReferenceInconsistencies", plan["summary"])
            self.assertEqual(len(plan["groupMembershipInconsistencies"]), 1)
            self.assertEqual(plan["editorialAliasInconsistencies"], [])


if __name__ == "__main__":
    unittest.main()
