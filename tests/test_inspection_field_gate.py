"""Synthetic saved-field checks for date-grouped inspection records.

The XML field gate does not check physical pagination, image content, or whether
the expected source-to-group map is exhaustive; those checks remain independent.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/hancom-hwpx-documents/scripts/validate_hwpx_opensource.py"
SPEC = importlib.util.spec_from_file_location("field_validator", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SECTION = "Contents/section0.xml"
# Independently transcribed synthetic expectations: each row is one date group.
EXPECTED = [
    ["2031-04-07", "2031-04-07", "2031-04-07", "Item A 외 2종"],
    ["2031-04-14", "2031-04-14", "2031-04-14", "Item D 외 1종"],
    ["2031-04-21", "2031-04-21", "2031-04-21", "Item F 외 3종"],
]


class InspectionFieldGateTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "inspection.hwpx"
        self.fields = [
            {"section": SECTION, "table": group, "row": 0, "col": col,
             "expected": value, "source": "Independent synthetic instruction and receipts"}
            for group, values in enumerate(EXPECTED)
            for col, value in enumerate(values)
        ]

    def save(self, groups):
        tables = []
        for values in groups:
            cells = "".join(
                '<hp:tc><hp:cellAddr rowAddr="0" colAddr="%d"/><hp:subList>'
                '<hp:p><hp:run><hp:t>%s</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
                % (col, value) for col, value in enumerate(values)
            )
            tables.append('<hp:tbl rowCnt="1"><hp:tr>' + cells + '</hp:tr></hp:tbl>')
        xml = ('<sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
               + "".join(tables) + '</sec>')
        with ZipFile(self.path, "w") as package:
            package.writestr(SECTION, xml)

    def check(self):
        return MODULE.verify_form_fields(self.path, {"fields": self.fields})

    def test_all_directed_date_and_kind_fields_match_independent_map(self):
        self.save(EXPECTED)
        self.assertEqual(self.check()["checked_fields"], 12)

    def test_each_misdirected_or_blank_date_is_rejected(self):
        for col in range(3):
            groups = deepcopy(EXPECTED)
            groups[1][col] = "" if col == 2 else "2031-04-07"
            self.save(groups)
            with self.subTest(col=col), self.assertRaisesRegex(ValueError, "saved cell differs"):
                self.check()

    def test_representative_count_and_missing_group_are_rejected(self):
        groups = deepcopy(EXPECTED)
        groups[0][3] = "Item A 외 1종"
        self.save(groups)
        with self.assertRaisesRegex(ValueError, "saved cell differs"):
            self.check()
        self.save(EXPECTED[:2])
        with self.assertRaises((IndexError, ValueError)):
            self.check()

    def test_unlisted_extra_unit_requires_separate_group_and_page_review(self):
        groups = deepcopy(EXPECTED)
        groups.append(["unlisted", "unlisted", "unlisted", "unlisted"])
        self.save(groups)
        self.assertEqual(self.check()["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
