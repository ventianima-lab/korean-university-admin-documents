"""Synthetic scoped invocations, not an automatic stage/owner classifier.

The independent instruction-to-role interpretation is a human/agent review gate.
These fixtures test its interface to the existing required-packet checker.
"""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from xml.sax.saxutils import escape
from zipfile import ZipFile

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/hancom-hwpx-documents/scripts"
sys.path.insert(0, str(SCRIPTS))
from verify_required_packet import audit as check
from validate_hwpx_opensource import verify_form_fields


class PreapprovalScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        prepared = Path(self.temp.name) / "synthetic-plan.txt"
        prepared.write_text("Synthetic current preparation; no signed contract.", encoding="utf-8")
        authority = "Fictional instruction: office contracts with vendor after all letters are approved."
        self.manifest = {
            "requirements": [{"id": "plan", "source": "Fictional current preapproval list"}],
            "artifacts": [{"id": "plan", "status": "ready", "paths": [str(prepared)],
                           "verification": "Synthetic plan fixture exists; not proof of approval."}],
            "expense_reviews": [{"category": "service", "source": "Fictional service checklist",
                "items": [
                    {"label": "operating plan", "status": "required", "requirement_id": "plan"},
                    {"label": "executed contract", "status": "not_applicable",
                     "reason": authority + " Later office execution is outside current preapproval preparation."}]}],
        }

    def test_confirmed_later_office_contract_does_not_block_current_scope(self):
        result = check(self.manifest)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual([r["id"] for r in result["requirements"]], ["plan"])

    def test_flat_list_reintroducing_future_execution_blocks(self):
        candidate = copy.deepcopy(self.manifest)
        candidate["requirements"].append({"id": "executed-contract", "source": "Unscoped checklist"})
        self.assertEqual(check(candidate)["status"], "INCOMPLETE")
        # The fix is independent stage review and scoped invocation, not fabrication.

    def test_separately_requested_vendor_review_draft_still_required(self):
        candidate = copy.deepcopy(self.manifest)
        candidate["requirements"].append({"id": "review-draft", "source": "Fictional vendor request: unsigned information form now"})
        candidate["expense_reviews"][0]["items"].append(
            {"label": "unsigned information form", "status": "required", "requirement_id": "review-draft"})
        result = check(candidate)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["requirements"][-1]["status"], "missing_role")

    def test_unresolved_trigger_or_owner_remains_pending(self):
        candidate = copy.deepcopy(self.manifest)
        candidate["expense_reviews"][0]["items"][1] = {"label": "executed contract", "status": "pending"}
        result = check(candidate)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["expense_review_issues"][0]["problem"], "applicability_pending")

    def test_stage_exclusion_needs_a_reason(self):
        candidate = copy.deepcopy(self.manifest)
        del candidate["expense_reviews"][0]["items"][1]["reason"]
        result = check(candidate)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["expense_review_issues"][0]["problem"], "exclusion_reason_missing")

    def test_genuinely_missing_current_plan_still_blocks(self):
        candidate = copy.deepcopy(self.manifest)
        candidate["artifacts"] = []
        self.assertEqual(check(candidate)["status"], "INCOMPLETE")


