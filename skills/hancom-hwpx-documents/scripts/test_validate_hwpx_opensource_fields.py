"""Exact-cell checks must include all text around inline controls."""
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import unittest
from validate_hwpx_opensource import verify_form_fields


class ExactFieldMixedContentTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic.hwpx"

    def package(self, content):
        xml = ('<sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
               '<hp:p><hp:run><hp:tbl><hp:tr><hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/>'
               '<hp:subList><hp:p><hp:run><hp:t>' + content + '</hp:t></hp:run></hp:p>'
               '</hp:subList></hp:tc></hp:tr></hp:tbl></hp:run></hp:p></sec>')
        with ZipFile(self.path, "w") as z:
            z.writestr("Contents/section0.xml", xml)

    def field(self, expected):
        return {"fields": [{"section": "Contents/section0.xml", "table": 0,
                            "row": 0, "col": 0, "source": "synthetic source",
                            "expected": expected}]}

    def test_text_after_break_is_included(self):
        self.package("first<hp:lineBreak/>second")
        self.assertEqual(verify_form_fields(self.path, self.field("firstsecond"))["status"], "PASS")

    def test_missing_tail_is_not_a_pass(self):
        self.package("first<hp:lineBreak/>second")
        with self.assertRaises(ValueError):
            verify_form_fields(self.path, self.field("first"))

    def test_text_after_other_control_is_not_blank(self):
        self.package("<hp:fwSpace/>unwanted")
        with self.assertRaises(ValueError):
            verify_form_fields(self.path, self.field(""))

    def test_real_empty_field_can_still_pass(self):
        self.package("<hp:fwSpace/>")
        self.assertEqual(verify_form_fields(self.path, self.field(""))["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
