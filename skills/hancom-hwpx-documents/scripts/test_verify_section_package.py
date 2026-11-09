"""Exercise the header/spine mismatch observed after extracting a form."""
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import subprocess
import sys
import unittest

from validate_hwpx_opensource import verify_section_package, verify_embedded_images


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


class EmbeddedImagePackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "image.hwpx"

    def package(self, flag=None, attribute="isEmbeded", href="BinData/photo.png",
                reference="image0", store=True, media="image/png"):
        import base64
        image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII=")
        extra = '' if flag is None else f' {attribute}="{flag}"'
        with ZipFile(self.path, "w") as z:
            z.writestr("Contents/header.xml", '<head secCnt="1"/>')
            z.writestr("Contents/content.hpf",
                       '<package><manifest><item id="section0" href="Contents/section0.xml"/>'
                       f'<item id="image0" href="{href}" media-type="{media}"{extra}/>'
                       '</manifest><spine><itemref idref="section0"/></spine></package>')
            z.writestr("Contents/section0.xml",
                       '<sec xmlns:hp="urn:paragraph" xmlns:hc="urn:core"><hp:p><hp:run>'
                       f'<hp:pic><hc:img binaryItemIDRef="{reference}"/></hp:pic>'
                       '</hp:run></hp:p></sec>')
            if store:
                z.writestr("BinData/photo.png", image)

    def test_missing_embed_flag_fails_and_metadata_only_fix_passes(self):
        self.package()
        with ZipFile(self.path) as z:
            before = {n: z.read(n) for n in z.namelist()}
        with self.assertRaisesRegex(ValueError, "isEmbeded=1"):
            verify_embedded_images(self.path)
        self.package("1")
        fixed_bytes = self.path.read_bytes()
        result = verify_embedded_images(self.path)
        self.assertEqual((result["checked_images"], result["image_references"]), (1, 1))
        self.assertEqual(self.path.read_bytes(), fixed_bytes)
        with ZipFile(self.path) as z:
            self.assertEqual([n for n in z.namelist() if z.read(n) != before[n]],
                             ["Contents/content.hpf"])

    def test_zero_and_misspelled_embed_flags_fail(self):
        for value, attribute in [("0", "isEmbeded"), ("1", "isEmbedded")]:
            with self.subTest(value=value, attribute=attribute):
                self.package(value, attribute)
                with self.assertRaisesRegex(ValueError, "isEmbeded=1"):
                    verify_embedded_images(self.path)

    def test_missing_reference_part_and_wrong_media_fail(self):
        for options in ({"reference": "absent"}, {"store": False},
                        {"media": "application/octet-stream"}):
            with self.subTest(options=options):
                self.package("1", **options)
                with self.assertRaises(ValueError):
                    verify_embedded_images(self.path)

    def test_relative_image_path_passes(self):
        self.package("1", href="../BinData/photo.png")
        self.assertEqual(verify_embedded_images(self.path)["checked_images"], 1)

    def test_images_only_cli_pass_fail_and_no_rewrite(self):
        import json
        script = Path(__file__).with_name("validate_hwpx_opensource.py")
        for flag, expected_code in [(None, 1), ("1", 0)]:
            self.package(flag)
            before = self.path.read_bytes()
            result = subprocess.run([sys.executable, str(script), str(self.path), "--images-only"],
                                    capture_output=True, text=True,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.assertEqual(result.returncode == 0, expected_code == 0, result.stderr)
            self.assertEqual(self.path.read_bytes(), before)
            if expected_code == 0:
                self.assertEqual(json.loads(result.stdout)["rows"][0]["embedded_images"]["checked_images"], 1)


if __name__ == "__main__":
    unittest.main()
