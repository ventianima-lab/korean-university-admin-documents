"""Synthetic exact-cell tests; no private records are required."""
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from validate_hwpx_opensource import verify_form_fields


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


if __name__ == "__main__":
    unittest.main()
