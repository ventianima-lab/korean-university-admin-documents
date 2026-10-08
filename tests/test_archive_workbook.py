"""Regression: a combined roster is classified from the later populated form."""

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills/finalize-department-files/scripts/inspect_archive_workbook.py"
spec = importlib.util.spec_from_file_location("archive_inspector", SCRIPT)
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def fixture(path):
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("xl/workbook.xml", f'<workbook xmlns="{MAIN}" xmlns:r="{REL}"><sheets>'
                         '<sheet name="전교 명단" sheetId="1" r:id="a"/>'
                         '<sheet name="숨김 참고" sheetId="2" state="veryHidden" r:id="b"/>'
                         '<sheet name="학과 확인서" sheetId="3" r:id="c"/>'
                         '</sheets></workbook>')
        package.writestr("xl/_rels/workbook.xml.rels", '<Relationships>'
                         '<Relationship Id="a" Target="worksheets/roster.xml"/>'
                         '<Relationship Id="b" Target="/xl/worksheets/hidden.xml"/>'
                         '<Relationship Id="c" Target="worksheets/completed.xml"/>'
                         '</Relationships>')
        package.writestr("xl/sharedStrings.xml", f'<sst xmlns="{MAIN}">'
                         '<si><r><t>테스트</t></r><r><t>학과</t></r></si></sst>')
        package.writestr("xl/worksheets/roster.xml", f'<worksheet xmlns="{MAIN}"><sheetData><row r="1">'
                         '<c r="A1" t="inlineStr"><is><t>여러 학과</t></is></c></row></sheetData></worksheet>')
        package.writestr("xl/worksheets/hidden.xml", f'<worksheet xmlns="{MAIN}"><sheetData><row r="70">'
                         '<c r="B70"><f>1+1</f><v>2</v></c></row></sheetData></worksheet>')
        package.writestr("xl/worksheets/completed.xml", f'<worksheet xmlns="{MAIN}"><sheetData><row r="90">'
                         '<c r="A90" t="s"><v>0</v></c>'
                         '<c r="C90" t="inlineStr"><is><t>샘플학생</t></is></c>'
                         '<c r="H90" t="inlineStr"><is><t>O</t></is></c>'
                         '</row></sheetData></worksheet>')


class ArchiveWorkbookTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "양식.xlsx"
        fixture(self.path)
        self.before = hashlib.sha256(self.path.read_bytes()).hexdigest()

    def run_cli(self, *args):
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        return subprocess.run([sys.executable, str(SCRIPT), str(self.path), *args],
                              capture_output=True, text=True, encoding="utf-8", creationflags=flags)

    def test_later_form_hidden_sheet_sparse_rows_and_relationships(self):
        result = inspector.inspect(self.path)
        self.assertEqual(result["sheet_count"], 3)
        self.assertEqual(result["sheets"][1]["state"], "veryHidden")
        self.assertEqual(result["sheets"][1]["cells"]["B70"]["formula"], "1+1")
        checks = inspector.check_cells(result, [("학과 확인서", "A90", "테스트학과"),
                                                ("학과 확인서", "C90", "샘플학생"),
                                                ("학과 확인서", "H90", "O")])
        self.assertTrue(all(x["passed"] for x in checks))
        self.assertEqual(result["sha256"], self.before)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), self.before)

    def test_cli_mismatch_and_missing_sheet_fail_closed(self):
        output = Path(self.temp.name) / "inventory.json"
        run = self.run_cli("--output", str(output), "--expect-cell", "학과 확인서", "A90", "다른학과",
                           "--expect-cell", "없는 시트", "A1", "O")
        self.assertEqual(run.returncode, 2, run.stderr)
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "FAILED")
        self.assertFalse(any(x["passed"] for x in result["checks"]))
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), self.before)

    def test_evidence_output_cannot_overwrite_workbook(self):
        run = self.run_cli("--output", str(self.path))
        self.assertEqual(run.returncode, 2)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), self.before)


if __name__ == "__main__":
    unittest.main()
