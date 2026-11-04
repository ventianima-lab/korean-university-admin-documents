import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("check_quote_candidate.py")


class CandidateGateTest(unittest.TestCase):
    def run_gate(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

    def test_higher_passes_lower_and_equal_fail(self):
        for candidate, expected in (("999", 1), ("1000", 1), ("1001", 0)):
            with self.subTest(candidate=candidate):
                result = self.run_gate("--main-total", "1000", "--candidate-total", candidate)
                self.assertEqual(result.returncode, expected)
                self.assertIn("PRICE_GATE_PASSED" if expected == 0 else "INELIGIBLE", result.stdout)

    def test_missing_unconfirmed_or_invalid_totals_fail_closed(self):
        for args in (("--main-total", "1000"), ("--main-total", "0", "--candidate-total", "1001"),
                     ("--main-total", "1000", "--candidate-total", "unknown"),
                     ("--main-total", "1000", "--candidate-total", "1001.5"),
                     ("--main-total", "-1", "--candidate-total", "1001")):
            with self.subTest(args=args):
                self.assertNotEqual(self.run_gate(*args).returncode, 0)

    def test_unknown_override_flags_are_rejected(self):
        result = self.run_gate("--main-total", "1000", "--candidate-total", "999", "--allow-lower-price")
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
