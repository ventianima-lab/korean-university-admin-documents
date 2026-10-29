"""Regression cases for unauthorized text in an original blank title region."""
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import unittest
from verify_title_band import check_title_band
from verify_required_packet import audit


def create_sample(path, title="Official title", spacer="", field="Value"):
    values = ["", title, "", spacer, field]
    rows = []
    for index, value in enumerate(values):
        rows.append('<hp:tr><hp:tc><hp:cellAddr rowAddr="%s" colAddr="0"/>'
                    '<hp:subList><hp:p><hp:run><hp:t>%s</hp:t></hp:run></hp:p></hp:subList>'
                    '</hp:tc></hp:tr>' % (index, value))
    xml = ('<sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
           '<hp:p><hp:run><hp:tbl>' + "".join(rows) + '</hp:tbl></hp:run></hp:p></sec>')
    with ZipFile(path, "w") as archive:
        archive.writestr("Contents/section0.xml", xml)


class TitleBandTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        directory = Path(self.temp.name)
        self.master, self.candidate = directory / "master.hwpx", directory / "candidate.hwpx"
        create_sample(self.master, field="Existing label")
        self.band = {"master": str(self.master), "master_section": "Contents/section0.xml",
                     "master_table": 0, "target_section": "Contents/section0.xml",
                     "target_table": 0, "first_content_row": 4,
                     "title_row": 1, "title_col": 0, "source": "official synthetic form"}

    def packet(self, checks=None):
        artifact = {"id": "report", "status": "ready", "paths": [str(self.candidate)],
                    "verification": "ready for testing"}
        if checks is not None:
            artifact["title_band_checks"] = checks
        return {"requirements": [{"id": "report", "source": "synthetic manual"}],
                "artifacts": [artifact]}

    def test_unrequested_title_in_original_blank_is_rejected(self):
        create_sample(self.candidate, spacer="Event title")
        result = check_title_band(self.candidate, self.band)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["issues"], [{"row": 3, "col": 0, "problem": "unexpected_text"}])
        checks = [{"path": str(self.candidate), "bands": [self.band]}]
        self.assertEqual(audit(self.packet(checks))["status"], "INCOMPLETE")

    def test_clean_title_band_and_filled_business_field_pass(self):
        create_sample(self.candidate, field="Actual field value")
        self.assertEqual(check_title_band(self.candidate, self.band)["status"], "PASS")
        checks = [{"path": str(self.candidate), "bands": [self.band]}]
        self.assertEqual(audit(self.packet(checks))["status"], "PASS")

    def test_packet_never_passes_when_the_check_was_omitted(self):
        create_sample(self.candidate)
        result = audit(self.packet())
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["requirements"][0]["title_band_issues"][0]["problem"],
                         "title_band_check_missing_or_duplicate")

    def test_nonempty_inline_tail_is_detected(self):
        create_sample(self.candidate, spacer="<hp:lineBreak/>Unwanted")
        self.assertEqual(check_title_band(self.candidate, self.band)["status"], "FAIL")

    def test_text_in_new_title_band_cell_is_rejected(self):
        create_sample(self.candidate)
        with ZipFile(self.candidate) as archive:
            xml = archive.read("Contents/section0.xml").decode("utf-8")
        xml = xml.replace('<hp:tr><hp:tc><hp:cellAddr rowAddr="3" colAddr="0"/>',
                          '<hp:tr><hp:tc><hp:cellAddr rowAddr="3" colAddr="1"/>'
                          '<hp:subList><hp:p><hp:run><hp:t>extra</hp:t></hp:run></hp:p></hp:subList>'
                          '</hp:tc><hp:tc><hp:cellAddr rowAddr="3" colAddr="0"/>')
        with ZipFile(self.candidate, "w") as archive:
            archive.writestr("Contents/section0.xml", xml)
        result = check_title_band(self.candidate, self.band)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["issues"][0]["problem"], "new_cell_text")

    def test_changed_anchor_is_not_silently_accepted(self):
        create_sample(self.candidate, title="Other title")
        with self.assertRaises(ValueError):
            check_title_band(self.candidate, self.band)

    def test_exception_requires_source_and_exact_user_value(self):
        create_sample(self.candidate, spacer="Explicitly requested")
        self.band["exceptions"] = [{"row": 3, "col": 0, "expected": "Explicitly requested",
                                     "source": "direct user request"}]
        self.assertEqual(check_title_band(self.candidate, self.band)["status"], "PASS")
        self.band["exceptions"][0]["expected"] = "Another value"
        self.assertEqual(check_title_band(self.candidate, self.band)["status"], "FAIL")
        self.band["exceptions"][0]["source"] = ""
        with self.assertRaises(ValueError):
            check_title_band(self.candidate, self.band)


if __name__ == "__main__":
    unittest.main()
