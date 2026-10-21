"""Synthetic exact-cell tests; no private records are required."""
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from validate_hwpx_opensource import verify_form_fields, verify_section_opening


class FieldGateTests(unittest.TestCase):
    def create(self, folder, value):
        path = Path(folder) / "synthetic.hwpx"
        xml = ('<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
               'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"><hp:p><hp:run><hp:tbl><hp:tr>'
               '<hp:tc><hp:subList><hp:p><hp:run><hp:t>이름</hp:t></hp:run></hp:p></hp:subList>'
               '<hp:cellAddr rowAddr="0" colAddr="0"/></hp:tc>'
               '<hp:tc><hp:subList><hp:p><hp:run><hp:t>'+value+'</hp:t></hp:run></hp:p></hp:subList>'
               '<hp:cellAddr rowAddr="0" colAddr="1"/></hp:tc>'
               '</hp:tr></hp:tbl></hp:run></hp:p></hs:sec>')
        with ZipFile(path, "w") as package:
            package.writestr("Contents/section0.xml", xml)
        return path

    def manifest(self, expected, col=1):
        return {"fields": [{"section": "Contents/section0.xml", "table": 0,
                            "row": 0, "col": col, "expected": expected, "source": "synthetic evidence"}]}

    def test_known_value_cannot_remain_blank(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                verify_form_fields(self.create(folder, ""), self.manifest("수신자"))

    def test_value_elsewhere_does_not_satisfy_target(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                verify_form_fields(self.create(folder, ""), self.manifest("이름", col=1))

    def test_known_value_and_intentional_blank(self):
        for value in ("수신자", ""):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as folder:
                result = verify_form_fields(self.create(folder, value), self.manifest(value))
                self.assertEqual(result["checked_fields"], 1)

    def test_missing_provenance_and_empty_inventory_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.create(folder, "수신자")
            for inventory in ({"fields": []}, self.manifest("수신자")):
                if inventory["fields"]:
                    inventory["fields"][0]["source"] = ""
                with self.assertRaises(ValueError):
                    verify_form_fields(path, inventory)

    def test_summary_checkbox_and_shipping_total_are_exact_fields(self):
        pairs = [
            ("복사용지 외 4종", "복사용지 외 3종"),
            ("■ 실험실습재료 □ 기타", "■ 실험실습재료 ■ 기타"),
            ("8,000", "5,000"),
            ("스마트폰 거치대", "홀더"),
        ]
        with tempfile.TemporaryDirectory() as folder:
            for expected, wrong in pairs:
                with self.subTest(expected=expected):
                    with self.assertRaises(ValueError):
                        verify_form_fields(self.create(folder, wrong), self.manifest(expected))
                    verify_form_fields(self.create(folder, expected), self.manifest(expected))

    def test_grouping_is_checked_independently_for_each_table(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.create(folder, "12,000")
            inventory = self.manifest("12,000")
            table = {"section": "Contents/section0.xml", "table": 0,
                     "rows": 1, "source": "User requests one aggregate row; total is unchanged"}
            inventory["tables"] = [table]
            self.assertEqual(verify_form_fields(path, inventory)["checked_tables"], 1)
            table["rows"] = 2
            with self.assertRaises(ValueError):
                verify_form_fields(path, inventory)
            table["rows"] = 1
            table["source"] = ""
            with self.assertRaises(ValueError):
                verify_form_fields(path, inventory)


class SectionOpeningTests(unittest.TestCase):
    def make(self, folder, runs):
        path = Path(folder) / "opening.hwpx"
        xml = ('<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
               'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"><hp:p>'
               '<hp:run><hp:secPr/></hp:run>' + runs + '</hp:p></hs:sec>')
        with ZipFile(path, "w") as package:
            package.writestr("Contents/section0.xml", xml)
        return path

    def test_early_column_control_keeps_both_drawing_and_table(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make(folder, '<hp:run><hp:ctrl><hp:colPr/></hp:ctrl></hp:run>'
                             '<hp:run><hp:pic/><hp:tbl/></hp:run>')
            self.assertEqual(verify_section_opening(path)["checked_sections"], 1)

    def test_late_column_after_each_kind_of_object_fails(self):
        for drawing in ("pic", "tbl"):
            with self.subTest(drawing=drawing), tempfile.TemporaryDirectory() as folder:
                path = self.make(folder, f'<hp:run><hp:{drawing}/><hp:ctrl><hp:colPr/>'
                                 '</hp:ctrl></hp:run>')
                with self.assertRaisesRegex(ValueError, "SECTION_OPENING_ORDER"):
                    verify_section_opening(path)

    def test_nested_cell_controls_do_not_change_section_order(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make(folder, '<hp:run><hp:ctrl><hp:colPr/></hp:ctrl><hp:tbl>'
                             '<hp:tr><hp:tc><hp:subList><hp:p><hp:run><hp:ctrl><hp:colPr/>'
                             '</hp:ctrl></hp:run></hp:p></hp:subList></hp:tc></hp:tr>'
                             '</hp:tbl></hp:run>')
            self.assertEqual(verify_section_opening(path)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
