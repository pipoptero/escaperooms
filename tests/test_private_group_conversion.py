"""The public converter cannot accidentally consume a workbook from Git."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "convert.py"


class PrivateGroupConversionTests(unittest.TestCase):
    def test_explicit_input_and_output_are_required(self):
        result = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT,
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--input", result.stderr)
        self.assertIn("--output", result.stderr)

    def test_missing_private_workbook_fails_without_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "data.json"
            result = subprocess.run([sys.executable, str(SCRIPT), "--input",
                                     str(Path(folder) / "missing.xlsx"), "--output", str(output)],
                                    cwd=ROOT, text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
