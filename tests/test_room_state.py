"""Run the actual client state model in Node, including on CI."""
from pathlib import Path
import subprocess
import unittest


class RoomStateRegressionTest(unittest.TestCase):
    def test_client_state_regressions(self):
        result = subprocess.run(
            ["node", "--test", str(Path(__file__).with_name("room_state.test.cjs"))],
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