class TravelStageScopeTests(unittest.TestCase):
    """Fictional role-specific forms; no current institutional procedure implied."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.travelers = {"faculty": ("Member A", "Faculty"), "staff": ("Member B", "Staff")}
        self.manifest = {
            "requirements": [{"id": role, "source": "Fictional current procedure: pretrip paper application for this role"}
                             for role in self.travelers],
            "artifacts": [],
            "expense_reviews": [{"category": "travel", "source": "Fictional current travel procedure",
                "items": [{"label": role + " pretrip application", "status": "required", "requirement_id": role}
                          for role in self.travelers]}],
        }

    def form(self, role, title="출장승인신청서", purpose_label="출장목적"):
        path = self.root / (role + str(len(list(self.root.iterdir()))) + ".hwpx")
        cells = [*self.travelers[role], "2030-04-03", purpose_label, ""]
        xml_cells = "".join(
            '<hp:tc><hp:subList><hp:p><hp:run><hp:t>' + escape(value) +
            '</hp:t></hp:run></hp:p></hp:subList><hp:cellAddr rowAddr="0" colAddr="' +
            str(col) + '"/></hp:tc>' for col, value in enumerate(cells))
        with ZipFile(path, "w") as package:
            package.writestr("Contents/section0.xml",
                '<sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
                '<hp:p><hp:run><hp:t>' + title + '</hp:t><hp:tbl rowCnt="1"><hp:tr>' +
                xml_cells + '</hp:tr></hp:tbl></hp:run></hp:p></sec>')
        return path

    def expected(self, role):
        return {
            "paragraphs": [{"section": "Contents/section0.xml", "paragraph": 0,
                            "expected": "출장승인신청서", "source": "Independently selected fictional application master"}],
            "fields": [{"section": "Contents/section0.xml", "table": 0, "row": 0, "col": col,
                        "expected": value, "source": "Fictional role-specific instruction and master"}
                       for col, value in enumerate([*self.travelers[role], "2030-04-03", "출장목적", ""])],
        }

    def ready_application(self, role):
        path = self.form(role)
        verify_form_fields(path, self.expected(role))
        self.manifest["artifacts"].append({"id": role, "status": "ready", "paths": [str(path)],
            "verification": "Exact fictional application title/fields and role checked; locally prepared only.",
            "title_band_checks": [{"path": str(path), "not_applicable": True, "master": str(path),
                "source": "Synthetic fixture topology only; not a real form master",
                "reason": "This minimal fixture has a top-level title paragraph, not a table title band."}]})

    def test_two_return_reports_with_same_people_and_dates_do_not_fill_applications(self):
        for role in self.travelers:
            report = self.form(role, "출장복명서", "복명내용")
            expectations = self.expected(role)
            # A name/date-only test passes, demonstrating why it cannot establish form role.
            verify_form_fields(report, {"fields": [expectations["fields"][i] for i in (0, 2)]})
            with self.assertRaises(ValueError):
                verify_form_fields(report, expectations)
        result = check(self.manifest)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual([r["status"] for r in result["requirements"]], ["missing_role", "missing_role"])

    def test_retitling_report_does_not_make_its_fields_an_application(self):
        report = self.form("faculty", "출장승인신청서", "복명내용")
        with self.assertRaisesRegex(ValueError, "Field 3: saved cell differs"):
            verify_form_fields(report, self.expected("faculty"))

    def test_faculty_application_cannot_cover_missing_staff_role(self):
        self.ready_application("faculty")
        result = check(self.manifest)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["requirements"][1]["status"], "missing_role")

    def test_matching_name_and_date_do_not_allow_role_swap(self):
        faculty_form = self.form("faculty")
        expected = self.expected("faculty")
        expected["fields"][1]["expected"] = "Staff"
        with self.assertRaisesRegex(ValueError, "Field 1: saved cell differs"):
            verify_form_fields(faculty_form, expected)

    def test_prepared_applications_pass_with_controlled_fields_blank(self):
        for role in self.travelers:
            self.ready_application(role)
        result = check(self.manifest, preparation_scope=True)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["scope"], "authorized_preparation")
        # PASS establishes neither ERP submission nor actual travel approval.

    def test_unresolved_current_route_blocks_without_inventing_paper_requirement(self):
        candidate = {"requirements": [{"id": "route", "source": "Fictional unresolved current route"}],
            "artifacts": [{"id": "route", "status": "pending", "paths": [],
                           "verification": "Confirm ERP-only versus applicable paper procedure."}],
            "expense_reviews": [{"category": "travel", "source": "Current route under review",
                "items": [{"label": "pretrip approval process", "status": "pending"}]}]}
        self.assertEqual(check(candidate)["status"], "INCOMPLETE")

    def test_confirmed_erp_only_preparation_does_not_require_paper_form(self):
        evidence = self.root / "fictional-erp-saved-entry.txt"
        evidence.write_text("Fictional saved entry; not submitted or approved.", encoding="utf-8")
        candidate = {"requirements": [{"id": "erp-entry", "source": "Fictional confirmed ERP-only preparation instruction"}],
            "artifacts": [{"id": "erp-entry", "status": "ready", "paths": [str(evidence)],
                           "verification": "Synthetic saved-entry evidence only; no submission or approval verified."}],
            "expense_reviews": [{"category": "travel", "source": "Fictional ERP-only procedure",
                "items": [{"label": "ERP entry preparation", "status": "required", "requirement_id": "erp-entry"},
                          {"label": "paper application", "status": "not_applicable",
                           "reason": "Fictional current procedure explicitly uses only ERP for this role and stage."}]}]}
        self.assertEqual(check(candidate, preparation_scope=True)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
