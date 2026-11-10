"""Synthetic scoped invocations, not an automatic stage/owner classifier.

The independent instruction-to-role interpretation is a human/agent review gate.
These fixtures test its interface to the existing required-packet checker.
"""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/hancom-hwpx-documents/scripts"
sys.path.insert(0, str(SCRIPTS))
from verify_required_packet import audit as check


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


if __name__ == "__main__":
    unittest.main()
