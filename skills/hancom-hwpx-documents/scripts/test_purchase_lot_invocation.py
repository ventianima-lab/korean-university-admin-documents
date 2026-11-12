"""Synthetic source-map invocations of existing field and packet checkers.

No actual records or native applications. These tests check supplied expectations,
not source authenticity, form eligibility, image provenance or actual receipt.
"""
import hashlib
from pathlib import Path
import tempfile
import unittest
from xml.sax.saxutils import escape
from zipfile import ZipFile

from validate_hwpx_opensource import verify_form_fields
from verify_required_packet import audit


# Fictional independent authority: one purchased lot serves three sessions;
# a second lot is still planned. Sign-off scope is a later separate instruction.
SESSIONS = ((1, "2030-04-01", 2), (2, "2030-04-03", 2), (3, "2030-04-09", 2),
            (4, "2030-04-21", 2), (5, "2030-04-22", 2))
LOTS = (("purchased", "2030-04-01", 30000, (1, 2, 3)),
        ("planned", "2030-04-21", 20000, (4, 5)))


class PurchaseLotInvocationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.saved = self.root / "synthetic.hwpx"
        self.period = f"{SESSIONS[0][1]}~{SESSIONS[2][1]}"
        self.expected = [self.period, "3 sessions", "6 hours", "30000", "purchased",
                         "Goods for sessions 1~3", "Purchase date", "2030-04-01", "", "",
                         "sessions 4~5: planned 20000 on 2030-04-21", "50000",
                         self.period, "30000", ""]
        self.inventory = {"fields": [
            {"section": "Contents/section0.xml", "table": 0, "row": row, "col": 0,
             "expected": value,
             "source": "Independent fictional lot/session authority; retained metadata blanks expressly directed"}
            for row, value in enumerate(self.expected)]}

    def write_form(self, overrides=None):
        values = list(self.expected)
        for row, value in (overrides or {}).items():
            values[row] = value
        rows = "".join(
            f'<hp:tr><hp:tc><hp:cellAddr rowAddr="{row}" colAddr="0"/>'
            f'<hp:subList><hp:p><hp:run><hp:t>{escape(value)}</hp:t></hp:run>'
            '</hp:p></hp:subList></hp:tc></hp:tr>' for row, value in enumerate(values))
        with ZipFile(self.saved, "w") as package:
            package.writestr("Contents/section0.xml",
                '<sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
                f'<hp:p><hp:run><hp:tbl>{rows}</hp:tbl></hp:run></hp:p></sec>')

    def check(self):
        return verify_form_fields(self.saved, self.inventory)

    def test_full_mapping_with_one_purchase_and_future_lot_passes(self):
        # Derive arithmetic from the independent authority, never the candidate.
        mapped = [s for s in SESSIONS if s[0] in LOTS[0][3]]
        self.assertEqual(sum(s[2] for s in mapped), 6)
        self.assertEqual(sum(lot[2] for lot in LOTS), 50000)
        self.write_form()
        self.assertEqual(self.check()["checked_fields"], len(self.expected))

    def test_single_session_period_or_stale_repeated_period_fails(self):
        for row in (0, 12):
            with self.subTest(row=row):
                self.write_form({row: "2030-04-01"})
                with self.assertRaises(ValueError):
                    self.check()

    def test_wrong_session_count_or_teaching_hours_fails(self):
        for row, value in ((1, "1 session"), (2, "2 hours"), (2, "9 days")):
            with self.subTest(row=row, value=value):
                self.write_form({row: value})
                with self.assertRaises(ValueError):
                    self.check()

    def test_multiplying_purchase_or_relabeling_planned_lot_fails(self):
        for row, value in ((3, "90000"), (13, "90000"), (4, "planned"),
                           (10, "sessions 4~5: purchased 20000 on 2030-04-21")):
            with self.subTest(row=row):
                self.write_form({row: value})
                with self.assertRaises(ValueError):
                    self.check()

    def test_correct_budget_cannot_hide_photo_metadata_role_errors(self):
        for row, value in ((5, "Goods for session 1"), (6, "Operating date"),
                           (7, self.period), (8, "10:00~12:00"), (9, "Classroom")):
            with self.subTest(row=row):
                self.write_form({row: value})  # Overall budget remains 50000.
                with self.assertRaises(ValueError):
                    self.check()

    def test_new_unsigned_form_cannot_inherit_signature(self):
        self.write_form({14: "copied signature"})
        with self.assertRaises(ValueError):
            self.check()

    def signoff_packet(self, pooled):
        packet_dir = self.root / "signoffs"
        packet_dir.mkdir()
        ids = [f"session-{session[0]}" for session in SESSIONS]
        artifacts = []
        for role in ids:
            path = packet_dir / ("pooled.txt" if pooled else role + ".txt")
            path.write_text("Symbolic unsigned receipt-form role only", encoding="utf-8")
            artifacts.append({"id": role, "status": "ready", "paths": [str(path)],
                              "verification": "Symbolic grouping fixture, not an actual official form"})
        return {
            "requirements": [{"id": role, "source": "Latest fictional instruction: one form for each of five sessions"}
                             for role in ids],
            "artifacts": artifacts,
            "expense_reviews": [{"category": "supplies", "source": "Fictional scope",
                "items": [{"label": role, "status": "required", "requirement_id": role} for role in ids]}],
            "output_group_check": {"packet_directory": str(packet_dir),
                "active_files": [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                                 for p in packet_dir.rglob("*") if p.is_file()],
                "groups": [{"id": "receipt-signoffs", "source": "Later fictional per-session request supersedes pooled grouping",
                            "requirement_ids": ids, "expected_file_count": len(SESSIONS)}]}}

    def test_later_per_session_instruction_cannot_reuse_pooled_file(self):
        result = audit(self.signoff_packet(pooled=True), output_group_check=True)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertIn("output_group_file_count_mismatch",
                      [issue["problem"] for issue in result["output_group_issues"]])

    def test_per_session_count_is_independent_of_two_purchase_lots(self):
        self.assertEqual(len(LOTS), 2)
        self.assertEqual(audit(self.signoff_packet(pooled=False), output_group_check=True)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
