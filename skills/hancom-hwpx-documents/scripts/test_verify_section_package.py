"""Exercise the header/spine mismatch observed after extracting a form."""
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import subprocess
import sys
import unittest

from validate_hwpx_opensource import verify_section_package


class SectionPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "sample.hwpx"

    def package(self, count=1, declared=("section0",), referenced=("section0",),
                stored=("section0",), relative=False):
        href = lambda name: name + ".xml" if relative else "Contents/" + name + ".xml"
        items = "".join('<item id="%s" href="%s"/>' % (name, href(name)) for name in declared)
        spine = "".join('<itemref idref="%s"/>' % name for name in referenced)
        with ZipFile(self.path, "w") as z:
            z.writestr("Contents/header.xml", '<head secCnt="%s"/>' % count)
            z.writestr("Contents/content.hpf", "<package><manifest>" + items +
                       "</manifest><spine>" + spine + "</spine></package>")
            for name in stored:
                z.writestr("Contents/" + name + ".xml", "<sec/>")

    def test_extracted_one_section_cannot_claim_three(self):
        self.package(count=3)
        with self.assertRaisesRegex(ValueError, "secCnt"):
            verify_section_package(self.path)
        self.package(count=1)
        self.assertEqual(verify_section_package(self.path)["section_count"], 1)

    def test_three_registered_sections_and_relative_paths(self):
        sections = ("section0", "section1", "section2")
        self.package(3, sections, sections, sections, relative=True)
        self.assertEqual(verify_section_package(self.path)["header_secCnt"], 3)

    def test_missing_unreferenced_or_duplicate_section_fails(self):
        for declared, referenced, stored in [
            (("section0",), ("section0",), ()),
            (("section0", "section1"), ("section0",), ("section0", "section1")),
            (("section0",), ("section0", "section0"), ("section0",)),
            (("section0",), ("section1",), ("section0",)),
        ]:
            with self.subTest(declared=declared, referenced=referenced, stored=stored):
                self.package(1, declared, referenced, stored)
                with self.assertRaises(ValueError):
                    verify_section_package(self.path)

    def test_cli_returns_failure_and_does_not_rewrite(self):
        self.package(count=3)
        before = self.path.read_bytes()
        script = Path(__file__).with_name("validate_hwpx_opensource.py")
        result = subprocess.run([sys.executable, str(script), str(self.path), "--sections-only"],
                                capture_output=True, text=True,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, self.path.read_bytes())


if __name__ == "__main__":
    unittest.main()
