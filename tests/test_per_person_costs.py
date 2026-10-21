"""Synthetic HWPX saved-cell tests; no institutional records."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
LOADER = importlib.util.spec_from_file_location("costs", ROOT / "skills/hancom-hwpx-documents/scripts/verify_per_person_costs.py")
MODULE = importlib.util.module_from_spec(LOADER)
LOADER.loader.exec_module(MODULE)


class CostingTests(unittest.TestCase):
    def check(self, text, roles, amount=24000, copies=1):
        with tempfile.TemporaryDirectory() as folder:
            bindings = []
            for i in range(copies):
                path = Path(folder) / f"form{i}.hwpx"
                xml = f'<section xmlns:h="http://www.hancom.co.kr/hwpml/2011/paragraph"><h:tbl><h:tr><h:tc><h:subList><h:p><h:run><h:t>{text}</h:t></h:run></h:p></h:subList><h:cellAddr rowAddr="0" colAddr="0"/></h:tc></h:tr></h:tbl></section>'
                with ZipFile(path, "w") as z:
                    z.writestr("Contents/section0.xml", xml)
                bindings.append(dict(path=str(path), table=0, row=0, col=0, paragraph=0))
            return MODULE.verify({"items": [dict(roles=roles, source="Synthetic independent attendance", unit_price=3000, servings=2, amount=amount, bindings=bindings)]})

    def test_repeated_forms(self):
        self.assertEqual(len(self.check("다과 4명×3,000원×2회", {"learners": 3, "instructor": 1}, copies=2)), 2)

    def test_omitted_instructor_rejected(self):
        with self.assertRaisesRegex(ValueError, "Saved factors"):
            self.check("다과 3명×3,000원×2회", {"learners": 3, "instructor": 1})

    def test_arithmetic_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "amount mismatch"):
            self.check("다과 4명×3,000원×2회", {"learners": 3, "instructor": 1}, amount=18000)

    def test_lump_sum_rejected(self):
        with self.assertRaisesRegex(ValueError, "Saved factors"):
            self.check("다과 24,000원", {"learners": 3, "instructor": 1})

    def test_missing_basis_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.verify({"items": []})


if __name__ == "__main__":
    unittest.main()
