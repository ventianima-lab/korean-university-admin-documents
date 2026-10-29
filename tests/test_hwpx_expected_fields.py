"""Exercise saved HWPX paragraph and cell checks using synthetic data only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get(
    "HWPX_FIELD_VALIDATOR",
    ROOT / "skills/hancom-hwpx-documents/scripts/validate_hwpx_opensource.py",
))
SECTION = "Contents/section0.xml"


class ExpectedFieldTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.document = self.root / "synthetic.hwpx"
        self.inventory = self.root / "expectations.json"
        self.cells = ["Member A", "■ None □ Yes", "■ None □ Yes", "", "Meal: 100"]
        self.expected = {
            "paragraphs": [{"section": SECTION, "paragraph": 0,
                            "expected": "Plan review", "source": "User instruction"}],
            "fields": [{"section": SECTION, "table": 0, "row": 0, "col": col,
                        "expected": value, "source": "Independent test input"}
                       for col, value in enumerate(self.cells)],
            "tables": [{"section": SECTION, "table": 0, "rows": 1,
                        "source": "Required table grouping"}],
        }

    def write_document(self, narrative="Plan review"):
        cells = "".join(
            '<hp:tc><hp:subList><hp:p><hp:run><hp:t>' + value +
            '</hp:t></hp:run></hp:p></hp:subList><hp:cellAddr rowAddr="0" colAddr="' +
            str(col) + '"/></hp:tc>' for col, value in enumerate(self.cells)
        )
        xml = ('<sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
               '<hp:p><hp:run><hp:t>' + narrative + '</hp:t>'
               '<hp:tbl rowCnt="1"><hp:tr>' + cells + '</hp:tr></hp:tbl>'
               '</hp:run></hp:p></sec>')
        with ZipFile(self.document, "w") as package:
            package.writestr(SECTION, xml)

    def run_gate(self, *args):
        self.inventory.write_text(json.dumps(self.expected, ensure_ascii=False), encoding="utf-8")
        # -S prevents site-packages from masking an accidental python-hwpx dependency.
        return subprocess.run([sys.executable, "-S", str(SCRIPT), str(self.document),
                               "--fields", str(self.inventory), "--fields-only", *args],
                              capture_output=True, text=True, encoding="utf-8")

    def test_independent_narrative_two_answers_budget_and_blank_signature(self):
        self.write_document()
        report = self.root / "report.json"
        result = self.run_gate("--report", str(report))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["engine"], "hwpx-xml-fields-only")
        self.assertEqual(payload["rows"][0]["form_fields"]["checked_paragraphs"], 1)
        self.assertEqual(payload["rows"][0]["form_fields"]["checked_fields"], 5)
        self.assertEqual(json.loads(report.read_text(encoding="utf-8")), payload)

    def test_reinserted_meal_sentence_fails_even_when_budget_is_valid(self):
        self.write_document("Plan review; meal afterwards")
        result = self.run_gate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("saved paragraph differs", result.stderr)

    def test_investigation_status_is_checked_independently(self):
        self.cells[2] = "□ None □ Yes"
        self.write_document()
        result = self.run_gate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Field 2: saved cell differs", result.stderr)

    def test_wrong_person_and_false_signature_fail(self):
        for col, value in ((0, "Member B"), (3, "Signed")):
            original = self.cells[col]
            self.cells[col] = value
            self.write_document()
            result = self.run_gate()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(f"Field {col}: saved cell differs", result.stderr)
            self.cells[col] = original

    def test_missing_duplicate_and_out_of_range_expectations_fail(self):
        self.write_document()
        original = self.expected["paragraphs"][0]
        for paragraphs in ([original, original], [dict(original, paragraph=7)],
                           [dict(original, source="")]):
            self.expected["paragraphs"] = paragraphs
            result = self.run_gate()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Paragraph", result.stderr)

    def test_paragraph_only_and_invalid_option_combinations(self):
        self.write_document()
        self.expected["fields"] = []
        self.assertEqual(self.run_gate().returncode, 0)
        no_inventory = subprocess.run([sys.executable, "-S", str(SCRIPT), str(self.document),
                                       "--fields-only"], capture_output=True)
        self.assertNotEqual(no_inventory.returncode, 0)
        self.assertNotEqual(self.run_gate("--roundtrip-dir", str(self.root / "out")).returncode, 0)


if __name__ == "__main__":
    unittest.main()
